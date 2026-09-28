"""Shared persistence/error utilities. No dependency on main.py."""
from __future__ import annotations
import json
from contextlib import contextmanager
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from .. import core


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={'code': code, 'message': message})


@contextmanager
def connection():
    conn = core.db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def rows(items) -> list[dict]:
    return [dict(item) for item in items]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


# Only static module-owned table names can enter this helper.
OWNED_TABLES = frozenset({'conversations', 'messages', 'generations', 'documents',
    'knowledge_bases', 'notes', 'knowledge_points', 'questions', 'ai_reports',
    'agent_tasks', 'tasks', 'courses', 'exams', 'study_plans'})


def owned(conn, table: str, item_id: str, user_id: str) -> dict:
    if table not in OWNED_TABLES:
        raise ValueError('invalid owner table')
    found = conn.execute(f'SELECT * FROM {table} WHERE id=? AND user_id=?',
                         (item_id, user_id)).fetchone()
    if not found:
        fail(404, 'NOT_FOUND', '资源不存在')
    return dict(found)


def non_null_updates(payload: BaseModel) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if any(value is None for value in updates.values()):
        fail(422, 'NULL_NOT_ALLOWED', '此字段不能为 null')
    return updates


def update_owned(conn, table, item_id, user_id, values):
    owned(conn, table, item_id, user_id)
    if values:
        fields = ','.join(f'{key}=?' for key in values)
        conn.execute(f'UPDATE {table} SET {fields},updated_at=? WHERE id=? AND user_id=?',
                     (*values.values(), core.now_iso(), item_id, user_id))
    return owned(conn, table, item_id, user_id)
