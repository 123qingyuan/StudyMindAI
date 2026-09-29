"""Learning management: deterministic data, dates and ownership, no fake AI."""
from __future__ import annotations
import json
from datetime import date, datetime, time as daytime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query
from pydantic import Field, field_validator, model_validator
from .core import StrictModel, current_user, db, uid, now_iso, ensure_owner, fail, local_now

router=APIRouter(prefix='/api')

class TaskIn(StrictModel):
    title:str=Field(min_length=1,max_length=120)
    description:str=Field(default='',max_length=5000)
    status:Literal['todo','doing','done']='todo'
    priority:int=Field(default=2,ge=1,le=3)
    due_date:date|None=None
    category:str=Field(default='学习',max_length=50)
    tags:list[str]=Field(default_factory=list,max_length=12)
    estimated_minutes:int=Field(default=30,ge=1,le=1440)
    @field_validator('due_date',mode='before')
    @classmethod
    def empty_date(cls,v): return v or None
    @field_validator('tags')
    @classmethod
    def tags_valid(cls,v):
        if any(not x.strip() or len(x)>30 for x in v): raise ValueError('标签须为1至30字')
        return list(dict.fromkeys(x.strip() for x in v))

class TaskPatch(StrictModel):
    title:str|None=Field(default=None,min_length=1,max_length=120)
    description:str|None=Field(default=None,max_length=5000)
    status:Literal['todo','doing','done']|None=None
    priority:int|None=Field(default=None,ge=1,le=3)
    due_date:date|None=None
    category:str|None=Field(default=None,max_length=50)
    tags:list[str]|None=None
    estimated_minutes:int|None=Field(default=None,ge=1,le=1440)
    @field_validator('due_date',mode='before')
    @classmethod
    def empty_date(cls,v): return v or None

class CourseIn(StrictModel):
    name:str=Field(min_length=1,max_length=80)
    teacher:str=Field(default='',max_length=80)
    classroom:str=Field(default='',max_length=120)
    weekday:int=Field(default=1,ge=1,le=7)
    start_time:daytime=daytime(8)
    end_time:daytime=daytime(9,40)
    start_week:int=Field(default=1,ge=1,le=60)
    end_week:int=Field(default=20,ge=1,le=60)
    week_pattern:Literal['all','odd','even']='all'
    term_start_date:date|None=None
    @field_validator('term_start_date',mode='before')
    @classmethod
    def empty_term(cls,v): return v or None
    @model_validator(mode='after')
    def bounds(self):
        if self.end_time<=self.start_time or self.end_week<self.start_week: raise ValueError('结束时间或周数不能早于开始')
        return self
class ExamIn(StrictModel):
    subject:str=Field(min_length=1,max_length=80)
    exam_date:date
    location:str=Field(default='',max_length=160)
    notes:str=Field(default='',max_length=5000)
class RecordIn(StrictModel):
    subject:str=Field(min_length=1,max_length=80)
    minutes:int=Field(ge=1,le=1440)
    studied_at:datetime|None=None
    note:str=Field(default='',max_length=5000)
class PlanIn(StrictModel):
    title:str=Field(min_length=1,max_length=120)
    goal:str=Field(min_length=1,max_length=3000)
    start_date:date
    end_date:date
    daily_minutes:int=Field(ge=1,le=1440)
    @model_validator(mode='after')
    def bounds(self):
        if self.end_date<self.start_date or (self.end_date-self.start_date).days>365: raise ValueError('计划范围须在一年以内')
        return self
class PlanItemPatch(StrictModel):
    title:str|None=Field(default=None,min_length=1,max_length=120)
    description:str|None=Field(default=None,max_length=5000)
    plan_date:date|None=None
    estimated_minutes:int|None=Field(default=None,ge=1,le=1440)
    status:Literal['todo','doing','done']|None=None
class FocusIn(StrictModel):
    subject:str=Field(min_length=1,max_length=80)


def encode(values):
    result={}
    for k,v in values.items():
        if isinstance(v,(datetime,date,daytime)): v=v.isoformat()
        if isinstance(v,list): v=json.dumps(v,ensure_ascii=False)
        result[k]=v
    return result

def task_public(item,user):
    data=dict(item)
    data['tags']=json.loads(data.get('tags') or '[]')
    data['overdue']=bool(data['status']!='done' and data.get('due_date') and data['due_date']<local_now(user).date().isoformat())
    return data

