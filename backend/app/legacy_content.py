"""Explicitly labelled historical expansions, static manifest only; no vectors."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from . import core
from .document.parser import Page, chunks

VERSION = 'legacy-expansion-v1'
DIRECTORY = core.ROOT / 'data' / 'builtin' / VERSION
SCHEMA = '''
CREATE TABLE IF NOT EXISTS builtin_expansion_runs (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 version TEXT NOT NULL, status TEXT NOT NULL, completed_at TEXT,
 PRIMARY KEY(user_id,version)
);
CREATE TABLE IF NOT EXISTS builtin_expansion_sources (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 version TEXT NOT NULL, item_key TEXT NOT NULL,
 document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
 content_hash TEXT NOT NULL, raw_hash TEXT NOT NULL,
 PRIMARY KEY(user_id,version,item_key)
);
'''


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def manifest():
    data = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    assert data['version'] == VERSION and len(data['items']) == 7
    assert len({i['key'] for i in data['items']}) == 7
    for item in data['items']:
        assert Path(item['file']).name == item['file']
        item['text'] = (DIRECTORY / item['file']).read_text(encoding='utf-8')
        assert sha(item['text']) == item['sha256'] and len(item['text']) == item['chars']
    return data


def provision(user_id, conn):
    if conn.engine.dialect.name == 'mysql':
        conn.execute('SELECT id FROM users WHERE id=? FOR UPDATE', (user_id,)).fetchone()
    marker = conn.execute('SELECT status FROM builtin_expansion_runs WHERE user_id=? AND version=?', (user_id, VERSION)).fetchone()
    if marker and marker['status'] == 'completed':
        return {'status': 'already_complete', 'version': VERSION}
    # Conflict update locks this account/version until its transaction commits.
    conn.execute("INSERT INTO builtin_expansion_runs(user_id,version,status) VALUES(?,?,?) ON CONFLICT(user_id,version) DO UPDATE SET status=excluded.status", (user_id, VERSION, 'running'))
    # Recheck after lock to handle an overlapping first-time run.
    existing = conn.execute('SELECT COUNT(*) AS n FROM builtin_expansion_sources WHERE user_id=? AND version=?', (user_id, VERSION)).fetchone()['n']
    if existing:
        raise RuntimeError('incomplete historical manifest requires explicit inspection')
    items = manifest()['items']
    timestamp = core.now_iso()
    # Hash-only comparison within this account; never use its private content as a source.
    candidates = conn.execute('SELECT id,content,storage_key FROM documents WHERE user_id=?', (user_id,)).fetchall()
    by_hash = {}
    for doc in candidates:
        by_hash.setdefault(sha(doc['content'] or ''), []).append(doc)
    added = reused = 0
    for item in items:
        found = by_hash.get(item['sha256'], []) + by_hash.get(item['raw_sha256'], [])
        kb = conn.execute('SELECT id FROM knowledge_bases WHERE user_id=? AND name=?', (user_id, item['domain'])).fetchone()
        kid = kb['id'] if kb else core.uid()
        if not kb:
            conn.execute('INSERT INTO knowledge_bases(id,user_id,name,description,created_at,updated_at) VALUES(?,?,?,?,?,?)', (kid, user_id, item['domain'], '独立的受控内置资料副本', timestamp, timestamp))
        # Existing exact duplicates are retained, labelled, and never propagated elsewhere.
        targets = found or [{'id': core.uid(), 'storage_key': None}]
        for doc in targets:
            did = doc['id']
            key = doc['storage_key'] or f'{user_id}_{did}.md'
            conn.write_file(Path(core.UPLOAD_DIR) / key, item['text'].encode('utf-8'))
            if found:
                conn.execute('UPDATE documents SET original_name=?,content=?,summary=?,size_bytes=?,updated_at=? WHERE id=? AND user_id=?', (item['original_name'], item['text'], item['summary'], len(item['text'].encode()), timestamp, did, user_id))
                conn.execute('DELETE FROM document_chunks WHERE document_id=? AND user_id=?', (did, user_id))
                conn.execute('UPDATE document_links SET knowledge_base_id=?,folder=?,index_mode=?,embedding_fingerprint=NULL,error_code=NULL WHERE document_id=?', (kid, '旧版扩展·含重复待整理', 'keyword', did))
                reused += 1
            else:
                conn.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (did,user_id,item['original_name'],key,'text/markdown',len(item['text'].encode()),'ready',item['text'],item['summary'],timestamp,timestamp))
                conn.execute('INSERT INTO document_links(document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?,?)', (did,kid,'旧版扩展·含重复待整理','text',1,'keyword'))
                added += 1
            for chunk in chunks([Page(1,item['text'],'text')]):
                conn.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)', (core.uid(),did,user_id,chunk['page'],chunk['ordinal'],chunk['content']))
        conn.execute('INSERT INTO builtin_expansion_sources(user_id,version,item_key,document_id,content_hash,raw_hash) VALUES(?,?,?,?,?,?)', (user_id,VERSION,item['key'],targets[0]['id'],item['sha256'],item['raw_sha256']))
    for item in items:
        saved = conn.execute('SELECT d.content,d.storage_key,l.index_mode,d.id FROM builtin_expansion_sources s JOIN documents d ON d.id=s.document_id JOIN document_links l ON l.document_id=d.id WHERE s.user_id=? AND s.version=? AND s.item_key=? AND d.user_id=?', (user_id,VERSION,item['key'],user_id)).fetchone()
        assert saved and sha(saved['content']) == item['sha256'] and saved['index_mode'] == 'keyword'
        assert hashlib.sha256((Path(core.UPLOAD_DIR)/saved['storage_key']).read_bytes()).hexdigest() == item['sha256']
        got = conn.execute('SELECT page,ordinal,content FROM document_chunks WHERE document_id=? AND user_id=? ORDER BY ordinal', (saved['id'],user_id)).fetchall()
        assert got == list(chunks([Page(1,item['text'],'text')]))
    conn.execute("UPDATE builtin_expansion_runs SET status='completed',completed_at=? WHERE user_id=? AND version=?", (timestamp,user_id,VERSION))
    return {'status': 'completed', 'version': VERSION, 'added': added, 'reused': reused, 'items': len(items)}


def backfill_user(user_id):
    with core.db() as conn:
        return provision(user_id, conn)
