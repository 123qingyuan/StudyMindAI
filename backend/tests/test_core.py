"""Core acceptance tests use a throwaway database, never user data."""
import json
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import core
from app.database import Database
from app.learning import router as learning

@pytest.fixture()
def client(tmp_path,monkeypatch):
    database=Database('sqlite:///'+(tmp_path/'test.sqlite3').as_posix())
    monkeypatch.setattr(core,'_database',database)
    monkeypatch.setattr(core,'DATA_DIR',tmp_path)
    monkeypatch.setattr(core,'UPLOAD_DIR',tmp_path/'uploads')
    core.init_db()
    # Lower Argon2 work factor only in isolated tests under memory pressure.
    # The production hasher remains 64 MiB / time_cost=3.
    from argon2 import PasswordHasher
    hasher=PasswordHasher(time_cost=1,memory_cost=8192,parallelism=1)
    monkeypatch.setattr(core,'PASSWORD',hasher)
    monkeypatch.setattr(core,'DUMMY_HASH',hasher.hash(secrets.token_urlsafe(20)))
    app=FastAPI();app.include_router(core.router);app.include_router(learning)
    with TestClient(app) as c: yield c
    database.engine.dispose()

def account(c,name='user'):
    password=secrets.token_urlsafe(16)
    result=c.post('/api/auth/register',json={'email':name+'@example.test','password':password,'display_name':name})
    assert result.status_code==201,result.text
    data=result.json();return data, {'Authorization':'Bearer '+data['access_token']},password

def test_auth_standard_jwt_and_logout(client):
    user,h,pw=account(client)
    assert len(user['access_token'].split('.'))==3
    assert client.get('/api/auth/me',headers=h).json()['display_name']=='user'
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'email':'user@example.test','password':'wrongwrong'}).status_code==401
    logged=client.post('/api/auth/login',json={'email':'user@example.test','password':pw})
    assert logged.status_code==200
    assert client.post('/api/auth/logout',headers=h).status_code==200
    assert client.get('/api/auth/me',headers=h).status_code==401
    assert 'password_hash' not in user['user']

def test_task_crud_isolation_and_validation(client):
    u,a,_=account(client,'a');v,b,_=account(client,'b')
    r=client.post('/api/tasks',headers=a,json={'title':'数据库复习','tags':['SQL','索引'],'due_date':'2020-01-01'})
    assert r.status_code==201,r.text
    t=r.json();assert t['overdue'];assert t['tags']==['SQL','索引']
    assert client.get('/api/tasks',headers=b).json()==[]
    for method in ['get','delete']:
        assert getattr(client,method)('/api/tasks/'+t['id'],headers=b).status_code==404
    assert client.patch('/api/tasks/'+t['id'],headers=b,json={'title':'盗取'}).status_code==404
    assert client.patch('/api/tasks/'+t['id'],headers=a,json={'status':'invalid'}).status_code==422
    assert client.patch('/api/tasks/'+t['id'],headers=a,json={'due_date':'not-date'}).status_code==422
    done=client.post('/api/tasks/'+t['id']+'/complete',headers=a).json();assert done['status']=='done' and not done['overdue']
    reopened=client.patch('/api/tasks/'+t['id'],headers=a,json={'status':'doing','due_date':None}).json()
    assert reopened['completed_at'] is None
    assert client.delete('/api/tasks/'+t['id'],headers=a).status_code==200
    assert client.get('/api/tasks',headers=a).json()==[]

def test_courses_exams_update_and_owner(client):
    _,a,_=account(client,'a');_,b,_=account(client,'b')
    course={'name':'数据库','weekday':1,'start_time':'09:00','end_time':'10:00'}
    c=client.post('/api/courses',headers=a,json=course).json()
    assert 'id' in c,c
    assert client.patch('/api/courses/'+c['id'],headers=a,json=course|{'teacher':'张老师'}).json()['teacher']=='张老师'
    assert client.delete('/api/courses/'+c['id'],headers=b).status_code==404
    assert client.post('/api/courses',headers=a,json=course|{'end_time':'08:00'}).status_code==422
    e=client.post('/api/exams',headers=a,json={'subject':'数据库','exam_date':'2027-01-01'}).json()
    assert client.get('/api/exams',headers=b).json()==[]
    assert client.delete('/api/exams/'+e['id'],headers=b).status_code==404
    assert client.post('/api/exams',headers=a,json={'subject':'数学','exam_date':'bad'}).status_code==422

def test_plan_publish_idempotent(client):
    _,a,_=account(client,'a');_,b,_=account(client,'b')
    r=client.post('/api/study-plans',headers=a,json={'title':'复习','goal':'数据库','start_date':'2026-09-25','end_date':'2026-09-27','daily_minutes':60})
    assert r.status_code==201,r.text
    p=r.json();assert len(p['items'])==3
    assert client.post('/api/study-plans/'+p['id']+'/publish',headers=b).status_code==404
    item=p['items'][0]
    r=client.patch(f"/api/study-plans/{p['id']}/items/{item['id']}",headers=a,json={'title':'主键外键','estimated_minutes':30})
    assert r.status_code==200,r.text
    assert client.post('/api/study-plans/'+p['id']+'/publish',headers=a).status_code==200
    assert client.post('/api/study-plans/'+p['id']+'/publish',headers=a).status_code==200
    assert len(client.get('/api/tasks',headers=a).json())==3

def test_record_stats_search_and_timezone(client):
    _,a,_=account(client,'a');_,b,_=account(client,'b')
    response=client.post('/api/study-records',headers=a,json={'subject':'数据库','minutes':42})
    assert response.status_code==201,response.text
    assert client.get('/api/dashboard/summary',headers=a).json()['study_minutes']==42
    assert client.get('/api/dashboard/summary',headers=b).json()['study_minutes']==0
    client.post('/api/tasks',headers=a,json={'title':'主键复习'})
    assert len(client.get('/api/search?q=主键',headers=a).json()['tasks'])==1
    assert client.get('/api/search?q=主键',headers=b).json()['tasks']==[]
    assert client.get('/api/search?q=%27%20OR%201%3D1--',headers=b).json()['tasks']==[]
    assert client.patch('/api/users/me',headers=a,json={'timezone':'bad-zone'}).status_code==422
    future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    assert client.post('/api/study-records',headers=a,json={'subject':'数据库','minutes':42,'studied_at':future}).status_code==422

def test_focus_no_fabricated_time(client):
    _,a,_=account(client,'a')
    r=client.post('/api/focus/start',headers=a,json={'subject':'数学'})
    assert r.status_code==200,r.text
    fid=r.json()['id']
    assert client.post('/api/focus/'+fid+'/stop',headers=a).status_code==422
    assert client.post('/api/focus/start',headers=a,json={'subject':'数学'}).status_code==409