def create_owned(table,payload,user):
    values=encode(payload.model_dump());values.update(id=uid(),user_id=user['id'],created_at=now_iso(),updated_at=now_iso())
    with db() as conn:
        fields=','.join(values);marks=','.join('?' for _ in values)
        conn.execute(f'INSERT INTO {table}({fields}) VALUES({marks})',tuple(values.values()))
        return ensure_owner(conn,table,values['id'],user['id'])

def replace_owned(table,item_id,payload,user):
    values=encode(payload.model_dump()); values['updated_at']=now_iso()
    with db() as conn:
        ensure_owner(conn,table,item_id,user['id'])
        fields=','.join(f'{k}=?' for k in values)
        conn.execute(f'UPDATE {table} SET {fields} WHERE id=? AND user_id=?',(*values.values(),item_id,user['id']))
        return ensure_owner(conn,table,item_id,user['id'])

def delete_owned(table,item_id,user):
    with db() as conn:
        ensure_owner(conn,table,item_id,user['id'])
        conn.execute(f'DELETE FROM {table} WHERE id=? AND user_id=?',(item_id,user['id']))
    return {'ok':True}

@router.get('/tasks')
def tasks(user=Depends(current_user),status:str|None=None):
    with db() as conn: values=conn.execute('SELECT * FROM tasks WHERE user_id=? ORDER BY priority,due_date,created_at DESC',(user['id'],)).fetchall()
    result=[task_public(x,user) for x in values]
    if status: result=[x for x in result if x['status']==status or status=='overdue' and x['overdue']]
    return result
@router.post('/tasks',status_code=201)
def new_task(payload:TaskIn,user=Depends(current_user)):
    result=create_owned('tasks',payload,user)
    if result['status']=='done':
        with db() as conn: conn.execute('UPDATE tasks SET completed_at=? WHERE id=?',(now_iso(),result['id']))
    return task_public(result,user)
@router.get('/tasks/{task_id}')
def get_task(task_id:str,user=Depends(current_user)):
    with db() as conn: return task_public(ensure_owner(conn,'tasks',task_id,user['id']),user)
@router.patch('/tasks/{task_id}')
def patch_task(task_id:str,payload:TaskPatch,user=Depends(current_user)):
    values=payload.model_dump(exclude_unset=True)
    if any(v is None and k!='due_date' for k,v in values.items()): fail(422,'NULL_NOT_ALLOWED','此字段不能为空')
    with db() as conn:
        previous=ensure_owner(conn,'tasks',task_id,user['id'])
        merged=TaskIn(**{k: (json.loads(previous[k]) if k=='tags' else previous[k]) for k in TaskIn.model_fields}|values)
        updates=encode(merged.model_dump());updates['updated_at']=now_iso()
        updates['completed_at']=(previous['completed_at'] or now_iso()) if updates['status']=='done' else None
        fields=','.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE tasks SET {fields} WHERE id=? AND user_id=?',(*updates.values(),task_id,user['id']))
        return task_public(ensure_owner(conn,'tasks',task_id,user['id']),user)
@router.post('/tasks/{task_id}/complete')
def complete_task(task_id:str,user=Depends(current_user)): return patch_task(task_id,TaskPatch(status='done'),user)
@router.delete('/tasks/{task_id}')
def remove_task(task_id:str,user=Depends(current_user)): return delete_owned('tasks',task_id,user)

@router.get('/courses')
def courses(user=Depends(current_user)):
    with db() as conn: return conn.execute('SELECT * FROM courses WHERE user_id=? ORDER BY weekday,start_time',(user['id'],)).fetchall()
@router.post('/courses',status_code=201)
def new_course(payload:CourseIn,user=Depends(current_user)): return create_owned('courses',payload,user)
@router.patch('/courses/{course_id}')
@router.put('/courses/{course_id}')
def patch_course(course_id:str,payload:CourseIn,user=Depends(current_user)): return replace_owned('courses',course_id,payload,user)
@router.delete('/courses/{course_id}')
def remove_course(course_id:str,user=Depends(current_user)): return delete_owned('courses',course_id,user)
@router.get('/exams')
def exams(user=Depends(current_user)):
    with db() as conn: return conn.execute('SELECT * FROM exams WHERE user_id=? ORDER BY exam_date',(user['id'],)).fetchall()
