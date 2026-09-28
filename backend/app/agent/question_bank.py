"""Strict question generation and grading; answers are withheld until submit."""
from __future__ import annotations
import json
from datetime import date
from typing import Any, Literal
from fastapi import APIRouter, Depends
from pydantic import Field, model_validator
from .. import core
from ..ai.common import StrictModel, connection, dumps, fail, owned, rows


router = APIRouter()
TYPES = {'单选题', '多选题', '判断题', '填空题', '简答题', '编程题'}
DIFFICULTIES = {'简单', '中等', '困难'}
COUNTS = {5, 10, 20, 50}
OBJECTIVE = {'单选题', '多选题', '判断题', '填空题'}


class QuestionGenIn(StrictModel):
    subject: str = Field(min_length=1, max_length=120)
    type: str
    difficulty: str
    count: int
    knowledge_base_id: str | None = None

    @model_validator(mode='after')
    def valid(self):
        if self.type not in TYPES:
            raise ValueError('题型不支持')
        if self.difficulty not in DIFFICULTIES:
            raise ValueError('难度不支持')
        if self.count not in COUNTS:
            raise ValueError('数量必须是 5、10、20 或 50')
        return self


class AnswerIn(StrictModel):
    answer: Any


class ManualQuestionIn(StrictModel):
    subject: str = Field(min_length=1, max_length=120)
    type: str
    difficulty: str
    stem: str = Field(min_length=1, max_length=10000)
    options: list[str] = Field(default_factory=list, max_length=20)
    answer: Any
    explanation: str = Field(default='', max_length=20000)
    knowledge_points: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def valid(self):
        if self.type not in TYPES or self.difficulty not in DIFFICULTIES:
            raise ValueError('题型或难度不支持')
        if not validate_question(self.model_dump(), self.type):
            raise ValueError('题目、选项或答案格式不正确')
        return self


def q_public(item):
    value = dict(item)
    value['options'] = json.loads(value.pop('options_json'))
    value['knowledge_points'] = json.loads(value.pop('knowledge_points_json'))
    value.pop('answer_json', None)
    value.pop('explanation', None)
    return value


def validate_question(item, qtype):
    if not isinstance(item, dict):
        return None
    stem = item.get('stem')
    if not isinstance(stem, str) or not stem.strip() or len(stem) > 10000:
        return None
    options = item.get('options', [])
    if not isinstance(options, list) or len(options) > 20 or any(not isinstance(x, str) or len(x) > 1000 for x in options):
        return None
    answer = item.get('answer')
    if qtype == '单选题' and (not isinstance(answer, str) or answer not in options):
        return None
    if qtype == '多选题' and (not isinstance(answer, list) or not answer or any(x not in options for x in answer)):
        return None
    if qtype == '判断题' and answer not in [True, False, '正确', '错误']:
        return None
    if qtype == '填空题' and not isinstance(answer, (str, list)):
        return None
    if qtype in {'简答题', '编程题'} and not isinstance(answer, str):
        return None
    explanation = item.get('explanation', '')
    points = item.get('knowledge_points', [])
    if not isinstance(explanation, str) or not isinstance(points, list) or any(not isinstance(x, str) for x in points):
        return None
    rubric = item.get('rubric', [])
    if qtype in {'简答题', '编程题'} and (not isinstance(rubric, list) or any(not isinstance(x, str) for x in rubric)):
        return None
    return {'stem': stem.strip(), 'options': options, 'answer': answer, 'explanation': explanation,
            'knowledge_points': points, 'rubric': rubric}



@router.post('/questions/manual')
def create_manual_question(payload: ManualQuestionIn, user=Depends(core.current_user)):
    item = validate_question(payload.model_dump(), payload.type)
    qid, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO questions(id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (qid,user['id'],payload.subject,payload.type,payload.difficulty,item['stem'],dumps(item['options']),dumps(item['answer']),item['explanation'],dumps(item['knowledge_points']),ts))
    return {'id':qid,'subject':payload.subject,'type':payload.type,'difficulty':payload.difficulty,'stem':item['stem'],'options':item['options'],'knowledge_points':item['knowledge_points'],'created_at':ts}


@router.get('/questions')
def list_questions(subject: str | None = None, user=Depends(core.current_user)):
    with connection() as conn:
        if subject:
            found = conn.execute('SELECT * FROM questions WHERE stem NOT LIKE \'【内置日练%\' AND user_id=? AND subject=? ORDER BY created_at DESC LIMIT 200', (user['id'], subject)).fetchall()
        else:
            found = conn.execute('SELECT * FROM questions WHERE stem NOT LIKE \'【内置日练%\' AND user_id=? ORDER BY created_at DESC LIMIT 200', (user['id'],)).fetchall()
    return [q_public(item) for item in found]


@router.get('/questions/daily')
def daily_questions(subject: str | None = None, user=Depends(core.current_user)):
    """Return up to 100 genuine questions per subject; never pad a shortage."""
    today = date.today().isoformat()
    with connection() as conn:
        subjects = [subject] if subject else [r['subject'] for r in conn.execute(
            'SELECT DISTINCT subject FROM questions WHERE stem NOT LIKE \'【内置日练%\' AND user_id=? ORDER BY subject', (user['id'],)).fetchall()]
        result = []
        for item_subject in subjects:
            pool = conn.execute('SELECT * FROM questions WHERE stem NOT LIKE \'【内置日练%\' AND user_id=? AND subject=? ORDER BY id', (user['id'], item_subject)).fetchall()
            if not pool:
                continue
            # Stable daily rotation. A new date changes the 100-item window without randomness or AI.
            offset = int(__import__('hashlib').sha256(f'{user["id"]}:{item_subject}:{today}'.encode()).hexdigest()[:8], 16) % len(pool)
            selected = [pool[(offset + i) % len(pool)] for i in range(min(100, len(pool)))]
            result.extend(q_public(row) for row in selected)
    return {'date': today, 'requested': 100, 'subjects': subjects, 'count': len(result), 'questions': result}


