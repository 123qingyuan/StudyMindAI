"""Read-only verification of all accounts, categories and actual list handler."""
import import_open_question_bank as bank
from app.agent.question_bank import list_questions
from collections import Counter
import hashlib,json
manifest=json.loads((bank.ROOT/'data/question_bank_manifest.json').read_text(encoding='utf8'))
with bank.core.db() as db:
 users=db.execute("SELECT id FROM users WHERE email NOT LIKE '%@example.test' AND email NOT LIKE 'local-ui-%'").fetchall()
result=[]
for user in users:
 for subject,expected in manifest.items():
  actual=list_questions(subject=subject,user=user)
  stems={bank.normalize(q['stem']) for q in actual}
  assert all(bank.normalize(q['stem']) in stems for q in expected),(subject,len(stems))
  assert all('answer' not in q and 'answer_json' not in q and 'explanation' not in q for q in actual)
  result.append({'account':hashlib.sha256(user['id'].encode()).hexdigest()[:12],'subject':subject,'handler_visible_distinct':len(stems),'manifest_visible':100,'answer_leak':False})
checksums={str(p.relative_to(bank.ROOT/'data')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (bank.ROOT/'data/open_sources').rglob('*') if p.is_file()}
report={'readback':'actual question list route handler against MySQL; not browser/auth HTTP test','account_subject_checks':len(result),'checks':result,'source_sha256':checksums,'source_question_count':sum(len(v) for v in manifest.values()),'datasets':dict(Counter(r['dataset'] for rows in manifest.values() for r in rows))}
(bank.ROOT/'data/question_bank_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks','source_sha256']},ensure_ascii=False))
