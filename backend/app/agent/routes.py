"""Auditable agent execution with bound one-use confirmations and CAS."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from .. import core
from ..ai.common import StrictModel, connection, dumps, fail, owned, rows
from .planner import plan_goal, parse_action, run_tool

router = APIRouter()


class AgentIn(StrictModel):
    goal: str = Field(min_length=1, max_length=2000)


class ConfirmIn(StrictModel):
    plan_hash: str = Field(pattern='^[a-f0-9]{64}$')
    confirmation_token: str = Field(min_length=20, max_length=200)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def plan_hash(user_id, plan):
    return digest(user_id + ':' + dumps(plan))


def token_digest(user_id, agent_id, token):
    return digest(user_id + ':' + agent_id + ':' + token)


def log_tool(conn, aid, name, inputs, output, status):
    conn.execute('INSERT INTO agent_tool_calls(id,agent_task_id,tool_name,input_json,output_json,status,created_at) VALUES(?,?,?,?,?,?,?)',
                 (core.uid(), aid, name, dumps(inputs), dumps(output) if output is not None else None, status, core.now_iso()))


def public_agent(conn, item):
    item['plan'] = json.loads(item.pop('plan_json'))
    item['result'] = json.loads(item.pop('result_json')) if item.get('result_json') else None
    item.pop('result_json', None)
    auth = conn.execute('SELECT plan_hash,expires_at,consumed_at,cancel_requested FROM agent_confirmations WHERE agent_task_id=?', (item['id'],)).fetchone()
    if auth:
        item.update(dict(auth))
    item['logs'] = rows(conn.execute('SELECT * FROM agent_tool_calls WHERE agent_task_id=? ORDER BY created_at,id', (item['id'],)).fetchall())
    for log in item['logs']:
        log['input'] = json.loads(log.pop('input_json'))
        log['output'] = json.loads(log.pop('output_json')) if log.get('output_json') else None
        log.pop('output_json', None)
    return item


@router.post('/agent/tasks')
async def create_agent(payload: AgentIn, user=Depends(core.current_user)):
    plan = await plan_goal(payload.goal, user['id'])
    aid, ts, token = core.uid(), core.now_iso(), secrets.token_urlsafe(32)
    hashed = plan_hash(user['id'], plan)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    with connection() as conn:
        conn.execute('INSERT INTO agent_tasks(id,user_id,goal,status,risk_level,plan_json,requires_confirmation,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                     (aid, user['id'], payload.goal, 'pending_confirmation', 'low', dumps(plan), 1, ts, ts))
        conn.execute('INSERT INTO agent_confirmations(agent_task_id,user_id,plan_hash,token_hash,expires_at) VALUES(?,?,?,?,?)',
                     (aid, user['id'], hashed, token_digest(user['id'], aid, token), expires))
        log_tool(conn, aid, 'read_learning_context', {}, plan['context'], 'completed')
        log_tool(conn, aid, 'llm_planner', {'goal': payload.goal}, {'plan_hash': hashed, 'action_count': len(plan['actions'])}, 'completed')
        result = public_agent(conn, owned(conn, 'agent_tasks', aid, user['id']))
    result['confirmation_token'] = token  # Returned once. Refresh with explicit /confirmation if lost.
    return result


@router.get('/agent/tasks')
def list_agents(user=Depends(core.current_user)):
    with connection() as conn:
        return [public_agent(conn, value) for value in rows(conn.execute('SELECT * FROM agent_tasks WHERE user_id=? ORDER BY created_at DESC LIMIT 100', (user['id'],)).fetchall())]


@router.get('/agent/tasks/{agent_id}')
def get_agent(agent_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        return public_agent(conn, owned(conn, 'agent_tasks', agent_id, user['id']))


@router.post('/agent/tasks/{agent_id}/confirmation')
def refresh_confirmation(agent_id: str, user=Depends(core.current_user)):
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    with connection() as conn:
        agent = owned(conn, 'agent_tasks', agent_id, user['id'])
        if agent['status'] != 'pending_confirmation':
            fail(409, 'INVALID_STATE', '只有待确认计划可以刷新确认凭证')
        hashed = plan_hash(user['id'], json.loads(agent['plan_json']))
        changed = conn.execute('UPDATE agent_confirmations SET token_hash=?,expires_at=?,plan_hash=? WHERE agent_task_id=? AND user_id=? AND consumed_at IS NULL AND cancel_requested=0',
                              (token_digest(user['id'], agent_id, token), expires, hashed, agent_id, user['id'])).rowcount
        if changed != 1:
            fail(409, 'INVALID_STATE', '计划已被确认或取消')
    return {'confirmation_token': token, 'plan_hash': hashed, 'expires_at': expires}


def execute_step(agent_id, user_id, index, action_value):
    with connection() as conn:
        # An UPDATE establishes a per-plan write lock before checking cancellation.
        conn.execute("UPDATE agent_tasks SET updated_at=? WHERE id=? AND user_id=? AND status='running'", (core.now_iso(), agent_id, user_id))
        agent = owned(conn, 'agent_tasks', agent_id, user_id)
        auth = conn.execute('SELECT cancel_requested FROM agent_confirmations WHERE agent_task_id=?', (agent_id,)).fetchone()
        if agent['status'] != 'running' or auth['cancel_requested']:
            return False
        previous = conn.execute('SELECT output_json FROM agent_step_results WHERE agent_task_id=? AND step_index=?', (agent_id, index)).fetchone()
        if previous:
            return True
        action = parse_action(action_value)
        output = run_tool(conn, action, user_id)
        conn.execute('INSERT INTO agent_step_results(agent_task_id,step_index,output_json) VALUES(?,?,?)', (agent_id, index, dumps(output)))
        log_tool(conn, agent_id, action.type, action_value, output, 'completed')
    return True


def finish_execution(agent_id, user_id, status):
    with connection() as conn:
        auth = conn.execute('SELECT cancel_requested FROM agent_confirmations WHERE agent_task_id=?', (agent_id,)).fetchone()
        if auth['cancel_requested']:
            status = 'cancelled'
        results = rows(conn.execute('SELECT step_index,output_json FROM agent_step_results WHERE agent_task_id=? ORDER BY step_index', (agent_id,)).fetchall())
        output = {'completed_steps': len(results), 'steps': [{'index': r['step_index'], 'output': json.loads(r['output_json'])} for r in results]}
        conn.execute("UPDATE agent_tasks SET status=?,result_json=?,updated_at=? WHERE id=? AND user_id=? AND status='running'", (status, dumps(output), core.now_iso(), agent_id, user_id))
        return public_agent(conn, owned(conn, 'agent_tasks', agent_id, user_id))


@router.post('/agent/tasks/{agent_id}/confirm')
async def confirm_agent(agent_id: str, payload: ConfirmIn, user=Depends(core.current_user)):
    with connection() as conn:
        agent = owned(conn, 'agent_tasks', agent_id, user['id'])
        auth = conn.execute('SELECT * FROM agent_confirmations WHERE agent_task_id=? AND user_id=?', (agent_id, user['id'])).fetchone()
        plan = json.loads(agent['plan_json'])
        valid = auth and hmac.compare_digest(auth['plan_hash'], payload.plan_hash) and hmac.compare_digest(
            auth['token_hash'], token_digest(user['id'], agent_id, payload.confirmation_token))
        if not valid or not hmac.compare_digest(plan_hash(user['id'], plan), payload.plan_hash):
            fail(403, 'INVALID_CONFIRMATION', '确认凭证与当前用户或计划不匹配')
        if auth['consumed_at']:
            # Exact replay is idempotent: no tool may be executed again.
            return public_agent(conn, agent)
        if auth['expires_at'] <= core.now_iso():
            fail(410, 'CONFIRMATION_EXPIRED', '确认凭证已过期，请重新检查计划并刷新凭证')
        # CAS and token consumption share one transaction. Rollback on any failure.
        changed = conn.execute("UPDATE agent_tasks SET status='running',requires_confirmation=0,updated_at=? WHERE id=? AND user_id=? AND status='pending_confirmation'",
                               (core.now_iso(), agent_id, user['id'])).rowcount
        if changed != 1:
            fail(409, 'INVALID_STATE', '计划已经运行、取消或结束')
        consumed = conn.execute('UPDATE agent_confirmations SET consumed_at=? WHERE agent_task_id=? AND user_id=? AND token_hash=? AND consumed_at IS NULL AND cancel_requested=0 AND expires_at>?',
            (core.now_iso(), agent_id, user['id'], auth['token_hash'], core.now_iso())).rowcount
        if consumed != 1:
            fail(409, 'CONFIRMATION_USED', '确认凭证已被使用或取消')
        log_tool(conn, agent_id, 'confirmation', {'plan_hash': payload.plan_hash}, {'confirmed': True}, 'completed')
    status = 'completed'
    try:
        for index, action in enumerate(plan['actions']):
            if not await asyncio.to_thread(execute_step, agent_id, user['id'], index, action):
                status = 'cancelled'
                break
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        finish_execution(agent_id, user['id'], 'interrupted')
        raise
    except Exception:
        status = 'failed'
        with connection() as conn:
            log_tool(conn, agent_id, 'execution_error', {}, {'code': 'TOOL_FAILED', 'message': '工具执行失败；已提交步骤可查看日志，未执行步骤未写入'}, 'failed')
    return finish_execution(agent_id, user['id'], status)


@router.post('/agent/tasks/{agent_id}/cancel')
def cancel_agent(agent_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        agent = owned(conn, 'agent_tasks', agent_id, user['id'])
        if agent['status'] in {'pending_confirmation', 'running'}:
            conn.execute('UPDATE agent_confirmations SET cancel_requested=1 WHERE agent_task_id=? AND user_id=?', (agent_id, user['id']))
            conn.execute("UPDATE agent_tasks SET status='cancelled',requires_confirmation=0,updated_at=? WHERE id=? AND user_id=? AND status='pending_confirmation'", (core.now_iso(), agent_id, user['id']))
            log_tool(conn, agent_id, 'cancel', {}, {'requested': True, 'note': '已提交步骤保留；后续步骤停止'}, 'completed')
        return public_agent(conn, owned(conn, 'agent_tasks', agent_id, user['id']))
