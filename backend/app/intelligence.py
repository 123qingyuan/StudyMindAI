"""Local-only feature router: documents, knowledge, questions and reports."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field
from . import core
from .ai.common import StrictModel, dumps, owned, rows
from .document.routes import router as document_router
from .agent.question_bank import router as question_router

router=APIRouter(prefix='/api')
router.include_router(document_router)
router.include_router(question_router)
from .ai.service import router as settings_router
from .ai.chat import router as chat_router
router.include_router(settings_router)
router.include_router(chat_router)

class ReportIn(StrictModel):
    period: Literal['daily','weekly']='weekly'

def metrics_for(user_id:str,period:str):
    days=1 if period=='daily' else 7
    cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
    with core.db() as conn:
        minutes=conn.execute('SELECT COALESCE(SUM(minutes),0) n FROM study_records WHERE user_id=? AND studied_at>=?',(user_id,cutoff)).fetchone()['n']
        tasks=conn.execute("SELECT COUNT(*) total,COALESCE(SUM(status='done'),0) done FROM tasks WHERE user_id=? AND created_at>=?",(user_id,cutoff)).fetchone()
        subjects=rows(conn.execute('SELECT subject,SUM(minutes) minutes FROM study_records WHERE user_id=? AND studied_at>=? GROUP BY subject ORDER BY minutes DESC',(user_id,cutoff)).fetchall())
        questions=conn.execute('SELECT COUNT(*) total,COALESCE(SUM(is_correct),0) correct FROM question_records q LEFT JOIN question_reviews r ON r.record_id=q.id WHERE q.user_id=? AND q.answered_at>=? AND r.record_id IS NULL',(user_id,cutoff)).fetchone()
    return {'period':period,'days':days,'study_minutes':int(minutes or 0),'task_total':int(tasks['total'] or 0),'task_done':int(tasks['done'] or 0),'task_rate':round(float(tasks['done'])/float(tasks['total'])*100) if tasks['total'] else 0,'subjects':[{'subject':x['subject'],'minutes':int(x['minutes'] or 0)} for x in subjects],'objective_question_total':int(questions['total'] or 0),'objective_question_correct':int(questions['correct'] or 0),'objective_accuracy':round(float(questions['correct'])/float(questions['total'])*100) if questions['total'] else None}

@router.get('/reports')
def list_reports(user=Depends(core.current_user)):
    with core.db() as conn:
        values=rows(conn.execute("SELECT r.*,COALESCE(m.source,'data_summary') source FROM ai_reports r LEFT JOIN report_metadata m ON m.report_id=r.id WHERE r.user_id=? ORDER BY r.created_at DESC LIMIT 30",(user['id'],)).fetchall())
    for value in values:value['metrics']=json.loads(value.pop('metrics_json'))
    return values

@router.post('/reports')
def create_report(payload:ReportIn,user=Depends(core.current_user)):
    metrics=metrics_for(user['id'],payload.period);label='过去一天' if payload.period=='daily' else '过去七天'
    content=f"{label}学习数据摘要：学习 {metrics['study_minutes']} 分钟，完成任务 {metrics['task_done']}/{metrics['task_total']} 项，客观题答对 {metrics['objective_question_correct']}/{metrics['objective_question_total']} 题。\n\n本报告完全依据数据库中的学习记录生成。"
    rid=core.uid();title=('今日' if payload.period=='daily' else '本周')+'学习报告';ts=core.now_iso()
    with core.db() as conn:
        conn.execute('INSERT INTO ai_reports(id,user_id,title,metrics_json,content,report_type,created_at) VALUES(?,?,?,?,?,?,?)',(rid,user['id'],title,dumps(metrics),content,payload.period,ts))
        conn.execute('INSERT INTO report_metadata(report_id,source) VALUES(?,?)',(rid,'data_summary'))
    return {'id':rid,'title':title,'metrics':metrics,'content':content,'report_type':payload.period,'source':'data_summary','created_at':ts}

@router.get('/reports/{report_id}')
def get_report(report_id:str,user=Depends(core.current_user)):
    with core.db() as conn:
        value=dict(owned(conn,'ai_reports',report_id,user['id']));value['metrics']=json.loads(value.pop('metrics_json'));value['source']='data_summary';return value

@router.delete('/reports/{report_id}')
def delete_report(report_id:str,user=Depends(core.current_user)):
    with core.db() as conn:
        owned(conn,'ai_reports',report_id,user['id']);conn.execute('DELETE FROM ai_reports WHERE id=? AND user_id=?',(report_id,user['id']))
    return {'ok':True}
