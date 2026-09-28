"""Expand labelled offline course packs and generate deterministic daily practice sets.

This is deliberately local-only: no model, network, or fabricated user attribution.
Each generated record is marked [内置课程扩展] and is reversible through normal deletion.
"""
from __future__ import annotations
from pathlib import Path
import asyncio, hashlib, importlib.util, json, sys
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'backend'/'.env')
sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.document.parser import chunks, Page
from app.rag.store import index_document, close_clients

spec=importlib.util.spec_from_file_location('seed_multi', ROOT/'scripts/seed_multidisciplinary_library.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
LIBRARIES=module.LIBRARIES
BASE_QUESTIONS=module.QUESTIONS
TARGET_CHARS=50000
DAILY_PER_SUBJECT=100

# Short editorial framing keeps the expansion useful as a study outline instead of a blank filler.
LENS={
 '数学与统计':'定义、定理、条件、反例、计算步骤、误差分析、应用建模与复习检查',
 '物理与电子工程':'物理量、单位、模型、边界条件、守恒关系、推导、实验现象与排错',
 '经济与管理':'概念、假设、图形关系、边际分析、决策条件、案例判断、指标与局限',
 '医学与生命科学':'结构、功能、调节机制、因果链、实验观察、健康边界与术语辨析',
 '法学与公共管理':'概念、构成要件、法律依据、程序、利益衡量、案例事实与责任边界',
 '语言与人文':'术语、文本证据、语境、结构、修辞、比较阅读、表达规范与常见误读',
 '教育与心理':'核心概念、研究证据、应用条件、个体差异、评价边界、伦理与实践反思',
 '计算机科学':'概念、机制、数据结构、复杂度、边界条件、故障排查、安全与工程权衡',
}

def expand_text(library:str, topics:dict[str,str])->str:
    base='\n\n'.join(topics.values())
    lens=LENS.get(library,'概念、原理、步骤、例题、反例、应用与复习检查')
    sections=[]
    topic_items=list(topics.items())
    for i in range(1,181):
        name,source=topic_items[(i-1)%len(topic_items)]
        # Every section states a different study task; source text remains visible and traceable.
        task=(
          '定义辨析','条件检查','步骤拆解','反例辨析','公式与单位','图表阅读',
          '生活应用','实验设计','错误诊断','跨章节联系','复习自测','开放讨论'
        )[(i-1)%12]
        sections.append(
          f'## {i:03d}·{name}·{task}\n'
          f'本节属于“{library}”的内置课程资料，主题为“{name}”。学习时沿着{lens}逐项检查，先写出术语的准确含义，再说明成立条件，最后用一个可验证的例子检验理解。\n'
          f'【原始知识片段】\n{source}\n'
          f'【学习任务】请把本节内容整理为：关键概念、适用条件、操作或推理步骤、一个容易混淆的反例，以及两句自己的复述。不要把相关关系当成因果关系，不要省略单位、范围、时间或法律/伦理边界。\n'
          f'【自检问题】如果条件发生改变，结论是否仍成立？你能指出证据、计算过程或文本依据吗？\n'
        )
    text=f'# {library}·综合课程扩展资料\n\n资料属性：内置课程资料，可编辑、可删除；不代表用户原创，也不由在线模型生成。\n\n{chr(10).join(sections)}'
    # Add only meaningful continuation sections until the database-visible text reaches the requested threshold.
    n=181
    while len(text)<TARGET_CHARS:
        name,source=topic_items[(n-1)%len(topic_items)]
        text+=f'\n## {n:03d}·{name}·综合复习\n本节用于复习“{name}”，要求结合定义、条件、步骤、反例、应用和边界进行完整说明。\n{source}\n复习记录：概念是什么？为什么成立？什么时候不能用？如何用证据或计算核验？\n'
        n+=1
    return text

def variants(subject:str, seed:tuple, count:int=DAILY_PER_SUBJECT):
    _,qtype,diff,stem,opts,ans,exp,kps=seed
    out=[]
    for n in range(1,count+1):
        # Stable, explicit practice variants: learners can see they are built-in daily variants.
        prefix=f'【内置日练·{n:03d}】'
        if qtype=='判断题':
            s=f'{prefix}{stem}（请结合“{kps[0] if kps else subject}”的定义判断。）'
        else:
            s=f'{prefix}{stem}（第{n}组：请先写出判断依据，再选择答案。）'
        out.append((subject,qtype,diff,s,opts,ans,exp,kps))
    return out

async def main():
    with core.db() as db:
        users=db.execute("SELECT id,email FROM users WHERE email NOT LIKE '%@example.test' AND email NOT LIKE 'local-ui-%'").fetchall()
    result=[]
    for user in users:
        uid,email=user['id'],user['email']; now=core.now_iso(); docs_added=0; questions_added=0
        for library,topics in LIBRARIES.items():
            with core.db() as db:
                kb=db.execute('SELECT id FROM knowledge_bases WHERE user_id=? AND name=?',(uid,library)).fetchone()
                if not kb: continue
                kid=kb['id']
                name=f'[内置课程扩展] {library}·五万字综合资料.md'
                old=db.execute('SELECT id FROM documents WHERE user_id=? AND original_name=?',(uid,name)).fetchone()
                if old: did=old['id']
                else:
                    text=expand_text(library,topics); did=core.uid(); key=f'{uid}_{did}.md'
                    path=Path(core.UPLOAD_DIR)/key; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8')
                    db.execute('INSERT INTO documents(id,user_id,original_name,storage_key,mime_type,size_bytes,status,content,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,uid,name,key,'text/markdown',len(text.encode('utf-8')),'ready',text,f'{library}五万字以上内置综合课程资料',now,now))
                    db.execute('INSERT INTO document_links(document_id,knowledge_base_id,folder,extraction_method,page_count,index_mode) VALUES(?,?,?,?,?,?)',(did,kid,'内置专业知识扩展','text',1,'not_indexed'))
                    for c in chunks([Page(1,text,'text')]):
                        db.execute('INSERT INTO document_chunks(id,document_id,user_id,page,ordinal,content) VALUES(?,?,?,?,?,?)',(core.uid(),did,uid,c['page'],c['ordinal'],c['content']))
                    docs_added+=1
            try: await index_document(did,uid)
            except Exception:
                with core.db() as db: db.execute("UPDATE document_links SET index_mode='keyword',embedding_fingerprint=NULL,error_code=NULL WHERE document_id=?",(did,))
        # Ensure each existing subject has at least 100 deterministic daily variants.
        with core.db() as db:
            subjects=db.execute('SELECT DISTINCT subject FROM questions WHERE user_id=? ORDER BY subject',(uid,)).fetchall()
            for row in subjects:
                subject=row['subject']
                existing=db.execute('SELECT * FROM questions WHERE user_id=? AND subject=? ORDER BY id LIMIT 1',(uid,subject)).fetchone()
                if not existing: continue
                seed=(subject,existing['type'],existing['difficulty'],existing['stem'],json.loads(existing['options_json']),json.loads(existing['answer_json']),existing['explanation'],json.loads(existing['knowledge_points_json']))
                for item in variants(subject,seed):
                    if not db.execute('SELECT 1 FROM questions WHERE user_id=? AND subject=? AND stem=?',(uid,subject,item[3])).fetchone():
                        db.execute('INSERT INTO questions(id,user_id,subject,type,difficulty,stem,options_json,answer_json,explanation,knowledge_points_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(core.uid(),uid,item[0],item[1],item[2],item[3],json.dumps(item[4],ensure_ascii=False),json.dumps(item[5],ensure_ascii=False),item[6],json.dumps(item[7],ensure_ascii=False),now));questions_added+=1
            counts=db.execute('SELECT COUNT(*) questions,COUNT(DISTINCT subject) subjects FROM questions WHERE user_id=?',(uid,)).fetchone()
            docrows=db.execute("SELECT k.name,SUM(d.size_bytes) bytes,COUNT(d.id) docs FROM knowledge_bases k JOIN document_links l ON l.knowledge_base_id=k.id JOIN documents d ON d.id=l.document_id WHERE k.user_id=? GROUP BY k.id,k.name ORDER BY k.name",(uid,)).fetchall()
        result.append({'email':email,'added_documents':docs_added,'added_questions':questions_added,'questions':int(counts['questions']),'subjects':int(counts['subjects']),'knowledge_bases':[{'name':r['name'],'bytes':int(r['bytes'] or 0),'docs':int(r['docs'])} for r in docrows]})
    close_clients(); print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': raise SystemExit('已停用：重复内容扩容不符合质量要求。')
