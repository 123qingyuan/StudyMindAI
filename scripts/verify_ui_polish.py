from pathlib import Path
import json, secrets, sys, re
import httpx
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app import core
OUT=ROOT/'data/verification'; OUT.mkdir(exist_ok=True)
BASE='http://127.0.0.1:8765'
report={'checks':[], 'console_errors':[], 'page_errors':[], 'screenshots':[]}
api=httpx.Client(base_url=BASE,timeout=120,trust_env=False)
email='ui-polish-'+secrets.token_hex(8)+'@example.test'; password=secrets.token_urlsafe(24)
a=None
try:
 r=api.post('/api/auth/register',json={'email':email,'password':password,'display_name':'界面验收'}); r.raise_for_status(); a=r.json()
 api.headers['Authorization']='Bearer '+a['access_token']
 daily=api.get('/api/questions/daily').json(); qs=daily['questions']; report['real_questions']=len(qs)
 longest=max(qs,key=lambda q:len(q['stem'])); report['longest_stem_characters']=len(longest['stem'])
 bases=api.get('/api/knowledge-bases').json(); report['knowledge_bases']=len(bases)
 docs=api.get('/api/documents').json(); longdoc=max(docs,key=lambda d:d.get('size_bytes',0))
 report['long_document_name']=longdoc['original_name']
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
  page.set_default_timeout(60000)
  page.on('console',lambda m:report['console_errors'].append(m.text) if m.type=='error' else None)
  page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
  page.goto(BASE+'/#/login',wait_until='networkidle')
  page.locator('#auth-email').fill(email);page.locator('#auth-password').fill(password)
  page.locator('button[type=submit]').click();page.wait_for_url('**/#/dashboard');page.wait_for_load_state('networkidle')
  report['real_ui_login']=True
  def check(name,screenshot=True):
   page.wait_for_load_state('networkidle')
   geometry=page.evaluate('''() => ({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('.page *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.right>innerWidth+1||r.left < -1)&&getComputedStyle(e).position!=='fixed'}).slice(0,8).map(e=>e.className)})''')
   report['checks'].append({'name':name,**geometry,'pass':geometry['scroll']<=geometry['width']})
   if screenshot:
    fn=OUT/f'ui-polish-{name}.png';page.screenshot(path=str(fn));report['screenshots'].append(str(fn))
  for width in [1440,390,320]:
   page.set_viewport_size({'width':width,'height':1000 if width==1440 else 844})
   for route in ['dashboard','knowledge','questions','settings','learning','documents','plans','analytics','search']:
    page.goto(BASE+'/#/'+route,wait_until='networkidle')
    check(f'{route}-{width}')
    if route=='questions':
     expect(page.locator('.question-card')).to_have_count(min(20,len(qs)),timeout=60000)
     buttons=page.locator('.subject-filter button'); names=buttons.all_text_contents()
     for subject in names[1:]:
      buttons.get_by_text(subject,exact=True).click()
      expect(page.locator('.question-card')).to_have_count(min(20,sum(q['subject']==subject for q in qs)))
     report['checks'].append({'name':f'all-subject-filters-{width}','count':len(names)-1,'pass':True})
     buttons.get_by_text(longest['subject'],exact=True).click()
     index=next(i for i,q in enumerate([x for x in qs if x['subject']==longest['subject']]) if q['id']==longest['id'])
     page.get_by_label('题目页码',exact=True).select_option(str(index//20+1))
     card=page.locator('.question-card').nth(index%20)
     card.evaluate('(e)=>e.scrollIntoView({block:"start"})');check(f'long-question-{width}')
     expect(card.locator('button',has_text='提交答案')).to_be_enabled()
     card.locator('button',has_text='提交答案').scroll_into_view_if_needed()
     page.get_by_label('作答状态',exact=True).select_option(label='已作答');expect(page.locator('.question-card')).to_have_count(0)
     page.get_by_label('作答状态',exact=True).select_option(label='未作答');expect(page.locator('.question-card')).to_have_count(min(20,sum(q['subject']==longest['subject'] for q in qs)))
    if route=='knowledge':
     page.get_by_role('button',name='专题资料',exact=True).click()
     link=page.get_by_role('link',name='阅读原文').first;expect(link).to_be_visible();link.click();page.wait_for_load_state('networkidle')
     expect(page.locator('.preview-box pre')).to_be_visible()
     page.goto(BASE+'/#/documents?id='+longdoc['id'],wait_until='networkidle')
     expect(page.locator('.preview-box pre')).to_be_visible(); text=page.locator('.preview-box pre').inner_text();report.setdefault('document_characters',len(text)); assert len(text)>10000
     page.locator('.document-detail').scroll_into_view_if_needed();check(f'long-document-{width}')
    if route=='learning':
     for tab in ['课程表','考试安排','学习记录']:
      page.get_by_role('tab',name=tab).click();check(f'learning-{tab}-{width}',False)
   if width<640:
    page.get_by_role('button',name='展开导航',exact=True).click();expect(page.locator('.sidebar')).to_have_class(re.compile('open'))
    page.get_by_role('button',name='收起主导航',exact=True).click()
    page.get_by_role('link',name='打开全局搜索').click();expect(page).to_have_url(re.compile('/search'))
  browser.close()
except Exception as e:
 report['failure']=str(e)
 raise
finally:
 if a:
  with core.db() as c:
   row=c.execute('SELECT email FROM users WHERE id=?',(a['user']['id'],)).fetchone()
   assert row and row['email']==email
   c.execute('DELETE FROM users WHERE id=?',(a['user']['id'],))
  with core.db() as c: report['temporary_account_removed']=c.execute('SELECT id FROM users WHERE id=?',(a['user']['id'],)).fetchone() is None
  report['removed_token_status']=api.get('/api/auth/me').status_code
 api.close()
 report['pass']=not report.get('failure') and not report['console_errors'] and not report['page_errors'] and all(x['pass'] for x in report['checks'])
 (OUT/'ui-polish-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k not in ['screenshots','checks']},ensure_ascii=False))
 print('checks',len(report['checks']),'failed',[x for x in report['checks'] if not x['pass']])
