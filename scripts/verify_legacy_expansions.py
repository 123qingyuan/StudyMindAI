"""Real HTTP registration and isolation acceptance, production MySQL; no credentials printed."""
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.legacy_content import manifest, backfill_user, provision, VERSION, sha
from app.default_content import _copy_default_content
from app.document.parser import Page,chunks


def main():
    m=manifest(); accounts=[]; report={'health':None,'accounts':[]}
    client=httpx.Client(base_url='http://127.0.0.1:8765',timeout=180,trust_env=False)
    try:
        r=client.get('/api/health');r.raise_for_status();report['health']=r.json()
        for n in range(2):
            start=time.monotonic()
            r=client.post('/api/auth/register',json={'email':f'legacy-accept-{secrets.token_hex(10)}@example.test','password':secrets.token_urlsafe(32),'display_name':'旧版资料验收临时账户'})
            assert r.status_code==201, (r.status_code,r.text)
            data=r.json();uid=data['user']['id'];headers={'Authorization':'Bearer '+data['access_token']}
            accounts.append({'uid':uid,'headers':headers})
            docs=client.get('/api/documents',headers=headers).json()
            longs=[d for d in docs if d['original_name'].startswith(m['label'])]
            assert len(docs)==31 and len(longs)==7
            verified=[]
            for item in m['items']:
                d=next(d for d in longs if d['original_name']==item['original_name'])
                r=client.get('/api/documents/'+d['id'],headers=headers);r.raise_for_status();full=r.json()
                assert sha(full['content'])==item['sha256'] and len(full['content'])==item['chars']
                actual=[{k:c[k] for k in ('page','ordinal','content')} for c in full['chunks']]
                assert actual==list(chunks([Page(1,item['text'],'text')]))
                assert full['link']['index_mode']=='keyword'
                download=client.get('/api/documents/'+d['id']+'/download',headers=headers)
                assert hashlib.sha256(download.content).hexdigest()==item['sha256']
                search=client.post('/api/knowledge/search',headers=headers,json={'question':m['label'],'knowledge_base_id':full['link']['knowledge_base_id']})
                assert search.status_code==200,(search.status_code,search.text)
                search=search.json();assert search['retrieval_mode']=='keyword' and any(x['document_id']==d['id'] for x in search['citations'])
                verified.append({'domain':item['domain'],'chars':len(full['content']),'chunks':len(actual),'sha256':sha(full['content']),'keyword_match':True})
            with core.db() as c:
                counts=c.execute('SELECT subject,COUNT(*) n FROM questions WHERE user_id=? GROUP BY subject',(uid,)).fetchall()
                assert len(counts)==28 and all(x['n']==100 for x in counts)
                assert c.execute("SELECT COUNT(*) n FROM documents WHERE user_id=? AND original_name LIKE '[内置] %'",(uid,)).fetchone()['n']==24
            accounts[-1]['documents']=longs
            report['accounts'].append({'registration_status':201,'registration_and_readback_seconds':round(time.monotonic()-start,3),'base_documents':24,'questions':2800,'categories':28,'long_documents':verified})
        a,b=accounts
        # Real private sentinel: B cannot enumerate, read, move, delete or search A's private material.
        sentinel='PRIVATE_SENTINEL_'+secrets.token_hex(16)
        r=client.post('/api/documents/upload',headers=a['headers'],files={'file':('private-sentinel.md',sentinel.encode(),'text/markdown')});r.raise_for_status();did=r.json()['id']
        bdocs=client.get('/api/documents',headers=b['headers']).json();assert did not in {d['id'] for d in bdocs}
        outcomes={}
        for verb,path,payload in [('GET','/api/documents/'+did,None),('GET','/api/documents/'+did+'/download',None),('PATCH','/api/documents/'+did,{'knowledge_base_id':None,'folder':'forbidden'}),('DELETE','/api/documents/'+did,None)]:
            response=client.request(verb,path,headers=b['headers'],json=payload)
            assert response.status_code==404,(verb,response.status_code)
            outcomes[verb+path.replace(did,'<private>')]=response.status_code
        kb=client.get('/api/knowledge-bases',headers=a['headers']).json()[0]['id']
        response=client.post('/api/knowledge/search',headers=b['headers'],json={'question':sentinel,'knowledge_base_id':kb});assert response.status_code==404
        response=client.post('/api/knowledge/search',headers=b['headers'],json={'question':sentinel});response.raise_for_status();assert all(d['document_id']!=did and sentinel not in d['content'] for d in response.json()['citations'])
        report['isolation']={'list_private_absent':True,'scoped_search_denied':True,'search_private_absent':True,'direct_access':outcomes}
        # Deletion via database avoids opening the vector-store just for keyword content.
        deleted=a['documents'][0]['id']
        with core.db() as c:
            c.execute('DELETE FROM documents WHERE id=? AND user_id=?',(deleted,a['uid']))
        assert backfill_user(a['uid'])['status']=='already_complete'
        assert _copy_default_content(a['uid'])['status']=='already_complete'
        assert client.get('/api/documents/'+deleted,headers=a['headers']).status_code==404
        assert len([d for d in client.get('/api/documents',headers=b['headers']).json() if d['original_name'].startswith(m['label'])])==7
        report['deletion_respected']=True
        # Failure after full provisioning proves both registration rows and files roll back.
        rollback_id=core.uid();email=f'rollback-{secrets.token_hex(10)}@example.test'
        with core.db() as c:
            initial_files={p.name for p in core.UPLOAD_DIR.glob(rollback_id+'_*')}
        try:
            with core.db() as c:
                ts=core.now_iso()
                c.execute('INSERT INTO users(id,email,password_hash,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(rollback_id,email,core.DUMMY_HASH,'rollback','Asia/Shanghai',ts,ts))
                _copy_default_content(rollback_id,c)
                provision(rollback_id,c)
                raise RuntimeError('intentional rollback test')
        except RuntimeError as exc:
            assert str(exc)=='intentional rollback test'
        with core.db() as c:
            assert not c.execute('SELECT id FROM users WHERE id=?',(rollback_id,)).fetchone()
            assert not c.execute('SELECT user_id FROM builtin_expansion_runs WHERE user_id=?',(rollback_id,)).fetchone()
        assert {p.name for p in core.UPLOAD_DIR.glob(rollback_id+'_*')}==initial_files
        # Same identifier can be retried successfully after failure; then dispose it.
        with core.db() as c:
            ts=core.now_iso();c.execute('INSERT INTO users(id,email,password_hash,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(rollback_id,email,core.DUMMY_HASH,'rollback','Asia/Shanghai',ts,ts))
            _copy_default_content(rollback_id,c);provision(rollback_id,c)
        with core.db() as c:
            assert c.execute("SELECT status FROM builtin_expansion_runs WHERE user_id=?",(rollback_id,)).fetchone()['status']=='completed'
            c.execute('DELETE FROM users WHERE id=?',(rollback_id,))
        for p in core.UPLOAD_DIR.glob(rollback_id+'_*'):p.unlink()
        report['rollback']={'user_absent':True,'marker_absent':True,'files_restored':True,'retry_successful':True,'dialect':'mysql'}
    finally:
        for a in accounts:
            with core.db() as c:c.execute('DELETE FROM users WHERE id=?',(a['uid'],))
            for p in core.UPLOAD_DIR.glob(a['uid']+'_*'):p.unlink()
            with core.db() as c:assert not c.execute('SELECT id FROM users WHERE id=?',(a['uid'],)).fetchone()
            assert client.get('/api/auth/me',headers=a['headers']).status_code==401
        report['temporary_accounts_removed']=len(accounts)
        client.close()
    out=ROOT/'data'/'builtin'/VERSION/'api-acceptance-report.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
