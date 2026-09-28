"""Real MySQL + Qdrant + document acceptance; all generated accounts are isolated test identities."""
from pathlib import Path
import secrets
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app import core
from app.rag.store import retrieve,close_clients
import asyncio

out=[]
def check(name,response,expected=(200,201)):
    ok=response.status_code in expected
    entry={'name':name,'status':response.status_code,'ok':ok}
    if not ok: entry['error']=response.text[:400]
    out.append(entry)
    assert ok,entry
    return response.json()

with TestClient(app) as c:
    password=secrets.token_urlsafe(20)
    user=check('mysql_register',c.post('/api/auth/register',json={'email':'acceptance-'+secrets.token_hex(6)+'@example.test','password':password,'display_name':'验收临时账号'}))
    h={'Authorization':'Bearer '+user['access_token']}
    actor=user['user']['id']
    other=check('second_user',c.post('/api/auth/register',json={'email':'isolation-'+secrets.token_hex(6)+'@example.test','password':secrets.token_urlsafe(20),'display_name':'隔离测试'}))
    hb={'Authorization':'Bearer '+other['access_token']}
    check('identity',c.get('/api/auth/me',headers=h))
    kb=check('knowledge_base',c.post('/api/knowledge-bases',headers=h,json={'name':'数据库教材'}))
    doc=check('upload_utf8',c.post('/api/documents/upload',headers=h,files={'file':('数据库教材.txt','数据库主键用于唯一标识一条记录。主键不能重复，不能为空。外键用于建立两个表之间的关联。'.encode('utf-8'),'text/plain')}))
    did=doc['id']
    detail=check('document_readback',c.get('/api/documents/'+did,headers=h));assert '主键' in detail['content']
    check('document_isolation',c.get('/api/documents/'+did,headers=hb),expected=(404,))
    check('knowledge_association',c.patch('/api/documents/'+did+'/knowledge-base',headers=h,json={'knowledge_base_id':kb['id'],'folder':'课程'}))
    index=check('semantic_index',c.post('/api/documents/'+did+'/index',headers=h));assert index['retrieval_mode']=='semantic',index
    cites,mode,warning=asyncio.run(retrieve('数据库主键是什么？',actor,kb['id']))
    assert cites and mode=='semantic',(cites,mode,warning)
    out.append({'name':'semantic_retrieval','ok':True,'mode':mode,'citations':len(cites),'score':cites[0]['score']})
    leaked,_,_=asyncio.run(retrieve('数据库主键是什么？',other['user']['id']))
    assert not leaked
    rag=check('rag_with_configured_model',c.post('/api/knowledge/query',headers=h,json={'question':'数据库主键是什么？'}))
    assert rag['citations'] and rag['source']=='ai',rag
    check('bad_pdf_rejected',c.post('/api/documents/upload',headers=h,files={'file':('bad.pdf',b'not-a-pdf','application/pdf')}),expected=(415,))
    task=check('task',c.post('/api/tasks',headers=h,json={'title':'验收任务','tags':['SQL']}))
    check('task_complete',c.post('/api/tasks/'+task['id']+'/complete',headers=h))
    check('record',c.post('/api/study-records',headers=h,json={'subject':'数据库','minutes':25}))
    summary=check('dashboard',c.get('/api/dashboard/summary',headers=h));assert summary['study_minutes']==25 and summary['task_done']==1
    check('report_without_model',c.post('/api/reports',headers=h,json={'period':'daily'}))
    check('document_delete',c.delete('/api/documents/'+did,headers=h))
    assert not asyncio.run(retrieve('数据库主键是什么？',actor))[0]
    check('logout',c.post('/api/auth/logout',headers=h))
    check('revoked_token',c.get('/api/auth/me',headers=h),expected=(401,))
    # Remove only the accounts generated above. All dependent test data cascades.
    with core.db() as conn:
        # The acceptance account owns generated report rows; remove explicit
        # children where an old installation lacked ON DELETE CASCADE.
        conn.execute('DELETE FROM report_metadata WHERE report_id IN (SELECT id FROM ai_reports WHERE user_id=?)',(actor,))
        conn.execute('DELETE FROM ai_reports WHERE user_id=?',(actor,))
        conn.execute('DELETE FROM users WHERE id=?',(actor,))
        conn.execute('DELETE FROM users WHERE id=?',(other['user']['id'],))
close_clients()
root=Path(__file__).resolve().parents[1]
(root/'data'/'api-acceptance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
