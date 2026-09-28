"""Build auditable licensed question manifest from cached online originals.
No model-generated or template-expanded questions; rejects absent keys/images.
"""
from pathlib import Path
import sys,json,csv,re,hashlib,tarfile,collections,unicodedata
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'data/open_sources'
sys.path.insert(0,str(ROOT/'data/import_tools'))
from bs4 import BeautifulSoup
from pylatexenc.latex2text import LatexNodes2Text
import pyarrow.parquet as pq
BANK=collections.defaultdict(list)
def norm(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',s)).strip()
def add(subject,stem,opts,answer,dataset,config,item,url,license,explanation='',qtype='单选题'):
    excluded={'C语言':{'69'},'软件工程':{'96','94'},'信息安全':{'86'},'公共管理':{'44','87'},'数据结构':{'Exercises__Binary__TPreorder2MCQ'}}
    if str(item) in excluded.get(subject,set()):return
    if len(BANK[subject])>=250:return
    if not stem.strip() or not str(answer).strip():return
    if qtype=='单选题' and (len(opts)<2 or len(set(map(norm,opts)))!=len(opts) or answer not in opts):return
    if re.search(r'!\[|<img|epsfbox|如图|下图|图示|图中|见图',stem):return
    if any(norm(x['stem'])==norm(stem) for x in BANK[subject]):return
    BANK[subject].append(dict(subject=subject,stem=stem.strip(),options=opts,answer=answer,dataset=dataset,config=config,source_item=str(item),url=url,license=license,explanation=explanation,type=qtype))
def ceval(subject,config,predicate=lambda r:True):
 for r in json.loads((P/f'ceval_{config}.json').read_text(encoding='utf8')):
  if r.get('answer') not in 'ABCD' or not predicate(r):continue
  opts=[r[k] for k in 'ABCD'];add(subject,r['question'],opts,opts['ABCD'.index(r['answer'])],'C-Eval',config,r['id'],f'https://huggingface.co/datasets/ceval/ceval-exam/viewer/{config}/test?row={r["id"]}','CC BY-NC-SA 4.0',r.get('explanation',''))
def cm(subject,config,predicate=lambda r:True):
 for r in csv.DictReader((P/f'cmmlu_{config}.csv').read_text(encoding='utf8').splitlines()):
  if r.get('Answer') not in 'ABCD' or not predicate(r):continue
  opts=[r[k] for k in 'ABCD'];add(subject,r['Question'],opts,opts['ABCD'.index(r['Answer'])],'CMMLU',config,r[''],f'https://github.com/haonan-li/CMMLU/blob/master/data/test/{config}.csv#L{int(r[""])+2}','CC BY-NC-SA 4.0')
def linkedin(subject,config):
 text=(P/f'linkedin_{config}.md').read_text(encoding='utf8')
 paths={'c-(programming-language)':'c-(programming-language)-quiz.md'}
 for m in re.finditer(r'^#### Q(\d+)\.\s*(.*?)(?=^#### Q|\Z)',text,re.M|re.S):
  block=m[2]; marks=list(re.finditer(r'^\s*- \[([xX ])\]\s*',block,re.M))
  if len(marks)!=4 or sum(x[1].lower()=='x' for x in marks)!=1:continue
  stem=block[:marks[0].start()].strip();opts=[]
  for i,mark in enumerate(marks):
   segment=block[mark.end():marks[i+1].start() if i+1<len(marks) else len(block)]
   if i==len(marks)-1:
    segment=re.split(r'\n\s*\n(?=\[|\*\*|Explanation|Reference|<|Note|>\s*\*\*Explanation|\d+\.\s*\[Reference)|\n\s*\[(?:Reference|Source)',segment,maxsplit=1)[0]
   opts.append(segment.strip())
  if any('![' in x or len(x)>2500 for x in opts):continue
  # Markdown multiline code options need intact closing fences.
  if any(x.count('```')%2 for x in opts+[stem]):continue
  ans=opts[next(i for i,x in enumerate(marks) if x[1].lower()=='x')]
  url=f'https://github.com/Ebazhanov/linkedin-skill-assessments-quizzes/blob/main/{config}/{paths.get(config,config+"-quiz.md")}#q{m[1]}'
  add(subject,stem,opts,ans,'LinkedIn community',config,m[1],url,'AGPL-3.0','社区题库原始勾选答案；未经逐题专家复核。原文保留，代码不执行。')
def opendsa():
 for p in sorted((P/'opendsa').glob('*.html')):
  s=BeautifulSoup(p.read_text(encoding='utf8'),'html.parser');q=s.select_one('.question');a=s.select_one('.solution');choices=s.select('.choices li')
  if not q or not a or not choices:continue
  if q.find(['var','img','script']) or a.find(['var','img']) or any(o.find(['var','img']) for o in choices):continue
  # Static questions only: dynamic/code references and diagrams cannot be detached.
  parent=q.parent
  if parent.select('div.jsavcanvas, .graph, .vars, img'):continue
  stem=q.get_text(' ',strip=True);answer=a.get_text(' ',strip=True);opts=[o.get_text(' ',strip=True) for o in choices]
  if answer not in opts:opts.insert(0,answer)
  if re.search(r'following (?:code|algorithm|figure|tree|graph)|shown|above|below',stem,re.I) and not q.find('pre'):continue
  folder=p.name.split('__')[1]
  subject='算法' if folder in {'Sorting','AlgAnal','RecurTutor','Background'} else '数据结构'
  path=p.name.replace('__','/');h=s.select_one('.hints')
  add(subject,stem,opts,answer,'OpenDSA',folder,p.stem,'https://github.com/OpenDSA/OpenDSA/blob/master/'+path,'MIT',h.get_text(' ',strip=True) if h else '')
def socratic():
 tex=LatexNodes2Text()
 def clean(x):
  x=re.sub(r'(?m)^%.*$','',x);x=re.sub(r'\\underbar\{file \d+\}','',x);x=re.sub(r'\\[vh]skip\s*\d+pt','',x);x=x.replace('\\item','\n• ')
  # Preserve TeX mathematics verbatim: latex2text drops overline/complement.
  maths=[]
  def hold(m):
   maths.append(m[0]);return ' MATHPLACEHOLDER'+str(len(maths)-1)+'TOKEN '
  x=re.sub(r'\$\$.*?\$\$|\$[^$]*\$',hold,x,flags=re.S)
  x=tex.latex_to_text(x).strip()
  for i,m in enumerate(maths):x=x.replace('MATHPLACEHOLDER'+str(i)+'TOKEN',m)
  return x
 review=[]
 with tarfile.open(P/'socratic.tar.gz') as t:
  for m in t.getmembers():
   if not re.search(r'/\d+\.tex$',m.name):continue
   raw=t.extractfile(m).read().decode('latin1');q=re.search(r'BEGIN_QUESTION\)(.*?)%\(END_QUESTION',raw,re.S);a=re.search(r'BEGIN_ANSWER\)(.*?)%\(END_ANSWER',raw,re.S)
   if not q or not a or re.search(r'epsfbox|includegraphics|PSbox|vbox',q[1]+a[1]):continue
   stem=clean(q[1]);answer=clean(a[1]);
   if len(stem)<30 or len(answer)<12 or re.search(r'let the electrons|research.*your own|I.ll let you|no answer|build something|I.ll leave|far too easy|example circuit|considering their use',answer+' '+stem,re.I):continue
   if Path(m.name).stem in {'01270','01276','02977','02978','02141','02147','02854','02914','02853'}:continue
   dig=bool(re.search(r'boolean|logic gates?|flip.flop|binary|multiplexer|decoder|encoder|latch|\bCMOS\b|\bTTL\b|\bADC\b|\bDAC\b|\bRAM\b|\bROM\b|\bEEPROM\b|\bSRAM\b|\bDRAM\b|memory (?:chip|device|circuit)|analog.to.digital|digital.to.analog|digital (?:circuit|signal|computer|counter|system)|shift register',stem,re.I))
   cir=bool(re.search(r'ohm.s law|kirchhoff|thevenin|norton|superposition|series circuit|parallel circuit|resistan|capacit|inductan|impedance|reactance|voltage|current',stem,re.I))
   if not (dig or cir):continue
   subject='数字电子' if dig else '电路基础';ident=Path(m.name).stem
   add(subject,stem,[],answer,'Socratic Electronics','digital' if dig else 'circuits',ident,f'https://www.ibiblio.org/kuphaldt/socratic/src/{ident}.tex','CC BY 3.0 US','Tony R. Kuphaldt；原始开放问答，TeX转文本；参考答案需人工评分。','简答题')
   review.append((subject,ident,stem))
 (ROOT/'data/socratic_mapping_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
def build():
 mapping={'中国文学':'chinese_language_and_literature','基础生物学':'high_school_biology','大学物理':'college_physics','微观经济学':'college_economics','操作系统':'operating_system','教育学':'education_science','概率统计':'probability_and_statistics','法学基础':'law','计算机组成原理':'computer_architecture','计算机网络':'computer_network','财务管理':'accountant','高等数学':'advanced_mathematics'}
 for sub,cfg in mapping.items():ceval(sub,cfg)
 for sub,cfg in [('C语言','c-(programming-language)'),('Git','git'),('Java','java'),('Python','python'),('数据库','mysql'),('软件工程','agile-methodologies')]:linkedin(sub,cfg)
 cm('信息安全','computer_security');cm('计算机基础','computer_science');cm('普通心理学','professional_psychology')
 cm('公共管理','management');cm('公共管理','public_relations')
 for r in pq.read_table(P/'medmcqa_validation.parquet').to_pylist():
  if r['subject_name']!='Physiology' or r['choice_type']!='single' or r['cop'] not in range(4):continue
  opts=[r['op'+k] for k in 'abcd'];add('人体生理学',r['question'],opts,opts[r['cop']],'MedMCQA','Physiology',r['id'],'https://huggingface.co/datasets/openlifescienceai/medmcqa','Apache-2.0',r.get('exp') or '')
 # NoDerivatives: preserve source question and distractors verbatim, no translation.
 en=json.loads((P/'english_train_exercise_dataset.json').read_text(encoding='utf8'))
 for ident,stem in en['gapped_text'].items():
  opts=[en['solution'][ident]]+en['distractors'][ident]
  if len(opts)!=4:continue
  add('大学英语',stem,opts,en['solution'][ident],'English grammar MCC',en['grammar_topic'][ident],ident,'https://github.com/ZanichelliEditore/english-grammar-multiple-choice-generation/blob/main/dataset/train_exercise_dataset.json','CC BY-NC-ND 4.0','原始公开训练集，语法练习；保留原文，不声称大学考试真题。')
 opendsa();socratic()
 result={s:rows[:100] for s,rows in BANK.items()}
 (ROOT/'data/question_bank_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({s:{'available':len(BANK[s]),'selected':len(rows)} for s,rows in result.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':build()
