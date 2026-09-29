"""Restored AI routes: mock transports only, never claim upstream availability."""
import json
import httpx
import pytest
from test_intelligence import env
from app import core
from app.ai import providers


def configure(c, auth):
    return c.put('/api/settings/ai', headers=auth, json={'provider':'openai-compatible','model':'test-model','base_url':'https://example.com/v1','api_key':'test-secret-only'})


def test_settings_isolation_encryption_and_ssrf(env, monkeypatch):
    c,a,b=env
    monkeypatch.delenv('AI_ALLOW_PRIVATE_ENDPOINTS', raising=False)
    assert c.get('/api/settings/ai').status_code==401
    assert c.put('/api/settings/ai',headers=a,json={'provider':'openai','model':'test','base_url':'http://127.0.0.1','api_key':'test'}).status_code==422
    async def public(*args): pass
    monkeypatch.setattr('app.ai.service.validate_url',public)
    assert configure(c,a).status_code==200
    assert 'test-secret-only' not in c.get('/api/settings/ai',headers=a).text
    assert c.get('/api/settings/ai',headers=b).json()['source']=='server_default'
    with core.db() as db:
        row=db.execute('SELECT secret_encrypted FROM ai_settings').fetchone()
        assert 'test-secret-only' not in row['secret_encrypted']
    assert c.put('/api/settings/ai',headers=a,json={'provider':'openai-compatible','model':'x','base_url':'https://other.example/v1'}).status_code==422
    assert c.delete('/api/settings/ai',headers=a).json()['source']=='server_default'
    assert c.get('/api/settings/ai',headers=a).json()['source']=='server_default'


@pytest.mark.parametrize('status,code',[(200,None),(400,'AI_INVALID_REQUEST'),(401,'AI_AUTH_REJECTED'),(402,'AI_BILLING_REQUIRED'),(403,'AI_AUTH_REJECTED'),(404,'AI_ENDPOINT_NOT_FOUND'),(422,'AI_INVALID_PARAMETERS'),(429,'AI_RATE_LIMITED'),(500,'AI_UPSTREAM_HTTP_ERROR')])
def test_completion_stream_and_failure_readback(env,monkeypatch,status,code):
    c,a,b=env
    async def public(*args): pass
    monkeypatch.setattr('app.ai.service.validate_url',public)
    monkeypatch.setattr(providers,'validate_url',public)
    assert configure(c,a).status_code==200
    original=httpx.AsyncClient
    def respond(request):
        data=json.loads(request.content)
        if status!=200: return httpx.Response(status,json={'secret':'must-not-leak'})
        if not data['stream']:
            return httpx.Response(200,json={'choices':[{'message':{'content':'connection ok'}}]})
        return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'hello'},'finish_reason':None}]})+'\n\ndata: [DONE]\n\n',headers={'content-type':'text/event-stream'})
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs: original(transport=httpx.MockTransport(respond),**kwargs))
    r=c.post('/api/settings/ai/test',headers=a)
    assert r.status_code==(200 if status==200 else 429 if status==429 else 502)
    if code: assert r.json()['detail']['code']==code
    cid=c.post('/api/conversations',headers=a,json={'mode':'general'}).json()['id']
    assert c.get(f'/api/conversations/{cid}/messages',headers=b).status_code==404
    r=c.post(f'/api/conversations/{cid}/messages',headers=a,json={'content':'hello'})
    assert r.status_code==200 and 'message_end' in r.text and 'must-not-leak' not in r.text
    assert (code in r.text) if code else ('hello' in r.text)
    messages=c.get(f'/api/conversations/{cid}/messages',headers=a).json()
    assistant=next(x for x in messages if x['role']=='assistant')
    assert assistant['status']==('failed' if code else 'completed')
    with core.db() as db: assert not db.execute('SELECT * FROM conversation_generation_locks').fetchall()
    assert c.delete(f'/api/conversations/{cid}',headers=a).status_code==200
