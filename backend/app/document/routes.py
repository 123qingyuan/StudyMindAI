"""Document upload, parsing, indexing, knowledge bases, notes and RAG."""
from __future__ import annotations
import asyncio
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import Field
from .. import core
from .parser import ALLOWED, MAX_BYTES, DocumentError, chunks, extract, safe_display_name, validate_signature
from ..ai.common import StrictModel, connection, dumps, fail, owned, rows, update_owned, non_null_updates
from ..ai.service import complete_for, parse_json
from ..rag.store import delete_vectors, index_document, retrieve

router = APIRouter()


class KBIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=1000)


class KBPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class NoteIn(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=200000)


class NotePatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=200000)


class AnalyzeIn(StrictModel):
    action: str = Field(pattern='^(summary|notes|keywords|knowledge_points|mindmap|questions)$')


class QueryIn(StrictModel):
    question: str = Field(min_length=1, max_length=10000)
    knowledge_base_id: str | None = None


class LinkIn(StrictModel):
    knowledge_base_id: str | None = None
    folder: str = Field(default='', max_length=160)


async def save_upload(file: UploadFile, user_id: str):
    name = safe_display_name(file.filename)
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED:
        fail(415, 'UNSUPPORTED_FILE', '支持 TXT、Markdown、CSV、JSON、DOCX、PDF 和常见图片')
    directory = Path(core.UPLOAD_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    document_id, storage = core.uid(), None
    temp = directory / f'.upload-{document_id}.part'
    size = 0
    try:
        with temp.open('wb') as output:
            while True:
                block = await file.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > MAX_BYTES:
                    fail(413, 'FILE_TOO_LARGE', '文件不能超过 20MB')
                output.write(block)
        validate_signature(temp, extension)
        pages = await asyncio.to_thread(extract, temp, extension)
        storage = f'{user_id}_{document_id}{extension}'
        final = directory / storage
        temp.replace(final)
        ts = core.now_iso()
        text = '\n\n'.join(page.text for page in pages)
        with connection() as conn:
            conn.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (document_id, user_id, name, storage, file.content_type or mimetypes.guess_type(name)[0] or 'application/octet-stream', size, 'ready', text, None, ts, ts))
            conn.execute('INSERT INTO document_links(document_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?)',
                (document_id, '', '+'.join(sorted({page.method for page in pages})), len(pages), 'not_indexed'))
            for item in chunks(pages):
                conn.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)',
                    (core.uid(), document_id, user_id, item['page'], item['ordinal'], item['content']))
            return dict(conn.execute('SELECT id,original_name,mime_type,size_bytes,status,summary,created_at,updated_at FROM documents WHERE id=?', (document_id,)).fetchone())
    except DocumentError as exc:
        fail(exc.status, exc.code, exc.message)
    except OSError:
        fail(507, 'STORAGE_ERROR', '文件存储失败')
    finally:
        temp.unlink(missing_ok=True)


@router.post('/documents/upload')
async def upload_document(file: UploadFile = File(...), user=Depends(core.current_user)):
    return await save_upload(file, user['id'])


@router.get('/documents')
def list_documents(user=Depends(core.current_user)):
    with connection() as conn:
        return rows(conn.execute('SELECT d.id,d.original_name,d.mime_type,d.size_bytes,d.status,d.summary,d.created_at,d.updated_at,l.folder,l.extraction_method,l.page_count,l.index_mode FROM documents d JOIN document_links l ON l.document_id=d.id WHERE d.user_id=? ORDER BY d.created_at DESC', (user['id'],)).fetchall())