@router.post('/exams',status_code=201)
def new_exam(payload:ExamIn,user=Depends(current_user)): return create_owned('exams',payload,user)
@router.patch('/exams/{exam_id}')
@router.put('/exams/{exam_id}')
def patch_exam(exam_id:str,payload:ExamIn,user=Depends(current_user)): return replace_owned('exams',exam_id,payload,user)
@router.delete('/exams/{exam_id}')
def remove_exam(exam_id:str,user=Depends(current_user)): return delete_owned('exams',exam_id,user)

@router.get('/study-records')
def records(user=Depends(current_user)):
    with db() as conn: return conn.execute('SELECT * FROM study_records WHERE user_id=? ORDER BY studied_at DESC LIMIT 1000',(user['id'],)).fetchall()
@router.post('/study-records',status_code=201)
def record(payload:RecordIn,user=Depends(current_user)):
    when=payload.studied_at or datetime.now(timezone.utc)
    if when.tzinfo is None: when=when.replace(tzinfo=ZoneInfo(user['timezone']))
    when=when.astimezone(timezone.utc)
    if when>datetime.now(timezone.utc)+timedelta(minutes=1): fail(422,'FUTURE_RECORD','不能记录未来学习时间')
    record_id=uid()
    with db() as conn:
        conn.execute('INSERT INTO study_records(id,user_id,subject,minutes,studied_at,note) VALUES(?,?,?,?,?,?)',(record_id,user['id'],payload.subject,payload.minutes,when.isoformat(),payload.note))
        return ensure_owner(conn,'study_records',record_id,user['id'])
@router.delete('/study-records/{record_id}')
def remove_record(record_id:str,user=Depends(current_user)): return delete_owned('study_records',record_id,user)
@router.post('/focus/start')
def start_focus(payload:FocusIn,user=Depends(current_user)):
    with db() as conn:
        found=conn.execute('SELECT id FROM focus_sessions WHERE user_id=? AND ended_at IS NULL',(user['id'],)).fetchone()
        if found: fail(409,'FOCUS_ACTIVE','已有一段学习计时未结束')
        focus_id=uid();conn.execute('INSERT INTO focus_sessions(id,user_id,subject,started_at) VALUES(?,?,?,?)',(focus_id,user['id'],payload.subject,now_iso()))
        return ensure_owner(conn,'focus_sessions',focus_id,user['id'])
