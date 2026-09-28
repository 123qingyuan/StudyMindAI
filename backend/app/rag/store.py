"""Real semantic embeddings + Qdrant; explicitly labelled lexical fallback."""
from __future__ import annotations
import asyncio
import hashlib
import math
import os
import threading
from pathlib import Path
import httpx
from .. import core
from ..ai.common import connection, rows, owned, fail
from ..ai.providers import ProviderError, endpoint, validate_url, TIMEOUT, read_json
from ..ai.service import get_config

_CLIENTS = {}
_MODELS = {}
_LOCK = threading.RLock()
LOCAL_MODEL = 'BAAI/bge-small-zh-v1.5'


def vector_client():
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise RuntimeError('Qdrant component is not included in this desktop build') from None
    server = os.getenv('QDRANT_URL', '')
    path = str(Path(core.DATA_DIR) / 'qdrant')
    key = server or path
    with _LOCK:
        if key not in _CLIENTS:
            _CLIENTS[key] = QdrantClient(url=server, api_key=os.getenv('QDRANT_API_KEY'), timeout=20) if server else QdrantClient(path=path)
        return _CLIENTS[key]


def close_clients():
    with _LOCK:
        for client in _CLIENTS.values():
            client.close()
        _CLIENTS.clear()


def fingerprint(config):
    if config.embedding_mode == 'local':
        model = os.getenv('LOCAL_EMBEDDING_MODEL', LOCAL_MODEL)
        value = 'local:' + model
    else:
        value = 'api:' + (config.embedding_base_url or config.base_url) + ':' + config.embedding_model
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def local_embed(texts):
    from fastembed import TextEmbedding
    model = os.getenv('LOCAL_EMBEDDING_MODEL', LOCAL_MODEL)
    cache = os.getenv('LOCAL_EMBEDDING_CACHE', str(Path(core.DATA_DIR) / 'models'))
    key = model + ':' + cache
    with _LOCK:
        if key not in _MODELS:
            # Only a preinstalled server-managed model may load in request handlers.
            _MODELS[key] = TextEmbedding(model_name=model, cache_dir=cache, threads=2, local_files_only=True)
        return [vector.tolist() for vector in _MODELS[key].embed(texts, batch_size=16)]


async def embeddings(texts, config):
    try:
        if config.embedding_mode == 'local':
            vectors = await asyncio.to_thread(local_embed, texts)
        elif config.embedding_mode == 'api':
            if not config.embedding_model or not config.api_key:
                fail(503, 'EMBEDDING_NOT_CONFIGURED', '语义向量模型未配置')
            base = config.embedding_base_url or config.base_url
            await validate_url(base, config.allow_private)
            vectors = []
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
                for start in range(0, len(texts), 32):
                    batch = texts[start:start + 32]
                    async with client.stream('POST', endpoint(base, '/embeddings'),
                        headers={'Authorization': 'Bearer ' + config.api_key},
                        json={'model': config.embedding_model, 'input': batch}) as response:
                        data = await read_json(response)
                    items = sorted(data['data'], key=lambda item: item['index'])
                    if [item['index'] for item in items] != list(range(len(batch))):
                        raise ValueError
                    vectors.extend(item['embedding'] for item in items)
        else:
            fail(422, 'EMBEDDING_DISABLED', '当前使用关键词检索，不生成语义向量')
        if len(vectors) != len(texts) or not vectors or not 8 <= len(vectors[0]) <= 8192:
            raise ValueError
        dimension = len(vectors[0])
        if any(len(v) != dimension or any(not math.isfinite(float(x)) for x in v) for v in vectors):
            raise ValueError
        return vectors
    except ProviderError as exc:
        fail(exc.status, exc.code, exc.message)
    except (ImportError, OSError, ValueError, KeyError, TypeError, httpx.HTTPError):
        fail(503, 'EMBEDDING_UNAVAILABLE', '语义模型不可用；请由管理员预安装本地模型或配置向量 API')


def upsert_vectors(chunk_rows, vectors, config, user_id, document_id):
    from qdrant_client import models
    name = 'study_' + fingerprint(config)
    with _LOCK:
        client = vector_client()
        if not client.collection_exists(name):
            client.create_collection(name, vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE))
        points = [models.PointStruct(id=chunk['id'], vector=vector,
                  payload={'user_id': user_id, 'document_id': document_id})
                  for chunk, vector in zip(chunk_rows, vectors)]
        for start in range(0, len(points), 64):
            client.upsert(name, points[start:start + 64], wait=True)
        saved = client.retrieve(name, ids=[chunk['id'] for chunk in chunk_rows], with_payload=False, with_vectors=False)
        if len(saved) != len(chunk_rows):
            raise RuntimeError('Qdrant verification failed')
    return name


async def index_document(document_id, user_id):
    config = get_config(user_id)
    with connection() as conn:
        owned(conn, 'documents', document_id, user_id)
        chunks = rows(conn.execute('SELECT * FROM document_chunks WHERE document_id=? AND user_id=? ORDER BY ordinal', (document_id, user_id)).fetchall())
    if not chunks:
        fail(422, 'NO_TEXT', '文档没有可入库文本')
    if config.embedding_mode == 'keyword':
        mode, fp = 'keyword', None
    else:
        vectors = await embeddings([chunk['content'] for chunk in chunks], config)
        try:
            await asyncio.to_thread(upsert_vectors, chunks, vectors, config, user_id, document_id)
        except Exception:
            fail(503, 'VECTOR_STORE_UNAVAILABLE', '向量数据库暂不可用，文档文本已保留')
        mode, fp = 'semantic', fingerprint(config)
    with connection() as conn:
        owned(conn, 'documents', document_id, user_id)
        conn.execute('UPDATE document_links SET index_mode=?,embedding_fingerprint=?,error_code=NULL WHERE document_id=?', (mode, fp, document_id))
    return {'document_id': document_id, 'retrieval_mode': mode, 'chunks': len(chunks),
            'embedding_source': config.embedding_mode if mode == 'semantic' else None}


