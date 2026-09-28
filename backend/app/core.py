"""Application security, isolated configuration and persistence primitives."""
from __future__ import annotations
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .database import Database

ROOT = Path(os.getenv('STUDYMIND_BUNDLE_ROOT', str(Path(__file__).resolve().parents[2])))
if os.getenv('STUDYMIND_TESTING') != '1': load_dotenv(ROOT / 'backend' / '.env', override=False)
DATA_DIR = Path(os.getenv('STUDYMIND_DATA_DIR', str(ROOT / 'data')))
UPLOAD_DIR = DATA_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'studymind.sqlite3'
DATABASE_URL = os.getenv('DATABASE_URL') or 'sqlite:///' + DB_PATH.as_posix()
if os.getenv('STUDYMIND_TESTING') == '1': DATABASE_URL = os.getenv('TEST_DATABASE_URL') or 'sqlite:///' + DB_PATH.as_posix()
_database = Database(DATABASE_URL)


def db(): return _database.connect()
def uid(): return str(uuid.uuid4())
def now_iso(): return datetime.now(timezone.utc).isoformat(timespec='microseconds')
def fail(status, code, message): raise HTTPException(status, {'code':code, 'message':message})
def local_now(user): return datetime.now(ZoneInfo(user.get('timezone') or 'Asia/Shanghai'))


def init_db():
    from .schema import SCHEMA
    from .extra_schema import SCHEMA as AI_SCHEMA
    from .legacy_content import SCHEMA as LEGACY_SCHEMA
    _database.initialize(SCHEMA + '\n' + AI_SCHEMA + '\n' + LEGACY_SCHEMA)
    from .default_content import _schema_compat
    with db() as conn:
        _schema_compat(conn)
        if not conn.execute('SELECT version FROM schema_versions WHERE version=?', (1,)).fetchone():
            conn.execute('INSERT INTO schema_versions(version,applied_at) VALUES(?,?)', (1,now_iso()))


def secret_key():
    configured = os.getenv('STUDYMIND_SECRET')
    if configured:
        if len(configured) < 32: raise RuntimeError('STUDYMIND_SECRET must have 32+ characters')
        return configured
    path = DATA_DIR / '.jwt-key'
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError: pass
    else:
        with os.fdopen(descriptor,'w') as f: f.write(secrets.token_urlsafe(48))
    return path.read_text().strip()

SECRET = secret_key()
PASSWORD = PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
DUMMY_HASH = PASSWORD.hash(secrets.token_urlsafe(20))
oauth = OAuth2PasswordBearer(tokenUrl='/api/auth/login', auto_error=False)


def public_user(user):
    return {k:user.get(k) for k in ('id','email','display_name','avatar_url','timezone')}


def current_user(token: str | None = Depends(oauth)):
    if not token: fail(401,'UNAUTHORIZED','请先登录')
    try:
        payload = jwt.decode(token, SECRET, algorithms=['HS256'], issuer='studymind', options={'require':['exp','iat','sub','jti']})
    except jwt.InvalidTokenError: fail(401,'INVALID_TOKEN','登录已失效，请重新登录')
    with db() as conn:
        found = conn.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND s.id=? AND s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?',
            (payload['sub'],payload['jti'],hashlib.sha256(token.encode()).hexdigest(),now_iso())).fetchone()
    if not found: fail(401,'SESSION_REVOKED','登录已失效，请重新登录')
    return dict(found)


OWNED = {'tasks','courses','exams','study_records','study_plans','notes','documents','conversations','questions','agent_tasks','knowledge_bases','ai_reports','focus_sessions'}
def ensure_owner(conn,table,item_id,user_id):
    if table not in OWNED: raise ValueError('Not an owned table')
    found=conn.execute(f'SELECT * FROM {table} WHERE id=? AND user_id=?',(item_id,user_id)).fetchone()
    if not found: fail(404,'NOT_FOUND','资源不存在')
    return dict(found)


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class LoginIn(StrictModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=8,max_length=128)
    @field_validator('email')
    @classmethod
    def email_value(cls,value):
        import re
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value): raise ValueError('邮箱格式无效')
        return value.lower()
