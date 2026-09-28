"""Database metrics are authoritative; AI prose is explicitly distinguished."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field
from .. import core
from ..ai.common import StrictModel, connection, dumps, owned, rows


router = APIRouter()


class ReportIn(StrictModel):
    title: str = Field(default='学习报告', min_length=1, max_length=160)
    report_type: Literal['overview', 'weekly', 'subject', 'exam'] = 'overview'


def collect_metrics(user_id: str, conn=None) -> dict:
    if conn is None:
        with connection() as db:
            return collect_metrics(user_id, db)
    u = conn.execute('SELECT timezone FROM users WHERE id=?', (user_id,)).fetchone()
    try:
        zone = ZoneInfo(u['timezone'] if u else 'Asia/Shanghai')
    except (KeyError, ValueError):
        zone = timezone.utc
    today = datetime.now(zone).date()
    start_day = today - timedelta(days=13)
    study = rows(conn.execute('SELECT studied_at,minutes,subject FROM study_records WHERE user_id=? ORDER BY studied_at', (user_id,)).fetchall())
    by_day, subjects, recent = defaultdict(int), defaultdict(int), 0
    for row in study:
        stamp = datetime.fromisoformat(row['studied_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        day = stamp.astimezone(zone).date()
        subjects[row['subject']] += int(row['minutes'])
        if start_day <= day <= today:
            by_day[day.isoformat()] += int(row['minutes'])
            recent += 1
    trend = [{'day': (start_day + timedelta(days=i)).isoformat(),
              'minutes': by_day[(start_day + timedelta(days=i)).isoformat()]} for i in range(14)]
    tasks = conn.execute("SELECT COUNT(*) total,COALESCE(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END),0) done FROM tasks WHERE user_id=?", (user_id,)).fetchone()
    questions = conn.execute("SELECT COUNT(*) total,COALESCE(SUM(CASE WHEN q.type IN ('单选题','多选题','判断题','填空题') THEN 1 ELSE 0 END),0) objective,COALESCE(SUM(CASE WHEN q.type IN ('单选题','多选题','判断题','填空题') THEN r.is_correct ELSE 0 END),0) correct,AVG(r.score) avg_score FROM question_records r JOIN questions q ON q.id=r.question_id WHERE r.user_id=?", (user_id,)).fetchone()
    docs = conn.execute('SELECT COUNT(*) c FROM documents WHERE user_id=?', (user_id,)).fetchone()['c']
    indexed = conn.execute("SELECT COUNT(*) c FROM document_links l JOIN documents d ON d.id=l.document_id WHERE d.user_id=? AND l.index_mode='semantic'", (user_id,)).fetchone()['c']
    upcoming = rows(conn.execute('SELECT subject,exam_date FROM exams WHERE user_id=? AND exam_date>=? ORDER BY exam_date LIMIT 10', (user_id, today.isoformat())).fetchall())
    return {'period': {'start': start_day.isoformat(), 'end': today.isoformat(), 'timezone': str(zone)},
        'study_minutes_14d': sum(item['minutes'] for item in trend), 'study_sessions_14d': recent,
        'study_minutes_total': sum(subjects.values()), 'trend': trend,
        'subject_minutes': [{'subject': k, 'minutes': v} for k, v in sorted(subjects.items(), key=lambda i: (-i[1], i[0]))],
        'tasks': {'total': int(tasks['total']), 'done': int(tasks['done']), 'completion_rate': round(tasks['done'] / tasks['total'] * 100, 2) if tasks['total'] else None},
        'questions': {'answered': int(questions['total']), 'objective_answered': int(questions['objective']), 'correct': int(questions['correct']),
                      'accuracy': round(questions['correct'] / questions['objective'] * 100, 2) if questions['objective'] else None,
                      'mean_score': round(float(questions['avg_score']), 2) if questions['avg_score'] is not None else None},
        'documents': {'total': int(docs), 'semantic_indexed': int(indexed)}, 'upcoming_exams': upcoming}


def deterministic_summary(metrics):
    return (f"学习数据摘要：{metrics['period']['start']} 至 {metrics['period']['end']}，"
            f"学习 {metrics['study_minutes_14d']} 分钟、记录 {metrics['study_sessions_14d']} 次；"
            f"已完成任务 {metrics['tasks']['done']}/{metrics['tasks']['total']}；"
            f"客观题答对 {metrics['questions']['correct']}/{metrics['questions']['objective_answered']}；"
            f"资料 {metrics['documents']['total']} 份。没有记录不代表没有学习；主观题自评不计入客观正确率。")


def save_report(conn, user_id, title, report_type, metrics, content, source):
    rid, ts = core.uid(), core.now_iso()
    conn.execute('INSERT INTO ai_reports(id,user_id,title,metrics_json,content,report_type,created_at) VALUES(?,?,?,?,?,?,?)',
                 (rid, user_id, title, dumps(metrics), content, report_type, ts))
    conn.execute('INSERT INTO report_metadata(report_id,source) VALUES(?,?)', (rid, source))
    return {'id': rid, 'title': title, 'metrics': metrics, 'content': content, 'report_type': report_type, 'source': source, 'created_at': ts}


async def generate_report_for(user_id, title, report_type):
    metrics = collect_metrics(user_id)
    source, content, warning = 'data_summary', deterministic_summary(metrics), None
    with connection() as conn:
        report = save_report(conn, user_id, title, report_type, metrics, content, source)
    report['warning'] = warning
    return report


@router.get('/reports/metrics')
def report_metrics(user=Depends(core.current_user)):
    return {'metrics': collect_metrics(user['id']), 'source': 'database'}


@router.post('/reports/generate')
@router.post('/analytics/reports/generate', include_in_schema=False)
async def generate_report(payload: ReportIn, user=Depends(core.current_user)):
    return await generate_report_for(user['id'], payload.title, payload.report_type)


def decode_report(conn, item):
    item['metrics'] = json.loads(item.pop('metrics_json'))
    meta = conn.execute('SELECT source FROM report_metadata WHERE report_id=?', (item['id'],)).fetchone()
    item['source'] = meta['source'] if meta else 'unknown'
    return item


@router.get('/reports')
@router.get('/analytics/reports', include_in_schema=False)
def list_reports(user=Depends(core.current_user)):
    with connection() as conn:
        return [decode_report(conn, item) for item in rows(conn.execute('SELECT * FROM ai_reports WHERE user_id=? ORDER BY created_at DESC LIMIT 100', (user['id'],)).fetchall())]


@router.get('/reports/{report_id}')
@router.get('/analytics/reports/{report_id}', include_in_schema=False)
def get_report(report_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        return decode_report(conn, owned(conn, 'ai_reports', report_id, user['id']))


@router.delete('/reports/{report_id}')
def delete_report(report_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'ai_reports', report_id, user['id'])
        conn.execute('DELETE FROM ai_reports WHERE id=? AND user_id=?', (report_id, user['id']))
    return {'ok': True}
