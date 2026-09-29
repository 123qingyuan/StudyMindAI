"""StudyMind ASGI application. Start one worker for local Qdrant storage."""
from contextlib import asynccontextmanager
import logging
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from . import core
from .learning import router as learning_router
from .intelligence import router as ai_router


@asynccontextmanager
async def lifespan(app):
    core.init_db()
    # One worker owns local Qdrant. A previous crash must not lock chats forever.
    with core.db() as conn:
        conn.execute("UPDATE messages SET status='failed' WHERE status='generating'")
        conn.execute("UPDATE generations SET status='failed',updated_at=? WHERE status='generating'", (core.now_iso(),))
        conn.execute('DELETE FROM conversation_generation_locks')
    yield
    from .rag.store import close_clients
    close_clients()

app=FastAPI(title='StudyMind · 个人学习空间',version='2.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173','http://localhost:8765','http://127.0.0.1:8765'],allow_credentials=False,allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['Authorization','Content-Type'])

@app.middleware('http')
async def harden(request:Request,call_next):
    length=request.headers.get('content-length','0')
    try: too_large=int(length)>22*1024*1024
    except ValueError: too_large=True
    if too_large: return JSONResponse({'error':{'code':'REQUEST_TOO_LARGE','message':'请求超过大小限制'}},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

def error_response(status,code,message,details=None):
    value={'code':code,'message':message}
    if details is not None: value['details']=details
    return JSONResponse({'error':value,'detail':value},status_code=status)
@app.exception_handler(HTTPException)
async def http_error(request,exc):
    detail=exc.detail if isinstance(exc.detail,dict) else {'code':'REQUEST_ERROR','message':str(exc.detail)}
    return error_response(exc.status_code,detail.get('code','REQUEST_ERROR'),detail.get('message','请求失败'))
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    details=[{'field':'.'.join(str(x) for x in e['loc']),'message':e['msg']} for e in exc.errors()]
    return error_response(422,'VALIDATION_ERROR','请检查输入内容',details)
@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request,exc): return error_response(409,'CONFLICT','操作与现有数据冲突')
@app.exception_handler(Exception)
async def internal_error(request,exc):
    logging.getLogger('studymind').error('Unhandled error %s at %s',type(exc).__name__,request.url.path)
    return error_response(500,'INTERNAL_ERROR','服务器处理失败，请稍后重试')

@app.get('/api/health')
def health():
    with core.db() as conn: conn.execute('SELECT 1 AS ok').fetchone()
    return {'status':'ok','database':core._database.engine.dialect.name,'version':app.version,'storage':'local','ocr':'rapidocr-onnx','embedding':'BAAI/bge-small-zh-v1.5','vector_store':'Qdrant-local'}

app.include_router(core.router)
app.include_router(learning_router)
app.include_router(ai_router)
DIST=core.ROOT/'frontend'/'dist'
if DIST.exists(): app.mount('/',StaticFiles(directory=str(DIST),html=True),name='frontend')
