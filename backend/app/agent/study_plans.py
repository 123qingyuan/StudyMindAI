"""AI-generated study-plan drafts; manual plans remain in core learning API."""
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends
from pydantic import Field, ValidationError, model_validator
from .. import core
from ..ai.common import StrictModel, connection, dumps, fail, rows
from ..ai.service import complete_for, parse_json
from .planner import learning_context

router = APIRouter()


class PlanIn(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=2000)
    start_date: date
    end_date: date
    daily_minutes: int = Field(strict=True, ge=10, le=480)

    @model_validator(mode='after')
    def dates(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 30:
            raise ValueError('AI 计划日期范围为 1 至 31 天；更长范围请分段规划')
        return self


class PlanItem(StrictModel):
    plan_date: date
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    estimated_minutes: int = Field(strict=True, ge=1, le=480)


class PlanOutput(StrictModel):
    items: list[PlanItem] = Field(min_length=1, max_length=100)


@router.post('/study-plans/generate')
async def generate_plan(payload: PlanIn, user=Depends(core.current_user)):
    context = learning_context(user['id'])
    raw = await complete_for(user['id'], 'study_plan', [
        {'role': 'system', 'content': '你是学习规划师。基于真实课程、考试、已有任务和目标生成每日具体学习计划。每一天都必须有任务，单日总分钟不得超过预算，不得声称已经完成学习。只输出 JSON，schema: ' + dumps(PlanOutput.model_json_schema())},
        {'role': 'user', 'content': dumps({'request': payload.model_dump(mode='json'), 'context': context})}],
        json_mode=True, max_tokens=12000)
    try:
        plan = PlanOutput.model_validate_json(raw, strict=True)
    except ValidationError:
        fail(502, 'INVALID_AI_PLAN', 'AI 计划结构无效，未保存')
    totals = defaultdict(int)
    for item in plan.items:
        totals[item.plan_date] += item.estimated_minutes
    expected = {payload.start_date + timedelta(days=i) for i in range((payload.end_date - payload.start_date).days + 1)}
    if set(totals) != expected or any(minutes > payload.daily_minutes for minutes in totals.values()):
        fail(502, 'INVALID_AI_PLAN', 'AI 计划未覆盖指定日期或超出每天时间预算，未保存')
    pid, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO study_plans(id,user_id,title,goal,start_date,end_date,daily_minutes,status,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (pid, user['id'], payload.title, payload.goal, payload.start_date.isoformat(), payload.end_date.isoformat(), payload.daily_minutes, 'draft', 'ai', ts, ts))
        for item in plan.items:
            conn.execute('INSERT INTO study_plan_items(id,study_plan_id,plan_date,title,description,estimated_minutes,status,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (core.uid(), pid, item.plan_date.isoformat(), item.title, item.description, item.estimated_minutes, 'todo', ts))
        result = dict(conn.execute('SELECT * FROM study_plans WHERE id=? AND user_id=?', (pid, user['id'])).fetchone())
        result['items'] = rows(conn.execute('SELECT * FROM study_plan_items WHERE study_plan_id=? ORDER BY plan_date', (pid,)).fetchall())
        return result