def delete_vectors(document_id, user_id):
    try:
        from qdrant_client import models
    except ImportError:
        return
    with _LOCK:
        client = vector_client()
        selector = models.FilterSelector(filter=models.Filter(must=[
            models.FieldCondition(key='user_id', match=models.MatchValue(value=user_id)),
            models.FieldCondition(key='document_id', match=models.MatchValue(value=document_id))]))
        for collection in client.get_collections().collections:
            if collection.name.startswith('study_'):
                client.delete(collection.name, points_selector=selector, wait=True)


def semantic_search(vector, config, user_id, allowed_ids, limit):
    from qdrant_client import models
    name = 'study_' + fingerprint(config)
    with _LOCK:
        client = vector_client()
        if not client.collection_exists(name):
            return []
        result = client.query_points(name, query=vector, limit=limit, with_payload=True,
            query_filter=models.Filter(must=[
                models.FieldCondition(key='user_id', match=models.MatchValue(value=user_id)),
                models.FieldCondition(key='document_id', match=models.MatchAny(any=allowed_ids))]),
            score_threshold=float(os.getenv('RAG_MIN_SCORE', '0.55')))
        return [(str(item.id), item.score) for item in result.points]


def lexical_search(question, chunks, limit):
    # Character n-gram hashing handles Chinese without pretending to be an embedding model.
    from sklearn.feature_extraction.text import HashingVectorizer
    import re
    if not chunks:
        return []
    normalized = re.sub(r'[\s，。！？；：、（）【】“”‘’]', '', question)
    vectorizer = HashingVectorizer(analyzer='char', ngram_range=(1, 4), n_features=2**18,
                                 alternate_sign=False, norm='l2')
    query = vectorizer.transform([normalized])
    matrix = vectorizer.transform([chunk['content'] for chunk in chunks])
    scores = (matrix @ query.T).toarray().ravel()
    return [(chunks[i]['id'], float(scores[i])) for i in scores.argsort()[::-1][:limit] if scores[i] >= 0.015]


async def retrieve(question, user_id, knowledge_base_id=None, limit=5):
    config = get_config(user_id)
    with connection() as conn:
        if knowledge_base_id:
            owned(conn, 'knowledge_bases', knowledge_base_id, user_id)
        sql = ('SELECT c.*,d.original_name,l.index_mode,l.embedding_fingerprint FROM document_chunks c '
               'JOIN documents d ON d.id=c.document_id JOIN document_links l ON l.document_id=d.id WHERE c.user_id=? AND d.user_id=?')
        params = [user_id, user_id]
        if knowledge_base_id:
            sql += ' AND l.knowledge_base_id=?'
            params.append(knowledge_base_id)
        chunks = rows(conn.execute(sql + ' ORDER BY d.created_at DESC,c.ordinal LIMIT 12000', params).fetchall())
    by_id = {chunk['id']: chunk for chunk in chunks}
    fp = fingerprint(config)
    eligible = [chunk for chunk in chunks if chunk['index_mode'] == 'semantic' and chunk['embedding_fingerprint'] == fp]
    mode, warning = 'keyword', None
    # Historical expansions are intentionally keyword-only. When included in a
    # scope, search all its SQL chunks locally instead of requiring model/Qdrant.
    historical = any(chunk['original_name'].startswith('[旧版扩展·含重复待整理]') for chunk in chunks)
    if config.embedding_mode != 'keyword' and eligible and not historical:
        vectors = await embeddings([question], config)
        try:
            found = await asyncio.to_thread(semantic_search, vectors[0], config, user_id,
                                           sorted({c['document_id'] for c in eligible}), limit)
        except Exception:
            fail(503, 'VECTOR_STORE_UNAVAILABLE', '语义检索暂不可用，请稍后重试')
        mode = 'semantic'
        if not found:
            found = await asyncio.to_thread(lexical_search, question, chunks, limit)
            mode = 'keyword_fallback'
            warning = '语义检索未达到相关度阈值，已自动使用关键词检索复核'
        if len(eligible) != len(chunks):
            # Keyword-only defaults must not disappear when older semantic
            # documents coexist. SQL-scoped lexical hits retain real provenance.
            lexical_only = [chunk for chunk in chunks if chunk['index_mode'] == 'keyword']
            lexical_found = await asyncio.to_thread(lexical_search, question, lexical_only, limit)
            if lexical_found:
                found = (lexical_found + [hit for hit in found if hit[0] not in {x[0] for x in lexical_found}])[:limit]
                mode = 'hybrid_keyword'
                warning = (warning + '；' if warning else '') + '包含明确标注的本地关键词检索资料'
            else:
                warning = (warning + '；' if warning else '') + '部分资料尚未按当前模型建立语义索引，关键词复核无匹配'
    else:
        found = await asyncio.to_thread(lexical_search, question, chunks, limit)
        if config.embedding_mode != 'keyword':
            warning = ('范围内含旧版扩展资料，本次对该范围执行本地关键词检索，不调用语义模型' if historical else '资料尚未建立语义索引，本次明确降级为关键词检索')
    citations = []
    for chunk_id, score in found:
        if chunk_id in by_id:  # Ownership and KB membership are rechecked against SQL.
            chunk = by_id[chunk_id]
            citations.append({'document_id': chunk['document_id'], 'chunk_id': chunk_id,
                'name': chunk['original_name'], 'page': chunk['page'], 'content': chunk['content'], 'score': round(score, 6)})
    return citations, mode, warning