class RegisterIn(LoginIn):
    display_name:str=Field(min_length=1,max_length=40)
class ProfilePatch(StrictModel):
    display_name:str|None=Field(default=None,min_length=1,max_length=40)
    timezone:str|None=None
    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,value):
        if value is not None:
            try: ZoneInfo(value)
            except Exception: raise ValueError('时区无效')
        return value

limits=defaultdict(deque)
limit_lock=threading.Lock()
def throttle(request,email):
    key=((request.client.host if request.client else 'local'),email)
    with limit_lock:
        attempts=limits[key];now=time.monotonic()
        while attempts and attempts[0]<now-300: attempts.popleft()
        if len(attempts)>=20: fail(429,'LOGIN_RATE_LIMIT','登录尝试过于频繁，请稍后再试')
        attempts.append(now)
        if len(limits)>10000: limits.clear()


def auth_result(user):
    session_id=uid();ts=datetime.now(timezone.utc);expires=ts+timedelta(hours=12)
    token=jwt.encode({'sub':user['id'],'jti':session_id,'iss':'studymind','iat':ts,'exp':expires},SECRET,algorithm='HS256')
    with db() as conn:
        conn.execute('INSERT INTO sessions(id,user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?,?)',(session_id,user['id'],hashlib.sha256(token.encode()).hexdigest(),expires.isoformat(),now_iso()))
    return {'access_token':token,'token_type':'bearer','expires_in':43200,'user':public_user(user)}

router=APIRouter(prefix='/api')
@router.post('/auth/register',status_code=201)
def register(payload:RegisterIn,request:Request):
    import sqlite3
    throttle(request,payload.email)
    user={'id':uid(),'email':payload.email,'display_name':payload.display_name,'timezone':'Asia/Shanghai','avatar_url':None}
    password_hash=PASSWORD.hash(payload.password)
    from .default_content import _copy_default_content
    from .legacy_content import provision as provision_legacy
    try:
        # User row and built-in provisioning share one transaction: a failed
        # initialization cannot leave a half-registered account behind.
        with db() as conn:
            conn.execute('INSERT INTO users(id,email,password_hash,display_name,timezone,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(user['id'],user['email'],password_hash,user['display_name'],user['timezone'],now_iso(),now_iso()))
            _copy_default_content(user['id'], conn=conn)
            provision_legacy(user['id'], conn)
    except sqlite3.IntegrityError: fail(409,'EMAIL_EXISTS','该邮箱已经注册')
    except Exception:
        fail(503,'DEFAULT_CONTENT_UNAVAILABLE','内置知识库初始化失败，请重试注册')
    return auth_result(user)

@router.post('/auth/login')
def login(payload:LoginIn,request:Request):
    throttle(request,payload.email)
    with db() as conn: user=conn.execute('SELECT * FROM users WHERE email=?',(payload.email,)).fetchone()
    try: PASSWORD.verify(user['password_hash'] if user else DUMMY_HASH,payload.password)
    except (VerificationError,InvalidHashError): fail(401,'LOGIN_FAILED','邮箱或密码错误')
    if not user: fail(401,'LOGIN_FAILED','邮箱或密码错误')
    return auth_result(user)

@router.post('/auth/logout')
def logout(user=Depends(current_user),token=Depends(oauth)):
    with db() as conn: conn.execute('UPDATE sessions SET revoked_at=? WHERE user_id=? AND token_hash=?',(now_iso(),user['id'],hashlib.sha256(token.encode()).hexdigest()))
    return {'ok':True}
@router.get('/auth/me')
def me(user=Depends(current_user)): return public_user(user)
@router.patch('/users/me')
def update_me(payload:ProfilePatch,user=Depends(current_user)):
    updates=payload.model_dump(exclude_none=True)
    with db() as conn:
        if updates:
            fields=','.join(f'{k}=?' for k in updates)
            conn.execute(f'UPDATE users SET {fields},updated_at=? WHERE id=?',(*updates.values(),now_iso(),user['id']))
        result=conn.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
    return public_user(result)
