"""Explicit all-account historical-content backfill, sanitized evidence."""
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import core
from app.legacy_content import backfill_user, manifest, VERSION, sha


def snapshot(conn):
    result = {}
    for table in ('questions','question_records','notes'):
        rows = conn.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
        result[table] = {'rows':len(rows), 'sha256':sha(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str))}
    result['base_documents'] = conn.execute("SELECT COUNT(*) n FROM documents WHERE original_name LIKE '[内置] %'").fetchone()['n']
    return result


def main():
    # Required startup migration, never inside a user registration/provision transaction.
    core.init_db()
    with core.db() as c:
        users = c.execute('SELECT id FROM users ORDER BY id').fetchall()
        before = snapshot(c)
        original_ids = {r['id'] for r in c.execute('SELECT id FROM documents').fetchall()}
        suspect = c.execute("SELECT COUNT(*) n FROM documents WHERE original_name LIKE '%五万字补全%'").fetchone()['n']
        user_content = {r['id']:sha(r['content'] or '') for r in c.execute('SELECT id,content FROM documents').fetchall()}
    reports = []
    evidence_dir=ROOT/'data'/'builtin'/VERSION
    run_id=core.now_iso().replace(':','').replace('.','')
    (evidence_dir/f'backfill-baseline-{run_id}.json').write_text(json.dumps({'before':before,'users':len(users),'existing_documents':len(original_ids)},ensure_ascii=False,indent=2),encoding='utf-8')
    for n, user in enumerate(users,1):
        try:
            result = backfill_user(user['id'])
            result['account'] = n
            reports.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
        except Exception as exc:
            print(json.dumps({'account':n,'error_type':type(exc).__name__,'error':str(exc)[:400]},ensure_ascii=False),flush=True)
            raise
    with core.db() as c:
        after = snapshot(c)
        if before != after:
            print(json.dumps({'before':before,'after':after},ensure_ascii=False),flush=True)
        assert before == after, 'unrelated records changed'
        current = {r['id']:sha(r['content'] or '') for r in c.execute('SELECT id,content FROM documents').fetchall()}
        assert original_ids <= set(current), 'existing document deleted'
        controlled = {r['document_id'] for r in c.execute('SELECT document_id FROM builtin_expansion_sources WHERE version=?',(VERSION,)).fetchall()}
        changes = [did for did in original_ids if current[did] != user_content[did]]
        assert set(changes) <= controlled, 'uncontrolled document changed'
        verified = []
        for n,u in enumerate(users,1):
            docs = c.execute('SELECT s.item_key,s.content_hash,d.content,d.storage_key,d.id,l.index_mode FROM builtin_expansion_sources s JOIN documents d ON d.id=s.document_id JOIN document_links l ON l.document_id=d.id WHERE s.user_id=? AND s.version=?',(u['id'],VERSION)).fetchall()
            assert len(docs)==7
            for d in docs:
                assert sha(d['content'])==d['content_hash']
                assert hashlib.sha256((core.UPLOAD_DIR/d['storage_key']).read_bytes()).hexdigest()==d['content_hash']
                assert d['index_mode']=='keyword'
            verified.append({'account':n,'long_documents':len(docs)})
    repeats = [backfill_user(u['id'])['status'] for u in users]
    assert set(repeats)=={'already_complete'}
    report={'version':VERSION,'accounts':len(users),'results':reports,'readback':verified,'before':before,'after':after,
            'all_existing_documents_preserved':True,'relabeled_existing_documents':len(changes),'excluded_topup_documents_retained_not_distributed':suspect,
            'repeat_noop_accounts':len(repeats),'manifest':[{k:v for k,v in i.items() if k!='text'} for i in manifest()['items']]}
    out=ROOT/'data'/'builtin'/'legacy-expansion-v1'/'backfill-report.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(out),'accounts':len(users),'unchanged':before==after},ensure_ascii=False))

if __name__=='__main__':main()
