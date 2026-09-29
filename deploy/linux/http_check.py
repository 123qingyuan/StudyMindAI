"""HTTP acceptance against a disposable instance. Never use production accounts."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('phase', choices=['create', 'verify'])
p.add_argument('--url', default='http://127.0.0.1:18765')
p.add_argument('--state', required=True)
a = p.parse_args()
os.umask(0o077)
state_path = Path(a.state)

def request(path, method='GET', payload=None, token=None, status=200):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(a.url + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            code, body = response.status, response.read()
    except urllib.error.HTTPError as exc:
        code, body = exc.code, exc.read()
    assert code == status, (path, code, body[:300])
    return json.loads(body)

health = request('/api/health')
assert health['database'] == 'sqlite' and health['embedding'] == 'keyword'
with urllib.request.urlopen(a.url + '/', timeout=10) as response:
    html = response.read().decode()
assert '<html' in html.lower()
assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
assert assets
for asset in assets:
    with urllib.request.urlopen(a.url + asset, timeout=10) as response:
        assert response.status == 200 and len(response.read()) > 0
if a.phase == 'create':
    state = {'email': 'linux-' + secrets.token_hex(8) + '@example.invalid', 'password': secrets.token_urlsafe(24)}
    registration = request('/api/auth/register', 'POST', {**state, 'display_name': 'Linux acceptance'}, status=201)
    state['token'] = registration['access_token']
    state['user_id'] = registration['user']['id']
    request('/api/auth/register', 'POST', {'email': state['email'], 'password': state['password'], 'display_name': 'Duplicate'}, status=409)
    request('/api/auth/login', 'POST', {'email': state['email'], 'password': 'invalid-password'}, status=401)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding='utf-8')
else:
    state = json.loads(state_path.read_text(encoding='utf-8'))
# An old token surviving container recreation proves sessions + JWT key persist.
assert request('/api/auth/me', token=state['token'])['id'] == state['user_id']
login = request('/api/auth/login', 'POST', {'email': state['email'], 'password': state['password']})
assert login['user']['id'] == state['user_id']
settings = request('/api/settings/ai', token=login['access_token'])
assert settings['embedding_mode'] == 'keyword' and not settings['configured']
print(json.dumps({'phase': a.phase, 'health': health, 'homepage_assets': len(assets), 'auth': 'pass', 'old_session': 'pass', 'offline_defaults': 'pass'}))
