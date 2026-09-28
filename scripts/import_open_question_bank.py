"""Idempotent licensed-manifest import; per-account readback, no emails in output.
Run build_question_manifest.py first. Does not touch application code or vectors.
"""
from __future__ import annotations
import hashlib,json,re,sys,unicodedata,collections
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];load_dotenv(ROOT/'backend/.env');sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.agent.question_bank import validate_question

def normalize(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s)).strip()
def dumps(x):return json.dumps(x,ensure_ascii=False)
def main():
 bank=json.loads((ROOT/'data/question_bank_manifest.json').read_text(encoding='utf8'))
 with core.db() as db:
  subjects={r['subject'] for r in db.execute("SELECT DISTINCT subject FROM questions WHERE stem NOT LIKE '【内置日练%'").fetchall()}
  users=db.execute("SELECT id FROM users WHERE email NOT LIKE '%@example.test' AND email NOT LIKE 'local-ui-%'").fetchall()
 assert set(bank)==subjects,(set(bank)^subjects)
 for subject,rows in bank.items():
  assert len(rows)==100 and len({normalize(r['stem']) for r in rows})==100,subject
  for row in rows:assert validate_question(row,row['type']), (subject,row['source_item'])
 # Preserve attempt history: hide only identifiable previous imported electrical
 # engineer records whose whole-domain mapping to digital electronics was false.
 with core.db() as db:
  old=db.execute("SELECT q.*,s.source_key FROM questions q JOIN question_sources s ON s.question_id=q.id WHERE q.subject='数字电子' AND s.dataset='C-Eval' AND s.config_name='electrical_engineer' AND q.stem NOT LIKE '【内置日练%'").fetchall()
  if old:
   backup=ROOT/'data/legacy_electrical_mapping_backup.json'
   if not backup.exists():backup.write_text(dumps([dict(r) for r in old]),encoding='utf8')
   for row in old:db.execute('UPDATE questions SET stem=? WHERE id=?',('【内置日练隔离：旧电气工程误映射，原题保留】'+row['stem'],row['id']))
 quarantined=len(old)
 added=updated=0
 for user in users:
  uid=user['id']
  with core.db() as db:
   existing=db.execute("SELECT q.*,s.dataset FROM questions q LEFT JOIN question_sources s ON s.question_id=q.id WHERE q.user_id=? AND q.stem NOT LIKE '【内置日练%'",(uid,)).fetchall()
   lookup={(q['subject'],normalize(q['stem'])):q for q in existing}
   for subject,rows in bank.items():
    for r in rows:
     key=hashlib.sha256(f"{uid}|{subject}|{r['dataset']}|{r['config']}|{r['source_item']}".encode()).hexdigest()
     old=lookup.get((subject,normalize(r['stem'])))
     explanation=f"来源：{r['dataset']}；{r['license']}；条目 {r['source_item']}\n{r['url']}\n{r['explanation']}"
     if old:
      if not old['dataset']:continue # Never overwrite user-authored records.
      qid=old['id']
      vals=(r['stem'],dumps(r['options']),dumps(r['answer']),explanation,r['type'])
      current=(old['stem'],old['options_json'],old['answer_json'],old['explanation'],old['type'])
      if vals!=current:
       db.execute('UPDATE questions SET stem=?,options_json=?,answer_json=?,explanation=?,type=? WHERE id=?',(*vals,qid));updated+=1
      db.execute('UPDATE question_sources SET source_url=?,license_name=? WHERE question_id=?',(r['url'],r['license'],qid))
     else:
      qid=core.uid();now=core.now_iso()
      db.execute('INSERT INTO questions(id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(qid,uid,subject,r['type'],'中等',r['stem'],dumps(r['options']),dumps(r['answer']),explanation,dumps([r['config'],'公开来源题库']),now))
      db.execute('INSERT INTO question_sources(question_id,source_key,dataset,config_name,split_name,source_url,license_name,imported_at) VALUES(?,?,?,?,?,?,?,?)',(qid,key,r['dataset'],r['config'],'public',r['url'],r['license'],now));added+=1
 print('Imported',added,'updated',updated,flush=True)
 report={'target_per_subject':100,'account_count':len(users),'subject_count':len(subjects),'imported':added,'updated':updated,'quarantined_legacy_mapping':quarantined,'subjects':{},'all_complete':True,'validation_scope':'Full manifest-vs-MySQL content/answer/option readback; source answers preserved, not independent expert re-solving.'}
 with core.db() as db:
  for subject,rows in bank.items():
   accounts=[]
   for user in users:
    qs=db.execute("SELECT q.*,s.source_url FROM questions q LEFT JOIN question_sources s ON s.question_id=q.id WHERE q.user_id=? AND q.subject=? AND q.stem NOT LIKE '【内置日练%'",(user['id'],subject)).fetchall()
    ix={normalize(q['stem']):q for q in qs};matched=0;errors=[]
    for r in rows:
     q=ix.get(normalize(r['stem']))
     if q and json.loads(q['options_json'])==r['options'] and json.loads(q['answer_json'])==r['answer'] and q['source_url']:matched+=1
     else:errors.append(r['source_item'])
    accounts.append({'account':hashlib.sha256(user['id'].encode()).hexdigest()[:12],'distinct_stems':len(ix),'verified_manifest_items':matched,'mismatches':errors})
   ok=all(x['verified_manifest_items']==100 for x in accounts);report['all_complete'] &= ok
   report['subjects'][subject]={'source_questions':len(rows),'type_counts':dict(collections.Counter(r['type'] for r in rows)),'datasets':dict(collections.Counter(r['dataset'] for r in rows)),'accounts':accounts,'status':'verified' if ok else 'shortage'}
 report['ceval_answer_audit']={p.stem:{'rows':len(rr:=json.loads(p.read_text(encoding='utf8'))),'answer_distribution':dict(collections.Counter(r.get('answer') for r in rr))} for p in (ROOT/'data/open_sources').glob('ceval_*.json')}
 (ROOT/'data/question_bank_import_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({k:v for k,v in report.items() if k not in {'subjects','ceval_answer_audit'}},ensure_ascii=False));assert report['all_complete']
if __name__=='__main__':main()