@router.get('/documents/{document_id}')
def get_document(document_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        doc = owned(conn, 'documents', document_id, user['id'])
        link = conn.execute('SELECT folder,extraction_method,page_count,index_mode,embedding_fingerprint,error_code,knowledge_base_id FROM document_links WHERE document_id=?', (document_id,)).fetchone()
        doc.pop('storage_key', None)
        doc['link'] = dict(link) if link else None
        doc['chunks'] = rows(conn.execute('SELECT id,page,ordinal,content FROM document_chunks WHERE document_id=? ORDER BY ordinal', (document_id,)).fetchall())
        return doc


@router.get('/documents/{document_id}/download')
def download_document(document_id: str, user=Depends(core.current_user)):
    # Main app may replace this with FileResponse; this endpoint returns no path outside ownership.
    from fastapi.responses import FileResponse
    with connection() as conn:
        doc = owned(conn, 'documents', document_id, user['id'])
    path = Path(core.UPLOAD_DIR) / doc['storage_key']
    if not path.is_file():
        fail(404, 'FILE_MISSING', '文件已不存在')
    return FileResponse(path, media_type=doc['mime_type'], filename=doc['original_name'])


@router.patch('/documents/{document_id}')
def patch_document(document_id: str, payload: LinkIn, user=Depends(core.current_user)):
    return link_document(document_id, payload, user)


@router.delete('/documents/{document_id}')
def delete_document(document_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        doc = owned(conn, 'documents', document_id, user['id'])
    try:
        delete_vectors(document_id, user['id'])
    except Exception:
        fail(503, 'VECTOR_DELETE_FAILED', '向量索引删除失败，文档已保留，请重试')
    try:
        (Path(core.UPLOAD_DIR) / doc['storage_key']).unlink(missing_ok=True)
    except OSError:
        fail(507, 'FILE_DELETE_FAILED', '原文件删除失败，数据库记录已保留，请重试')
    with connection() as conn:
        conn.execute('DELETE FROM documents WHERE id=? AND user_id=?', (document_id, user['id']))
    return {'ok': True}


@router.post('/documents/{document_id}/index')
async def index(document_id: str, user=Depends(core.current_user)):
    return await index_document(document_id, user['id'])


@router.post('/documents/{document_id}/summarize')
async def summarize(document_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        doc = owned(conn, 'documents', document_id, user['id'])
    result = await complete_for(user['id'], 'document_summary', [
        {'role': 'system', 'content': '只根据资料生成摘要。不得添加资料中没有的事实。'},
        {'role': 'user', 'content': doc['content']}])
    with connection() as conn:
        conn.execute('UPDATE documents SET summary=?,updated_at=? WHERE id=? AND user_id=?', (result, core.now_iso(), document_id, user['id']))
        conn.execute('INSERT INTO document_actions(id,document_id,user_id,action,result_json,created_at) VALUES(?,?,?,?,?,?)',
                     (core.uid(), document_id, user['id'], 'summary', dumps({'summary': result}), core.now_iso()))
    return {'summary': result, 'source': 'ai'}


@router.post('/documents/{document_id}/analyze', include_in_schema=False)
async def analyze(document_id: str, payload: AnalyzeIn, user=Depends(core.current_user)):
    fail(410, 'FEATURE_REMOVED', '生成式文档分析功能已移除')
    with connection() as conn:
        doc = owned(conn, 'documents', document_id, user['id'])
    instructions = {
        'summary': '输出 JSON {"summary":"..."}', 'notes': '输出 JSON {"title":"...","content":"..."}',
        'keywords': '输出 JSON {"keywords":["..."]}', 'knowledge_points': '输出 JSON {"points":[{"title":"...","description":"..."}]}',
        'mindmap': '输出 JSON {"root":"...","children":[{"title":"...","children":[]}]}',
        'questions': '输出 JSON {"questions":[{"stem":"...","answer":"...","explanation":"..."}]}',
    }
    raw = await complete_for(user['id'], 'document_' + payload.action,
        [{'role': 'system', 'content': '你是学习资料分析器。严格只输出 JSON，不补造原文外事实。' + instructions[payload.action]},
         {'role': 'user', 'content': doc['content']}], json_mode=True)
    result = parse_json(raw)
    if not isinstance(result, dict): fail(502, 'INVALID_DOCUMENT_ANALYSIS', '模型返回的分析格式无效，未保存')
    field = {'summary':'summary','notes':'content','keywords':'keywords','knowledge_points':'points','mindmap':'children','questions':'questions'}[payload.action]
    expected = str if payload.action in {'summary','notes'} else list
    if not isinstance(result.get(field), expected): fail(502, 'INVALID_DOCUMENT_ANALYSIS', '模型缺少必要分析字段，未保存')
    if payload.action == 'knowledge_points' and any(not isinstance(p, dict) or not isinstance(p.get('title'), str) or not isinstance(p.get('description'), str) for p in result['points']):
        fail(502, 'INVALID_DOCUMENT_ANALYSIS', '模型返回的知识点格式无效，未保存')
    with connection() as conn:
        conn.execute('INSERT INTO document_actions(id,document_id,user_id,action,result_json,created_at) VALUES(?,?,?,?,?,?)',
                     (core.uid(), document_id, user['id'], payload.action, dumps(result), core.now_iso()))
        if payload.action == 'summary':
            conn.execute('UPDATE documents SET summary=?,updated_at=? WHERE id=? AND user_id=?', (result.get('summary', ''), core.now_iso(), document_id, user['id']))
        if payload.action == 'notes':
            timestamp = core.now_iso()
            note_id = core.uid()
            conn.execute('INSERT INTO notes(id,user_id,title,content,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)', (note_id, user['id'], str(result.get('title') or doc['original_name'])[:160], result['content'], 'ai_document', timestamp, timestamp))
            result['saved_note_id'] = note_id
        if payload.action == 'knowledge_points':
            for point in result.get('points', []):
                conn.execute('INSERT INTO knowledge_points(id,user_id,title,description,source_document_id,created_at) VALUES(?,?,?,?,?,?)',
                    (core.uid(), user['id'], str(point.get('title', ''))[:200], str(point.get('description', '')), document_id, core.now_iso()))
    return {'action': payload.action, 'result': result, 'source': 'ai'}


@router.get('/knowledge-bases')
def list_kbs(user=Depends(core.current_user)):
    with connection() as conn:
        return rows(conn.execute("""SELECT k.*,
            COUNT(DISTINCT l.document_id) AS document_count,
            COALESCE(SUM(CASE WHEN l.index_mode='semantic' THEN 1 ELSE 0 END),0) AS indexed_count,
            COUNT(DISTINCT c.id) AS chunk_count
            FROM knowledge_bases k
            LEFT JOIN document_links l ON l.knowledge_base_id=k.id
            LEFT JOIN document_chunks c ON c.document_id=l.document_id
            WHERE k.user_id=? GROUP BY k.id ORDER BY k.updated_at DESC""", (user['id'],)).fetchall())


@router.get('/knowledge-bases/{knowledge_base_id}')
def get_kb(knowledge_base_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        item = owned(conn, 'knowledge_bases', knowledge_base_id, user['id'])
        item['documents'] = rows(conn.execute("""SELECT d.id,d.original_name,d.mime_type,d.size_bytes,d.status,d.summary,d.created_at,
            l.folder,l.extraction_method,l.page_count,l.index_mode
            FROM documents d JOIN document_links l ON l.document_id=d.id
            WHERE d.user_id=? AND l.knowledge_base_id=? ORDER BY d.created_at DESC""", (user['id'], knowledge_base_id)).fetchall())
        item['knowledge_points'] = rows(conn.execute('SELECT id,title,description,source_document_id,created_at FROM knowledge_points WHERE user_id=? AND source_document_id IN (SELECT document_id FROM document_links WHERE knowledge_base_id=?) ORDER BY created_at DESC LIMIT 200', (user['id'], knowledge_base_id)).fetchall())
        return item


@router.get('/knowledge-points')
def list_knowledge_points(knowledge_base_id: str | None = None, user=Depends(core.current_user)):
    with connection() as conn:
        if knowledge_base_id:
            owned(conn, 'knowledge_bases', knowledge_base_id, user['id'])
            found = conn.execute('SELECT id,title,description,source_document_id,created_at FROM knowledge_points WHERE user_id=? AND source_document_id IN (SELECT document_id FROM document_links WHERE knowledge_base_id=?) ORDER BY created_at DESC LIMIT 500', (user['id'], knowledge_base_id)).fetchall()
        else:
            found = conn.execute('SELECT id,title,description,source_document_id,created_at FROM knowledge_points WHERE user_id=? ORDER BY created_at DESC LIMIT 500', (user['id'],)).fetchall()
        return rows(found)


@router.post('/knowledge-bases')
def create_kb(payload: KBIn, user=Depends(core.current_user)):
    kid, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO knowledge_bases(id,user_id,name,description,created_at,updated_at) VALUES(?,?,?,?,?,?)', (kid, user['id'], payload.name, payload.description, ts, ts))
        return owned(conn, 'knowledge_bases', kid, user['id'])


@router.patch('/knowledge-bases/{knowledge_base_id}')
def patch_kb(knowledge_base_id: str, payload: KBPatch, user=Depends(core.current_user)):
    with connection() as conn:
        return update_owned(conn, 'knowledge_bases', knowledge_base_id, user['id'], non_null_updates(payload))


@router.delete('/knowledge-bases/{knowledge_base_id}')
def delete_kb(knowledge_base_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'knowledge_bases', knowledge_base_id, user['id'])
        conn.execute('UPDATE document_links SET knowledge_base_id=NULL WHERE knowledge_base_id=?', (knowledge_base_id,))
        conn.execute('DELETE FROM knowledge_bases WHERE id=? AND user_id=?', (knowledge_base_id, user['id']))
    return {'ok': True}


@router.patch('/documents/{document_id}/knowledge-base')
def link_document(document_id: str, payload: LinkIn, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'documents', document_id, user['id'])
        if payload.knowledge_base_id:
            owned(conn, 'knowledge_bases', payload.knowledge_base_id, user['id'])
        conn.execute('UPDATE document_links SET knowledge_base_id=?,folder=? WHERE document_id=?', (payload.knowledge_base_id, payload.folder, document_id))
    return {'document_id': document_id, 'knowledge_base_id': payload.knowledge_base_id, 'folder': payload.folder}


@router.get('/notes')
def list_notes(user=Depends(core.current_user)):
    with connection() as conn:
        return rows(conn.execute('SELECT * FROM notes WHERE user_id=? ORDER BY updated_at DESC', (user['id'],)).fetchall())


@router.post('/notes')
def create_note(payload: NoteIn, user=Depends(core.current_user)):
    nid, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO notes(id,user_id,title,content,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)', (nid, user['id'], payload.title, payload.content, 'manual', ts, ts))
        return owned(conn, 'notes', nid, user['id'])


@router.patch('/notes/{note_id}')
def patch_note(note_id: str, payload: NotePatch, user=Depends(core.current_user)):
    with connection() as conn:
        return update_owned(conn, 'notes', note_id, user['id'], non_null_updates(payload))


@router.delete('/notes/{note_id}')
def delete_note(note_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'notes', note_id, user['id'])
        conn.execute('DELETE FROM notes WHERE id=? AND user_id=?', (note_id, user['id']))
    return {'ok': True}


@router.post('/knowledge/query')
async def query(payload: QueryIn, user=Depends(core.current_user)):
    citations, mode, warning = await retrieve(payload.question, user['id'], payload.knowledge_base_id)
    if not citations:
        return {'answer': '当前知识库中没有找到足够的信息。请换一个更具体的关键词。',
                'citations': [], 'retrieval_mode': mode, 'warning': warning, 'source': 'no_evidence'}
    return {'answer': '', 'citations': citations, 'retrieval_mode': mode, 'warning': warning,
            'source': 'local_retrieval'}


@router.post('/knowledge/search')
async def search_knowledge(payload: QueryIn, user=Depends(core.current_user)):
    return await query(payload, user)
