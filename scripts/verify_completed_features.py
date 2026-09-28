"""Live end-to-end acceptance for AI, knowledge and practice modules."""
from pathlib import Path
import json,secrets,sys,time
import httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app import core
BASE='http://127.0.0.1:8765/api'; email=f'feature-{secrets.token_hex(6)}@example.test'; password=secrets.token_urlsafe(20); uid=''
checks=[]
def ok(name,condition,detail=''):
 checks.append({'name':name,'passed':bool(condition),'detail':detail});assert condition,f'{name}: {detail}'
with httpx.Client(base_url=BASE,trust_env=False,timeout=240) as c:
 reg=c.post('/auth/register',json={'email':email,'password':password,'display_name':'功能验收账户'});reg.raise_for_status();data=reg.json();uid=data['user']['id'];h={'Authorization':'Bearer '+data['access_token']}
 try:
  settings=c.get('/settings/ai',headers=h).json();ok('真实AI已配置',settings.get('configured') is True,settings.get('model',''))
  kb=c.post('/knowledge-bases',headers=h,json={'name':'数据库验收库','description':'事务与并发控制'}).json();kid=kb['id']
  files={'file':('事务资料.txt','事务具有原子性、一致性、隔离性和持久性。串行化隔离级别可以避免脏读、不可重复读和幻读。两阶段锁协议用于并发控制。'.encode('utf-8'),'text/plain')}
  doc=c.post('/documents/upload',headers=h,files=files);doc.raise_for_status();did=doc.json()['id'];ok('真实TXT解析',doc.json()['status']=='ready')
  link=c.patch(f'/documents/{did}/knowledge-base',headers=h,json={'knowledge_base_id':kid,'folder':'验收'});link.raise_for_status()
  index=c.post(f'/documents/{did}/index',headers=h);index.raise_for_status();ok('本地中文向量索引',index.json()['retrieval_mode']=='semantic',str(index.json()))
  detail=c.get(f'/knowledge-bases/{kid}',headers=h);detail.raise_for_status();d=detail.json();ok('知识库详情聚合',len(d['documents'])==1 and d['documents'][0]['index_mode']=='semantic')
  rag=c.post('/knowledge/query',headers=h,json={'question':'事务有哪些特性？','knowledge_base_id':kid});rag.raise_for_status();rd=rag.json();ok('RAG带引用回答',bool(rd['citations']) and '原子性' in rd['answer'],rd['answer'][:100])
  conv=c.post('/conversations',headers=h,json={'title':'知识库问答验收','mode':'tutor'}).json();cid=conv['id']
  with c.stream('POST',f'/conversations/{cid}/messages',headers=h,json={'content':'根据资料，用一句话说明事务特性。','knowledge_base_id':kid}) as s:
   ok('AI流式HTTP',s.status_code==200,str(s.status_code));body=''.join(s.iter_text())
  ok('AI流式事件完整',all(x in body for x in ['event: message_start','event: token','event: message_end']))
  msgs=c.get(f'/conversations/{cid}/messages',headers=h).json();assistant=next(x for x in msgs if x['role']=='assistant');ok('AI知识库回答落库',assistant['status']=='completed' and len(assistant['content'])>3,assistant['content'][:80])
  questions=c.post('/questions/generate',headers=h,json={'subject':'事务 特性 隔离性 并发控制','type':'单选题','difficulty':'简单','count':5,'knowledge_base_id':kid})
  if questions.is_error: print('QUESTION_ERROR',questions.status_code,questions.text,flush=True)
  questions.raise_for_status();qs=questions.json();ok('知识库AI出题',len(qs)==5,str(len(qs)))
  answer=c.post(f"/questions/{qs[0]['id']}/answer",headers=h,json={'answer':qs[0]['options'][0]});answer.raise_for_status();ok('确定性评分落库',answer.json()['grading_method']=='objective_exact_rule')
  stat=c.get('/questions/stats/overview',headers=h);stat.raise_for_status();sd=stat.json();ok('题库统计',sd['total']==5 and sd['answered']==1,str(sd))
  delete=c.delete(f"/questions/{qs[0]['id']}",headers=h);delete.raise_for_status();ok('题目删除',delete.json()['ok'] is True)
 finally:
  if uid:
   with core.db() as db: db.execute('DELETE FROM users WHERE id=?',(uid,))
out=ROOT/'data'/'verification'/'feature-completion.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':len(checks),'report':str(out)},ensure_ascii=False))
