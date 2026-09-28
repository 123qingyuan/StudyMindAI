"""Conversation lifecycle and cancellable SSE with durable partial messages."""
from __future__ import annotations
import asyncio
import contextlib
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from .. import core
from .common import StrictModel, connection, rows, owned, fail, non_null_updates, update_owned
from .service import Mode, MODES, provider_for, bounded_messages, record_usage
from .providers import ProviderError

router = APIRouter()


class ConversationIn(StrictModel):
    title: str = Field(default='新对话', min_length=1, max_length=120)
    mode: Mode = 'tutor'


class ConversationPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    mode: Mode | None = None


class ChatIn(StrictModel):
    content: str = Field(min_length=1, max_length=20000)
    knowledge_base_id: str | None = None


@router.get('/conversations')
def list_conversations(user=Depends(core.current_user)):
    with connection() as conn:
        return rows(conn.execute('SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC', (user['id'],)).fetchall())


@router.post('/conversations')
def create_conversation(payload: ConversationIn, user=Depends(core.current_user)):
    cid, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO conversations(id,user_id,title,mode,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                     (cid, user['id'], payload.title, payload.mode, ts, ts))
        return owned(conn, 'conversations', cid, user['id'])


@router.get('/conversations/{conversation_id}')
def get_conversation(conversation_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        return owned(conn, 'conversations', conversation_id, user['id'])


@router.patch('/conversations/{conversation_id}')
def patch_conversation(conversation_id: str, payload: ConversationPatch, user=Depends(core.current_user)):
    with connection() as conn:
        return update_owned(conn, 'conversations', conversation_id, user['id'], non_null_updates(payload))


@router.delete('/conversations/{conversation_id}')
def delete_conversation(conversation_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'conversations', conversation_id, user['id'])
        if conn.execute("SELECT 1 FROM generations WHERE conversation_id=? AND status='generating'", (conversation_id,)).fetchone():
            fail(409, 'GENERATION_ACTIVE', '请先取消当前生成，再删除对话')
        conn.execute('DELETE FROM conversations WHERE id=? AND user_id=?', (conversation_id, user['id']))
    return {'ok': True}


@router.get('/conversations/{conversation_id}/messages')
def list_messages(conversation_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'conversations', conversation_id, user['id'])
        return rows(conn.execute('SELECT id,role,content,status,created_at FROM messages WHERE conversation_id=? AND user_id=? ORDER BY created_at,id',
                                 (conversation_id, user['id'])).fetchall())


def sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


def cancel_requested(gid, user_id):
    with connection() as conn:
        row = conn.execute('SELECT cancel_requested FROM generations WHERE id=? AND user_id=?', (gid, user_id)).fetchone()
        return not row or bool(row['cancel_requested'])


async def start_generation(conversation_id, user, request, content=None, regenerate=False, knowledge_base_id=None):
    provider = provider_for(user['id'])  # Real 503 before opening the SSE response.
    gid, mid, ts = core.uid(), core.uid(), core.now_iso()
    with connection() as conn:
        conversation = owned(conn, 'conversations', conversation_id, user['id'])
        if conn.execute("SELECT 1 FROM generations WHERE conversation_id=? AND status='generating'", (conversation_id,)).fetchone():
            fail(409, 'GENERATION_ACTIVE', '此对话已有生成任务')
        history = rows(conn.execute("SELECT id,role,content,status,created_at FROM messages WHERE conversation_id=? AND user_id=? AND status!='superseded' ORDER BY created_at,id",
                                    (conversation_id, user['id'])).fetchall())
        if regenerate:
            positions = [i for i, message in enumerate(history) if message['role'] == 'user']
            if not positions:
                fail(409, 'NO_MESSAGE_TO_REGENERATE', '尚无可重新生成的用户消息')
            cut = positions[-1] + 1
            superseded = [message['id'] for message in history[cut:]]
            history = history[:cut]
        else:
            superseded = []
            history.append({'role': 'user', 'content': content})
        system_prompt = MODES[conversation['mode']]
        if knowledge_base_id:
            from ..rag.store import retrieve
            evidence, retrieval_mode, warning = await retrieve(content or history[-1]['content'], user['id'], knowledge_base_id, limit=5)
            if not evidence:
                fail(422, 'INSUFFICIENT_EVIDENCE', '当前知识库中没有找到足够的信息')
            sources = '\n\n'.join(f"[{i+1}] {item['name']} 第{item.get('page') or '?'}页\n{item['content'][:2600]}" for i, item in enumerate(evidence))
            system_prompt += '\n\n本轮必须只根据以下知识库证据回答，每个关键结论标注 [n]；证据不足必须明确说明，不得用常识补造。\n' + sources
        prompt = bounded_messages([{'role': 'system', 'content': system_prompt}] +
                    [{'role': m['role'], 'content': m['content']} for m in history], provider.config.input_budget)
        # Dedicated primary-key lock works on both SQLite and MySQL.
        try:
            conn.execute('INSERT INTO conversation_generation_locks(conversation_id,generation_id) VALUES(?,?)', (conversation_id, gid))
        except Exception as exc:
            if 'integrity' in type(exc).__name__.lower() or 'unique' in str(exc).lower() or 'duplicate' in str(exc).lower():
                fail(409, 'GENERATION_ACTIVE', '此对话已有生成任务')
            raise
        for message_id in superseded:
            conn.execute("UPDATE messages SET status='superseded' WHERE id=?", (message_id,))
        if not regenerate:
            conn.execute('INSERT INTO messages(id,conversation_id,user_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)',
                         (core.uid(), conversation_id, user['id'], 'user', content, 'completed', ts))
        conn.execute('INSERT INTO messages(id,conversation_id,user_id,role,content,status,created_at) VALUES(?,?,?,?,?,?,?)',
                     (mid, conversation_id, user['id'], 'assistant', '', 'generating', core.now_iso()))
        conn.execute('INSERT INTO generations(id,user_id,conversation_id,message_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                     (gid, user['id'], conversation_id, mid, 'generating', ts, ts))
        conn.execute('UPDATE conversations SET updated_at=? WHERE id=?', (ts, conversation_id))

    async def events():
        text, status, usage = '', 'cancelled', None
        pending, iterator = None, provider.stream(prompt).__aiter__()
        started = asyncio.get_running_loop().time()
        try:
            yield sse('message_start', {'message_id': mid, 'generation_id': gid})
            while True:
                if cancel_requested(gid, user['id']):
                    break
                if asyncio.get_running_loop().time() - started > 180:
                    raise ProviderError('AI_TIMEOUT', '生成超时，已保存部分内容', 504)
                if pending is None:
                    pending = asyncio.create_task(iterator.__anext__())
                done, _ = await asyncio.wait({pending}, timeout=0.25)
                if not done:
                    continue
                try:
                    delta = pending.result()
                except StopAsyncIteration:
                    status = 'completed' if text else 'failed'
                    if not text:
                        yield sse('error', {'code': 'AI_EMPTY_RESPONSE', 'message': '模型未返回文本'})
                    break
                finally:
                    pending = None
                if delta.usage is not None:
                    usage = delta.usage
                if delta.text:
                    text += delta.text
                    # Checkpoint each delta; abrupt worker failure loses no emitted text.
                    with connection() as conn:
                        conn.execute('UPDATE messages SET content=? WHERE id=? AND user_id=?', (text, mid, user['id']))
                        conn.execute('UPDATE generations SET updated_at=? WHERE id=?', (core.now_iso(), gid))
                    yield sse('token', {'content': delta.text})
        except asyncio.CancelledError:
            status = 'cancelled'
            raise
        except GeneratorExit:
            status = 'cancelled'
            raise
        except Exception as exc:
            status = 'failed'
            error = exc if isinstance(exc, ProviderError) else ProviderError()
            yield sse('error', {'code': error.code, 'message': error.message})
        finally:
            # Synchronous transaction runs even under Starlette's cancellation scope.
            with connection() as conn:
                conn.execute('UPDATE messages SET content=?,status=? WHERE id=? AND user_id=?', (text, status, mid, user['id']))
                conn.execute('UPDATE generations SET status=?,updated_at=? WHERE id=?', (status, core.now_iso(), gid))
                conn.execute('DELETE FROM conversation_generation_locks WHERE conversation_id=? AND generation_id=?', (conversation_id, gid))
            record_usage(user['id'], 'chat_regenerate' if regenerate else 'chat', provider, usage, status)
            if pending:
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await pending
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await iterator.aclose()
        yield sse('message_end', {'message_id': mid, 'generation_id': gid, 'status': status})

    return StreamingResponse(events(), media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.post('/conversations/{conversation_id}/messages')
async def send_message(conversation_id: str, payload: ChatIn, request: Request, user=Depends(core.current_user)):
    return await start_generation(conversation_id, user, request, content=payload.content, knowledge_base_id=payload.knowledge_base_id)


@router.post('/conversations/{conversation_id}/regenerate')
async def regenerate(conversation_id: str, request: Request, user=Depends(core.current_user)):
    return await start_generation(conversation_id, user, request, regenerate=True)


@router.get('/generations/{generation_id}')
def get_generation(generation_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        return owned(conn, 'generations', generation_id, user['id'])


@router.post('/generations/{generation_id}/cancel')
def cancel_generation(generation_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        value = owned(conn, 'generations', generation_id, user['id'])
        if value['status'] == 'generating':
            conn.execute('UPDATE generations SET cancel_requested=1,updated_at=? WHERE id=? AND user_id=?', (core.now_iso(), generation_id, user['id']))
        value = owned(conn, 'generations', generation_id, user['id'])
    return {'generation_id': generation_id, 'status': value['status'], 'cancel_requested': bool(value['cancel_requested'])}
