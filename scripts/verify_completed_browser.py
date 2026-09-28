"""Browser acceptance for the completed AI, knowledge and practice UI."""
from pathlib import Path
import json,secrets,sys
import httpx
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app import core
URL='http://127.0.0.1:8765';OUT=ROOT/'data'/'verification';OUT.mkdir(parents=True,exist_ok=True)
email=f'ui-feature-{secrets.token_hex(5)}@example.test';password=secrets.token_urlsafe(22);uid='';checks=[];errors=[]
def mark(name):checks.append(name);print(name,'PASS',flush=True)
with httpx.Client(base_url=URL+'/api',trust_env=False,timeout=180) as api:
 reg=api.post('/auth/register',json={'email':email,'password':password,'display_name':'界面验收'});reg.raise_for_status();data=reg.json();uid=data['user']['id'];h={'Authorization':'Bearer '+data['access_token']}
 try:
  kb=api.post('/knowledge-bases',headers=h,json={'name':'浏览器知识库','description':'用于完整页面验收'}).json()
  f={'file':('网页验收.txt','数据库事务包含原子性、一致性、隔离性、持久性。'.encode(),'text/plain')};doc=api.post('/documents/upload',headers=h,files=f).json();api.patch(f"/documents/{doc['id']}/knowledge-base",headers=h,json={'knowledge_base_id':kb['id'],'folder':''});api.post(f"/documents/{doc['id']}/index",headers=h)
  with sync_playwright() as p:
   browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--no-first-run']);page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(URL,wait_until='networkidle')
   page.get_by_label('邮箱地址').fill(email);page.get_by_label('密码').fill(password);page.get_by_role('button',name='登录学习空间').click();page.wait_for_url('**/#/dashboard',wait_until='networkidle');mark('真实登录')
   page.goto(URL+'/#/chat',wait_until='networkidle');expect(page.get_by_role('heading',name='AI 学习助手')).to_be_visible();expect(page.get_by_text('模型服务已连接')).to_be_visible();page.locator('.chat-head-controls select').first.select_option(kb['id']);page.locator('.chat-composer textarea').fill('根据资料，只回复：数据库事务包含原子性、一致性、隔离性和持久性。');page.locator('.send-button').click();expect(page.locator('.message.assistant')).to_contain_text('原子性',timeout=180000);expect(page.locator('.send-button')).to_be_visible(timeout=180000);expect(page.locator('.typing')).to_have_count(0);mark('AI助手真实流式回答并结束状态');page.screenshot(path=str(OUT/'ai-assistant-polished.png'),full_page=True)
   page.goto(URL+'/#/knowledge',wait_until='networkidle');expect(page.get_by_role('heading',name='个人知识库')).to_be_visible();expect(page.get_by_text('浏览器知识库',exact=True).first).to_be_visible();page.locator('.rag-form textarea').fill('事务有哪些特性？');page.get_by_role('button',name='获取带引用答案').click();expect(page.locator('.citation')).to_have_count(1,timeout=180000);mark('知识库检索引用');page.screenshot(path=str(OUT/'knowledge-polished.png'),full_page=True)
   page.goto(URL+'/#/questions',wait_until='networkidle');expect(page.get_by_role('heading',name='智能练习题库')).to_be_visible();expect(page.get_by_text('AI QUESTION STUDIO')).to_be_visible();mark('题库完整工作台');page.screenshot(path=str(OUT/'questions-polished.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.reload(wait_until='networkidle');assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2');mark('题库移动端无横向溢出');page.screenshot(path=str(OUT/'questions-mobile-polished.png'),full_page=True)
   assert not errors,errors;mark('无前端运行错误');browser.close()
 finally:
  if uid:
   with core.db() as db:db.execute('DELETE FROM users WHERE id=?',(uid,))
report={'passed':len(checks),'checks':checks,'page_errors':errors};(OUT/'completed-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