@router.get('/questions/stats/overview')
def question_stats(user=Depends(core.current_user)):
    with connection() as conn:
        totals = conn.execute('SELECT COUNT(*) AS total,COUNT(DISTINCT subject) AS subjects FROM questions WHERE stem NOT LIKE \'【内置日练%\' AND user_id=?', (user['id'],)).fetchone()
        records = conn.execute("""SELECT COUNT(*) AS answered,
            COALESCE(SUM(CASE WHEN v.record_id IS NULL AND r.is_correct=1 THEN 1 ELSE 0 END),0) AS correct,
            COALESCE(SUM(CASE WHEN v.record_id IS NULL THEN 1 ELSE 0 END),0) AS objective,
            AVG(r.score) AS average_score
            FROM question_records r LEFT JOIN question_reviews v ON v.record_id=r.id WHERE r.user_id=?""", (user['id'],)).fetchone()
        by_subject = rows(conn.execute("""SELECT q.subject,COUNT(DISTINCT q.id) AS total,COUNT(r.id) AS answered,
            AVG(r.score) AS average_score FROM questions q LEFT JOIN question_records r ON r.question_id=q.id
            WHERE q.user_id=? AND q.stem NOT LIKE \'【内置日练%\' GROUP BY q.subject ORDER BY answered DESC,total DESC""", (user['id'],)).fetchall())
    return {'total': int(totals['total'] or 0), 'subjects': int(totals['subjects'] or 0),
            'answered': int(records['answered'] or 0), 'objective': int(records['objective'] or 0),
            'correct': int(records['correct'] or 0),
            'accuracy': round(float(records['correct']) / float(records['objective']) * 100) if records['objective'] else None,
            'average_score': round(float(records['average_score']), 1) if records['average_score'] is not None else None,
            'by_subject': by_subject}


@router.get('/questions/{question_id}')
def get_question(question_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        return q_public(owned(conn, 'questions', question_id, user['id']))


@router.delete('/questions/{question_id}')
def delete_question(question_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'questions', question_id, user['id'])
        conn.execute('DELETE FROM questions WHERE id=? AND user_id=?', (question_id, user['id']))
    return {'ok': True}


def normalized(value):
    if isinstance(value, list):
        return sorted(str(v).strip().lower() for v in value)
    return str(value).strip().lower()


def objective_grade(q, answer):
    expected = json.loads(q['answer_json'])
    if q['type'] == '判断题':
        def boolean(value):
            if isinstance(value, bool): return value
            return {'true': True, 'false': False, '正确': True, '错误': False}.get(str(value).strip().lower())
        correct = boolean(expected) is not None and boolean(answer) is boolean(expected)
    elif q['type'] == '填空题':
        expected_values = expected if isinstance(expected, list) else [expected]
        actual_values = answer if isinstance(answer, list) else [answer]
        correct = len(expected_values) == len(actual_values) and all(normalized(a) == normalized(e) for a, e in zip(actual_values, expected_values))
    else:
        correct = normalized(expected) == normalized(answer)
    return (100.0 if correct else 0.0), bool(correct), 'objective_exact_rule'


@router.post('/questions/{question_id}/answer')
async def answer_question(question_id: str, payload: AnswerIn, user=Depends(core.current_user)):
    with connection() as conn:
        q = owned(conn, 'questions', question_id, user['id'])
        rubric_row = conn.execute('SELECT rubric_json FROM question_rubrics WHERE question_id=?', (question_id,)).fetchone()
    if q['type'] in OBJECTIVE:
        score, correct, method = objective_grade(q, payload.answer)
        feedback = q['explanation']
        rubric_scores = []
    else:
        if not isinstance(payload.answer, str) or not payload.answer.strip():
            fail(422, 'ANSWER_REQUIRED', '主观题答案不能为空')
        score, correct, method = 0.0, None, 'self_review'
        feedback = '主观题不自动评分。请对照参考答案与解析自行订正。'
        rubric_scores = []
    record_id, ts = core.uid(), core.now_iso()
    with connection() as conn:
        conn.execute('INSERT INTO question_records(id,user_id,question_id,answer_json,is_correct,score,answered_at) VALUES(?,?,?,?,?,?,?)',
                     (record_id, user['id'], question_id, dumps(payload.answer), 1 if correct is True else 0, float(score), ts))
        if method == 'self_review':
            conn.execute('INSERT INTO question_reviews(record_id,grading_method,feedback,rubric_scores_json) VALUES(?,?,?,?)', (record_id, method, feedback, dumps(rubric_scores)))
    return {'record_id': record_id, 'correct': correct, 'score': score, 'grading_method': method,
            'feedback': feedback, 'explanation': q['explanation'], 'answer': json.loads(q['answer_json'])}


@router.get('/questions/{question_id}/records')
def question_records(question_id: str, user=Depends(core.current_user)):
    with connection() as conn:
        owned(conn, 'questions', question_id, user['id'])
        records = rows(conn.execute('SELECT * FROM question_records WHERE question_id=? AND user_id=? ORDER BY answered_at DESC', (question_id, user['id'])).fetchall())
        for item in records:
            review = conn.execute('SELECT grading_method,feedback,rubric_scores_json FROM question_reviews WHERE record_id=?', (item['id'],)).fetchone()
            if review:
                item['review'] = dict(review)
                item['review']['rubric_scores'] = json.loads(item['review'].pop('rubric_scores_json'))
    return records