@router.post('/focus/{focus_id}/stop')
def stop_focus(focus_id:str,user=Depends(current_user)):
    with db() as conn:
        focus=ensure_owner(conn,'focus_sessions',focus_id,user['id'])
        if focus['ended_at']: fail(409,'FOCUS_ENDED','计时已经结束')
        minutes=int((datetime.now(timezone.utc)-datetime.fromisoformat(focus['started_at'])).total_seconds()//60)
        if minutes<1: fail(422,'FOCUS_TOO_SHORT','计时不足一分钟，尚不能计入学习时长')
        if minutes>1440: fail(422,'FOCUS_TOO_LONG','计时超过一天，请手动记录有效学习时长')
        rid=uid();ended=now_iso()
        changed=conn.execute('UPDATE focus_sessions SET ended_at=?,record_id=? WHERE id=? AND ended_at IS NULL',(ended,rid,focus_id))
        if changed.rowcount!=1: fail(409,'FOCUS_ENDED','计时已经结束')
        conn.execute('INSERT INTO study_records(id,user_id,subject,minutes,studied_at,note) VALUES(?,?,?,?,?,?)',(rid,user['id'],focus['subject'],minutes,ended,'专注计时'))
        return ensure_owner(conn,'study_records',rid,user['id'])


def plan_with_items(conn,plan_id,user_id):
    plan=ensure_owner(conn,'study_plans',plan_id,user_id)
    plan['items']=conn.execute('SELECT * FROM study_plan_items WHERE study_plan_id=? ORDER BY plan_date,created_at',(plan_id,)).fetchall()
    return plan
@router.get('/study-plans')
def plans(user=Depends(current_user)):
    with db() as conn:
        ids=conn.execute('SELECT id FROM study_plans WHERE user_id=? ORDER BY created_at DESC',(user['id'],)).fetchall()
        return [plan_with_items(conn,p['id'],user['id']) for p in ids]
@router.post('/study-plans',status_code=201)
def new_plan(payload:PlanIn,user=Depends(current_user)):
    values=encode(payload.model_dump());pid=uid();ts=now_iso()
    with db() as conn:
        conn.execute('INSERT INTO study_plans(id,user_id,title,goal,start_date,end_date,daily_minutes,status,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,user['id'],payload.title,payload.goal,values['start_date'],values['end_date'],payload.daily_minutes,'draft','manual',ts,ts))
        for offset in range((payload.end_date-payload.start_date).days+1):
            day=payload.start_date+timedelta(days=offset)
            conn.execute('INSERT INTO study_plan_items(id,study_plan_id,plan_date,title,description,estimated_minutes,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid(),pid,day.isoformat(),payload.title,payload.goal,payload.daily_minutes,'todo',ts))
        return plan_with_items(conn,pid,user['id'])
@router.patch('/study-plans/{plan_id}/items/{item_id}')
def patch_plan_item(plan_id:str,item_id:str,payload:PlanItemPatch,user=Depends(current_user)):
    values=encode(payload.model_dump(exclude_none=True))
    with db() as conn:
        plan=ensure_owner(conn,'study_plans',plan_id,user['id'])
        item=conn.execute('SELECT * FROM study_plan_items WHERE id=? AND study_plan_id=?',(item_id,plan_id)).fetchone()
        if not item: fail(404,'NOT_FOUND','计划条目不存在')
        if values.get('plan_date') and not plan['start_date']<=values['plan_date']<=plan['end_date']: fail(422,'INVALID_DATE','条目日期须在计划范围内')
        if values:
            fields=','.join(f'{k}=?' for k in values)
            conn.execute(f'UPDATE study_plan_items SET {fields} WHERE id=? AND study_plan_id=?',(*values.values(),item_id,plan_id))
            if item['task_id']:
                linked={('due_date' if k=='plan_date' else k):v for k,v in values.items()}
                linked['updated_at']=now_iso()
                if 'status' in linked: linked['completed_at']=now_iso() if linked['status']=='done' else None
                fields=','.join(f'{k}=?' for k in linked)
                conn.execute(f'UPDATE tasks SET {fields} WHERE id=? AND user_id=?',(*linked.values(),item['task_id'],user['id']))
        return conn.execute('SELECT * FROM study_plan_items WHERE id=?',(item_id,)).fetchone()
@router.post('/study-plans/{plan_id}/publish')
def publish_plan(plan_id:str,user=Depends(current_user)):
    with db() as conn:
        plan=plan_with_items(conn,plan_id,user['id'])
        if plan['status']=='published': return {**plan,'already_published':True}
        changed=conn.execute("UPDATE study_plans SET status='published',updated_at=? WHERE id=? AND user_id=? AND status='draft'",(now_iso(),plan_id,user['id']))
        if changed.rowcount!=1: fail(409,'INVALID_STATE','计划状态已变化')
        for item in plan['items']:
            if item['task_id']: continue
            tid=uid();ts=now_iso()
            conn.execute('INSERT INTO tasks(id,user_id,title,description,status,priority,due_date,category,estimated_minutes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,user['id'],item['title'],item['description'],item['status'],2,item['plan_date'],'学习计划',item['estimated_minutes'],ts,ts))
            conn.execute('UPDATE study_plan_items SET task_id=? WHERE id=?',(tid,item['id']))
        return plan_with_items(conn,plan_id,user['id'])
@router.delete('/study-plans/{plan_id}')
def remove_plan(plan_id:str,user=Depends(current_user)): return delete_owned('study_plans',plan_id,user)


def in_local_day(timestamp,user):
    when=datetime.fromisoformat(timestamp)
    if when.tzinfo is None: when=when.replace(tzinfo=timezone.utc)
    return when.astimezone(ZoneInfo(user['timezone'])).date()
@router.get('/dashboard/summary')
def summary(user=Depends(current_user)):
    current=local_now(user).date(); all_tasks=tasks(user); all_records=records(user); done=sum(t['status']=='done' for t in all_tasks)
    subjects={}
    for r in all_records: subjects[r['subject']]=subjects.get(r['subject'],0)+r['minutes']
    with db() as conn:
        docs=conn.execute('SELECT COUNT(*) AS n FROM documents WHERE user_id=?',(user['id'],)).fetchone()['n']
        convs=conn.execute('SELECT COUNT(*) AS n FROM conversations WHERE user_id=?',(user['id'],)).fetchone()['n']
        question_count=conn.execute("SELECT COUNT(*) AS n FROM questions WHERE user_id=? AND stem NOT LIKE '【内置日练%'",(user['id'],)).fetchone()['n']
        exam=conn.execute('SELECT * FROM exams WHERE user_id=? AND exam_date>=? ORDER BY exam_date LIMIT 1',(user['id'],current.isoformat())).fetchone()
    return {'today':current.isoformat(),'study_minutes':sum(r['minutes'] for r in all_records if in_local_day(r['studied_at'],user)==current),'total_minutes':sum(r['minutes'] for r in all_records),'task_total':len(all_tasks),'task_done':done,'task_rate':round(done/len(all_tasks)*100) if all_tasks else 0,'documents':docs,'questions':question_count,'conversations':convs,'next_exam':exam,'subjects':[{'subject':k,'minutes':v} for k,v in sorted(subjects.items(),key=lambda x:-x[1])],'period':'all_time'}
@router.get('/dashboard/today')
def today_view(user=Depends(current_user)):
    today=local_now(user).date(); iso=today.isoformat()
    chosen=[]
    for course in courses(user):
        if course['weekday']!=today.isoweekday(): continue
        if course.get('term_start_date'):
            first=date.fromisoformat(course['term_start_date']); week=(today-first).days//7+1
            if not course['start_week']<=week<=course['end_week']: continue
            if course['week_pattern']=='odd' and week%2==0 or course['week_pattern']=='even' and week%2!=0: continue
        chosen.append(course)
    return {'tasks':[x for x in tasks(user) if x['status']!='done' and (not x['due_date'] or x['due_date']<=iso)],'courses':chosen,'exams':[x for x in exams(user) if x['exam_date']>=iso]}
@router.get('/analytics/overview')
def analytics(user=Depends(current_user)):
    all_records=records(user);today=local_now(user).date();by_day={};subjects={}
    for r in all_records:
        day=in_local_day(r['studied_at'],user).isoformat();by_day[day]=by_day.get(day,0)+r['minutes'];subjects[r['subject']]=subjects.get(r['subject'],0)+r['minutes']
    with db() as conn:
        result=conn.execute('SELECT COUNT(*) AS n,COALESCE(SUM(q.is_correct),0) AS correct FROM question_records q LEFT JOIN question_reviews r ON r.record_id=q.id WHERE q.user_id=? AND r.record_id IS NULL',(user['id'],)).fetchone()
    trend=[{'day':(today-timedelta(days=i)).isoformat(),'minutes':by_day.get((today-timedelta(days=i)).isoformat(),0)} for i in reversed(range(14))]
    return {'trend':trend,'subjects':[{'subject':k,'minutes':v} for k,v in sorted(subjects.items(),key=lambda x:-x[1])],'question_records':result['n'],'accuracy':round(result['correct']/result['n']*100) if result['n'] else 0,'mastery_status':'数据不足' if result['n']<5 else '基于练习记录','total_minutes':sum(r['minutes'] for r in all_records)}
@router.get('/search')
def search(q:str=Query(min_length=1,max_length=100),user=Depends(current_user)):
    pattern='%'+q+'%'
    with db() as conn:
        documents=conn.execute('SELECT id,original_name,substr(content,1,240) AS snippet FROM documents WHERE user_id=? AND (original_name LIKE ? OR content LIKE ?) LIMIT 30',(user['id'],pattern,pattern)).fetchall()
        notes=conn.execute('SELECT id,title,substr(content,1,240) AS snippet FROM notes WHERE user_id=? AND (title LIKE ? OR content LIKE ?) LIMIT 30',(user['id'],pattern,pattern)).fetchall()
        found_tasks=conn.execute('SELECT * FROM tasks WHERE user_id=? AND (title LIKE ? OR description LIKE ?) LIMIT 30',(user['id'],pattern,pattern)).fetchall()
    return {'documents':documents,'notes':notes,'tasks':[task_public(t,user) for t in found_tasks]}
@router.get('/notifications')
def notifications(user=Depends(current_user)):
    data=today_view(user)
    return [{'id':'task:'+x['id'],'type':'task','title':x['title'],'due_date':x['due_date'],'overdue':x['overdue']} for x in data['tasks']]+[{'id':'exam:'+x['id'],'type':'exam','title':x['subject'],'due_date':x['exam_date']} for x in data['exams']]
