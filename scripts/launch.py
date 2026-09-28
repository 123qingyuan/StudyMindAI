"""One-click local launcher, no shell commands generated from user input."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'backend'/'.venv'/'Scripts'/'python.exe'
DATA=ROOT/'data'
DATA.mkdir(exist_ok=True)
URL='http://127.0.0.1:8765'
LAN_HOST='0.0.0.0'

def ready():
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(URL+'/api/health',timeout=2) as response:
            return json.load(response).get('status')=='ok'
    except Exception: return False

def listening(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1',port))==0

def start():
    if not PYTHON.is_file(): raise SystemExit('Missing backend virtual environment. See README.md.')
    if not (ROOT/'frontend'/'dist'/'index.html').is_file(): raise SystemExit('Frontend build missing. Run npm ci and npm run build in frontend.')
    if ready():
        if '--no-browser' not in sys.argv: webbrowser.open(URL)
        print('StudyMind is ready: '+URL);return
    if listening(8765): raise SystemExit('Port 8765 is occupied by another service. Nothing was stopped.')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0) | getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
    mysql=ROOT/'runtime'/'mysql'/'bin'/'mysqld.exe'
    if not listening(3306) and mysql.is_file():
        log=(DATA/'mysql-start.log').open('a',encoding='utf-8')
        subprocess.Popen([str(mysql),'--defaults-file='+str(ROOT/'runtime'/'mysql'/'my.ini'),'--console'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        deadline=time.monotonic()+45
        while not listening(3306) and time.monotonic()<deadline: time.sleep(0.25)
        log.close()
        if not listening(3306): raise SystemExit('MySQL did not become ready; see data/mysql-start.log.')
    log=(DATA/'app.log').open('a',encoding='utf-8')
    env=os.environ.copy();env['PYTHONUTF8']='1';env['NO_PROXY']='127.0.0.1,localhost'
    proc=subprocess.Popen([str(PYTHON),'-m','uvicorn','app.main:app','--host',LAN_HOST,'--port','8765','--workers','1'],cwd=ROOT/'backend',stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=flags)
    (DATA/'app.pid').write_text(str(proc.pid),encoding='ascii')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        if ready():
            print('StudyMind is ready: '+URL+' (LAN bind '+LAN_HOST+')')
            if '--no-browser' not in sys.argv: webbrowser.open(URL)
            return
        if proc.poll() is not None: raise SystemExit('Backend exited. See data/app.log.')
        time.sleep(0.3)
    raise SystemExit('Backend readiness timed out. See data/app.log.')

if __name__=='__main__': start()
