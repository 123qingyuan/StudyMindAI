"""Browser acceptance for local-only product and rotating backgrounds."""
from playwright.sync_api import sync_playwright,expect
import httpx,json,secrets
BASE='http://127.0.0.1:8765';email=f'local-ui-{secrets.token_hex(4)}@example.test';password=secrets.token_urlsafe(20)
with httpx.Client(base_url=BASE+'/api',trust_env=False,timeout=30) as c:
 r=c.post('/auth/register',json={'email':email,'password':password,'display_name':'本地界面验收'});r.raise_for_status()
checks=[]
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True);page=b.new_page(viewport={'width':1440,'height':1000});page.goto(BASE+'/#/login');page.get_by_label('邮箱地址').fill(email);page.get_by_label('密码').fill(password);page.get_by_role('button',name='登录学习空间').click();page.wait_for_url('**/#/dashboard',timeout=30000)
 expect(page.locator('.sidebar')).not_to_contain_text('AI 助手');expect(page.locator('.sidebar')).not_to_contain_text('智能行动');checks.append('生成式功能入口已移除')
 page.goto(BASE+'/#/knowledge');expect(page.get_by_text('多专业知识库',exact=True)).to_be_visible();checks.append('多专业本地知识库页面可见')
 page.goto(BASE+'/#/questions');expect(page.get_by_text('多专业练习题库',exact=True)).to_be_visible();checks.append('多专业本地题库页面可见')
 assert page.locator('.background-scene').count()==4 and page.locator('.background-scene.active').count()==1;checks.append('全局轮换背景已挂载')
 assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth');checks.append('桌面端无横向溢出')
 page.screenshot(path='E:/StudyMindAI/data/verification/local-only-polished.png',full_page=True);b.close()
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
