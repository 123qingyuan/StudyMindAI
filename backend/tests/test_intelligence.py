"""Local-only API tests: removed generators, manual bank, local reports and retrieval."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import core,intelligence
from app.database import Database

@pytest.fixture()
def env(tmp_path,monkeypatch):
    database=Database('sqlite:///'+(tmp_path/'test.sqlite3').as_posix());monkeypatch.setattr(core,'_database',database);monkeypatch.setattr(core,'DATA_DIR',tmp_path);monkeypatch.setattr(core,'UPLOAD_DIR',tmp_path/'uploads');core.init_db()
    from app.learning import router as learning
    app=FastAPI();app.include_router(core.router);app.include_router(learning);app.include_router(intelligence.router)
    with TestClient(app) as c:
        hs=[]
        for name in ['alpha','beta']:
            r=c.post('/api/auth/register',json={'email':name+'@example.test','password':'LocalTest123!','display_name':name});assert r.status_code==201,r.text;hs.append({'Authorization':'Bearer '+r.json()['access_token']})
        yield c,hs[0],hs[1]
    database.engine.dispose()

def test_removed_generation_routes(env):
    c,a,_=env
    assert c.post('/api/conversations',headers=a,json={}).status_code==200
    assert c.get('/api/settings/ai',headers=a).status_code==200
    assert c.post('/api/questions/generate',headers=a,json={'subject':'Python','type':'单选题','difficulty':'简单','count':5}).status_code in {404,405}
    assert c.post('/api/study-plans/generate',headers=a,json={'title':'x','goal':'x','start_date':'2026-10-01','end_date':'2026-10-02','daily_minutes':30}).status_code in {404,405}
    assert c.post('/api/agent/tasks',headers=a,json={'goal':'x'}).status_code==404

def test_manual_objective_question(env):
    c,a,b=env
    q=c.post('/api/questions/manual',headers=a,json={'subject':'Python','type':'单选题','difficulty':'简单','stem':'len([1,2]) 的结果是？','options':['1','2','3'],'answer':'2','explanation':'列表有两个元素。','knowledge_points':['列表']});assert q.status_code==200,q.text
    qid=q.json()['id'];assert c.post(f'/api/questions/{qid}/answer',headers=b,json={'answer':'2'}).status_code==404
    r=c.post(f'/api/questions/{qid}/answer',headers=a,json={'answer':'2'});assert r.status_code==200 and r.json()['correct'] is True and r.json()['grading_method']=='objective_exact_rule'

def test_subjective_self_review(env):
    c,a,_=env
    q=c.post('/api/questions/manual',headers=a,json={'subject':'网络','type':'简答题','difficulty':'中等','stem':'解释 TCP 三次握手。','options':[],'answer':'同步序号并确认双向通信能力。','explanation':'对照关键点订正。','knowledge_points':['TCP']});assert q.status_code==200,q.text
    r=c.post(f"/api/questions/{q.json()['id']}/answer",headers=a,json={'answer':'我的回答'});assert r.status_code==200 and r.json()['grading_method']=='self_review' and r.json()['correct'] is None

def test_report_is_database_summary_and_scoped(env):
    c,a,b=env
    r=c.post('/api/reports',headers=a,json={'period':'weekly'});assert r.status_code==200,r.text
    data=r.json();assert data['source']=='data_summary' and '数据库' in data['content'];assert c.get('/api/reports',headers=b).json()==[]

def test_local_search_no_evidence(env):
    c,a,_=env
    # Registration now includes built-in sources; use a genuinely empty KB to
    # exercise the no-evidence branch instead of assuming a new account is empty.
    empty=c.post('/api/knowledge-bases',headers=a,json={'name':'无资料验收库'})
    assert empty.status_code==200
    r=c.post('/api/knowledge/search',headers=a,json={'question':'不存在的内容','knowledge_base_id':empty.json()['id']});assert r.status_code==200,r.text
    assert r.json()['source']=='no_evidence' and r.json()['citations']==[]
