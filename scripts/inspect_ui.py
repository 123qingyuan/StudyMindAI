from pathlib import Path
import sys,secrets,httpx
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app import core
url='http://127.0.0.1:8765'; api=httpx.Client(base_url=url,trust_env=False)
a=api.post('/api/auth/register',json={'email':'inspect-'+secrets.token_hex(8)+'@example.test','display_name':'页面检查','password':secrets.token_urlsafe(24)}).json();api.headers['Authorization']='Bearer '+a['access_token']
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu']);ctx=b.new_context();page=ctx.new_page();page.set_default_timeout(15000)
  page.goto(url,wait_until='networkidle');page.evaluate('(a)=>{sessionStorage.setItem("studymind_token",a.access_token);sessionStorage.setItem("studymind_user",JSON.stringify(a.user))}',a)
  page.goto(url+'/#/analytics',wait_until='networkidle');page.wait_for_timeout(1000)
  print('URL',page.url);print('HEADINGS',page.locator('h1,h2,h3').all_text_contents());print('BUTTONS',page.locator('button').all_text_contents());print('BODY',page.locator('body').inner_text()[:8000])
  b.close()
finally:
 with core.db() as c:c.execute('DELETE FROM users WHERE id=?',(a['user']['id'],))
 api.close()
