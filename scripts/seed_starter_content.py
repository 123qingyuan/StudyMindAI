"""Add clearly labelled, removable starter content to real StudyMind accounts.
Idempotent: keyed by exact [示例] names and stems.
"""
from pathlib import Path
import json,sys
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'backend'/'.env')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import core
from app.document.parser import chunks, Page
from app.rag.store import index_document,close_clients
import asyncio
USERS=['f070225@gmail.com','f070225@foexl.com']
KB_NAME='[示例] 大学计算机基础'
TEXT='''大学计算机基础复习资料（示例，可随时删除）

一、计算机系统
计算机系统由硬件系统和软件系统组成。硬件包括运算器、控制器、存储器、输入设备和输出设备。CPU 主要由运算器和控制器组成。内存用于暂时存放正在运行的程序和数据，断电后通常会丢失；外存用于长期保存数据。

二、操作系统
操作系统负责管理处理器、存储器、文件和设备等资源，并为应用程序提供运行环境。进程是程序的一次执行过程，线程是进程内的执行单元。并发强调多个任务在一段时间内交替推进，并行强调多个任务在同一时刻执行。

三、数据库基础
关系数据库使用表组织数据。主键用于唯一标识表中的记录，不能重复且不能为空；外键用于建立表之间的关联。事务具有原子性、一致性、隔离性和持久性，简称 ACID。

四、Python 基础
Python 使用缩进表示代码块。列表是有序、可变的序列；元组是有序、通常不可变的序列；字典以键值对存储数据，键应当可哈希。for 循环适合遍历可迭代对象，while 循环适合条件驱动的重复执行。
'''
QUESTIONS=[
 ('计算机基础','单选题','简单','CPU 主要由哪两部分组成？',['运算器和控制器','内存和外存','输入设备和输出设备','操作系统和应用程序'],'运算器和控制器','CPU 的核心组成是运算器与控制器。',['计算机系统']),
 ('计算机基础','判断题','简单','内存中的数据在断电后通常仍会永久保留。',[],False,'内存通常属于易失性存储，断电后数据会丢失。',['存储器']),
 ('数据库','单选题','简单','关系表中用于唯一标识一条记录的字段是？',['主键','外键','索引','视图'],'主键','主键的值必须唯一且不能为空。',['主键']),
 ('数据库','多选题','中等','下列哪些属于事务的 ACID 特性？',['原子性','一致性','隔离性','持久性','随机性'],['原子性','一致性','隔离性','持久性'],'事务的四个基本特性是原子性、一致性、隔离性和持久性。',['事务','ACID']),
 ('Python','单选题','简单','Python 中哪一种数据结构以键值对存储数据？',['字典','列表','元组','集合'],'字典','字典使用 key-value 键值对组织数据。',['字典']),
 ('Python','填空题','中等','Python 使用什么来表示代码块的层级结构？',[],'缩进','Python 依靠一致的缩进划分代码块。',['缩进']),
 ('操作系统','判断题','中等','并发一定要求多个任务在同一时刻执行。',[],False,'并发表示一段时间内交替推进；同一时刻执行属于并行。',['并发','并行']),
 ('计算机网络','单选题','中等','HTTPS 相比 HTTP 主要增加了什么能力？',['传输加密和身份认证','更大的文件容量','自动编译代码','数据库事务'],'传输加密和身份认证','HTTPS 通过 TLS 提供传输加密、完整性保护和服务器身份认证。',['HTTP','HTTPS','TLS']),
]
async def main():
 created=[]
 with core.db() as db:
  users=db.execute('SELECT id,email FROM users WHERE email IN (?,?)',USERS).fetchall()
 for user in users:
  uid,email=user['id'],user['email'];ts=core.now_iso()
  with core.db() as db:
   kb=db.execute('SELECT id FROM knowledge_bases WHERE user_id=? AND name=?',(uid,KB_NAME)).fetchone()
   if kb: kid=kb['id']
   else:
    kid=core.uid();db.execute('INSERT INTO knowledge_bases(id,user_id,name,description,created_at,updated_at) VALUES(?,?,?,?,?,?)',(kid,uid,KB_NAME,'内置入门资料与练习示例，可编辑、补充或直接删除。',ts,ts))
   doc=db.execute("SELECT id FROM documents WHERE user_id=? AND original_name='[示例] 大学计算机基础复习资料.txt'",(uid,)).fetchone()
   if doc: did=doc['id']
   else:
    did=core.uid();storage=f'{uid}_{did}.txt';path=Path(core.UPLOAD_DIR)/storage;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(TEXT,encoding='utf-8')
    db.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,uid,'[示例] 大学计算机基础复习资料.txt',storage,'text/plain',len(TEXT.encode()),'ready',TEXT,'计算机系统、操作系统、数据库与 Python 入门复习资料。',ts,ts))
    db.execute('INSERT INTO document_links(document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?,?)',(did,kid,'示例资料','text',1,'not_indexed'))
    for item in chunks([Page(1,TEXT,'text')]):db.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)',(core.uid(),did,uid,item['page'],item['ordinal'],item['content']))
   if not db.execute("SELECT 1 FROM notes WHERE user_id=? AND title='[示例] 复习使用建议'",(uid,)).fetchone():
    db.execute('INSERT INTO notes(id,user_id,title,content,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(core.uid(),uid,'[示例] 复习使用建议','先阅读资料，再完成题库中的 8 道示例题；错题对应回看知识库原文。此笔记可随时删除。','manual',ts,ts))
   for subject,qtype,difficulty,stem,options,answer,explanation,kps in QUESTIONS:
    if not db.execute('SELECT 1 FROM questions WHERE user_id=? AND stem=?',(uid,stem)).fetchone():
     db.execute('INSERT INTO questions(id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(core.uid(),uid,subject,qtype,difficulty,stem,json.dumps(options,ensure_ascii=False),json.dumps(answer,ensure_ascii=False),explanation,json.dumps(kps,ensure_ascii=False),ts))
  try:
   result=await index_document(did,uid);index_mode=result['retrieval_mode']
  except Exception:
   # A broken personal embedding override must not block starter data; keyword retrieval remains real.
   with core.db() as db: db.execute("UPDATE document_links SET index_mode='keyword',embedding_fingerprint=NULL,error_code=NULL WHERE document_id=?",(did,))
   index_mode='keyword'
  created.append({'email':email,'knowledge_base':kid,'document':did,'questions':len(QUESTIONS),'index':index_mode})
 close_clients();print(json.dumps(created,ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
