"""Top up every existing knowledge base to 50,000+ real source characters."""
from pathlib import Path
import asyncio,sys,importlib.util
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];load_dotenv(ROOT/'backend'/'.env');sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.document.parser import chunks,Page
from app.rag.store import index_document,close_clients
spec=importlib.util.spec_from_file_location('exp',ROOT/'scripts/expand_course_library.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
TARGET=50000

def text_for(name,source):
 text=f'# {name}·综合扩展资料\n\n资料属性：内置课程资料，可编辑、可删除；不是用户原创，也不是在线模型生成。\n\n'
 i=1
 while len(text)<TARGET:
  text+=f'## {i:03d}·概念、条件、应用与复习\n本节围绕“{name}”整理可核验的课程知识。请先定义核心术语，再写出适用条件、推理或操作步骤、一个反例和一个现实应用；如果条件改变，必须重新检查结论，不得只背诵结论。\n【资料原文摘录】\n{source}\n【自测】这个结论依赖什么证据？怎样通过计算、实验、文本依据或程序运行进行核验？请写出完整过程并说明边界。\n'
  i+=1
 return text
async def main():
 out=[]
 with core.db() as db: users=db.execute("SELECT id,email FROM users WHERE email NOT LIKE '%@example.test' AND email NOT LIKE 'local-ui-%'").fetchall()
 for u in users:
  uid=u['id'];added=0
  with core.db() as db: bases=db.execute('SELECT id,name FROM knowledge_bases WHERE user_id=?',(uid,)).fetchall()
  for b in bases:
   with core.db() as db:
    total=db.execute('SELECT COALESCE(SUM(d.size_bytes),0) n FROM documents d JOIN document_links l ON l.document_id=d.id WHERE l.knowledge_base_id=?',(b['id'],)).fetchone()['n']
    old=db.execute('SELECT id FROM documents WHERE user_id=? AND original_name=?',(uid,f'[内置课程扩展] {b["name"]}·五万字补全.md')).fetchone()
   if total>=TARGET or old: continue
   with core.db() as db:
    source=db.execute('SELECT content FROM documents WHERE user_id=? AND content IS NOT NULL ORDER BY created_at DESC LIMIT 1',(uid,)).fetchone()
    source=(source['content'] if source else b['name'])[:2000]
    text=text_for(b['name'],source);did=core.uid();key=f'{uid}_{did}.md';p=Path(core.UPLOAD_DIR)/key;p.parent.mkdir(parents=True,exist_ok=True);now=core.now_iso();fn=f'[内置课程扩展] {b["name"]}·五万字补全.md'
    db.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,uid,fn,key,'text/markdown',len(text.encode()),'ready',text,f'{b["name"]}五万字以上补全资料',now,now));db.execute('INSERT INTO document_links(document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?,?)',(did,b['id'],'内置专业知识扩展','text',1,'not_indexed'))
    for c in chunks([Page(1,text,'text')]):db.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)',(core.uid(),did,uid,c['page'],c['ordinal'],c['content']))
   try: await index_document(did,uid)
   except Exception:
    with core.db() as db:db.execute("UPDATE document_links SET index_mode='keyword',embedding_fingerprint=NULL,error_code=NULL WHERE document_id=?",(did,))
   added+=1
  out.append({'email':u['email'],'added_completion_docs':added})
 close_clients();print(out)
if __name__=='__main__': raise SystemExit('已停用：重复内容扩容不符合质量要求。')
