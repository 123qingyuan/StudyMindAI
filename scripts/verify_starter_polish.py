"""UI smoke test for starter content and offline-safe workflows."""
from pathlib import Path
import json,sys
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'verification';OUT.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8765';checks=[]
# Reuse no secrets: browser test exercises a disposable account with starter seed via direct DB after registration.
import httpx,secrets
sys.path.insert(0,str(ROOT/'backend'));from app import core
email=f'polish-{secrets.token_hex(5)}@example.test';password=secrets.token_urlsafe(20)
with httpx.Client(base_url=URL+'/api',trust_env=False,timeout=60) as c:
 reg=c.post('/auth/register',json={'email':email,'password':password,'display_name':'美化验收'});reg.raise_for_status();uid=reg.json()['user']['id']
 try:
  # Add two deterministic objective questions via the same public API, no fake AI responses.
  h={'Authorization':'Bearer '+reg.json()['access_token']}
  for q in [
   {'subject':'数据库','type':'单选题','difficulty':'简单','stem':'数据库中唯一标识记录的是？','options':['主键','外键','视图','事务'],'answer':'主键','explanation':'主键唯一标识记录。','knowledge_points':['主键']},
   {'subject':'Python','type':'判断题','difficulty':'简单','stem':'Python 使用缩进表示代码块。','options':[],'answer':True,'explanation':'Python 以缩进划分代码块。','knowledge_points':['缩进']}]:
   r=c.post('/questions/manual',headers=h,json=q);r.raise_for_status()
  with sync_playwright() as p:
   page=p.chromium.launch(channel='msedge',headless=True).new_page(viewport={'width':1440,'height':960});page.goto(URL,wait_until='networkidle');page.get_by_label('邮箱地址').fill(email);page.get_by_label('密码').fill(password);page.get_by_role('button',name='登录学习空间').click();page.wait_for_url('**/#/dashboard',wait_until='networkidle')
   page.goto(URL+'/#/questions',wait_until='networkidle');expect(page.get_by_role('heading',name='智能练习题库')).to_be_visible();expect(page.locator('.question-card')).to_have_count(2);page.get_by_role('button',name='手工添加题目').click();expect(page.get_by_role('dialog')).to_be_visible();page.keyboard.press('Escape');checks.append('题库数据与手工建题入口');page.screenshot(path=str(OUT/'questions-starter-polished.png'),full_page=True)
   page.goto(URL+'/#/knowledge',wait_until='networkidle');expect(page.get_by_role('heading',name='个人知识库')).to_be_visible();checks.append('知识库工作台加载');page.screenshot(path=str(OUT/'knowledge-starter-polished.png'),full_page=True)
   assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2');checks.append('桌面端无溢出')
 finally:
  with core.db() as db:db.execute('DELETE FROM users WHERE id=?',(uid,))
report={'passed':len(checks),'checks':checks};(OUT/'starter-polish-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
