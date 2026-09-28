"""Browser acceptance against running local app using a disposable labelled user.
Uses installed Edge, no fake HTTP responses and no external model calls.
"""
from pathlib import Path
import json, secrets, sys
import httpx
from playwright.sync_api import sync_playwright, expect
expect.set_options(timeout=45000)
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app import core
OUT=ROOT/'data'/'verification'; OUT.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8765'
results=[]; errors=[]; account=None; email=''; password=''
api=httpx.Client(base_url=URL,trust_env=False,timeout=60)
def mark(name,**extra):
    results.append({'name':name,'ok':True,**extra})
    print(name,'PASS',flush=True)
def call(method,path,**kw):
    r=api.request(method,'/api'+path,**kw); r.raise_for_status(); return r.json()
def persist():
    (OUT/'browser.json').write_text(json.dumps({'checks':results,'page_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
try:
    email='ui-'+secrets.token_hex(8)+'@example.test'; password=secrets.token_urlsafe(24)
    account=call('POST','/auth/register',json={'email':email,'display_name':'浏览器验收测试','password':password})
    api.headers['Authorization']='Bearer '+account['access_token']
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--disable-gpu','--no-first-run'])
        context=browser.new_context(viewport={'width':1440,'height':960})
        page=context.new_page();page.set_default_timeout(45000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:d.accept())
        page.goto(URL,wait_until='networkidle')
        expect(page.get_by_role('heading',name='欢迎回来')).to_be_visible()
        mark('anonymous_login_page')
        page.get_by_label('邮箱地址').fill(email); page.get_by_label('密码').fill(password)
        page.get_by_role('button',name='登录学习空间').click()
        page.wait_for_url('**/#/dashboard',wait_until='networkidle')
        expect(page.locator('.stat-card')).to_have_count(4)
        assert call('GET','/dashboard/summary')['study_minutes']==0
        mark('empty_dashboard_no_fabricated_stats')
        def route(path):
            page.goto(URL+'/#'+path,wait_until='networkidle')
            titles={'/learning':'我的学习','/plans':'学习计划','/knowledge':'知识库','/documents':'AI 文档','/chat':'AI 助手','/questions':'练习题库','/agent':'智能行动','/analytics':'数据与报告','/settings':'空间设置','/search':'全局搜索'}
            title=titles.get(path.split('?')[0])
            if title: expect(page.get_by_role('heading',level=1,name=title,exact=True)).to_be_visible(timeout=30000)
            else: expect(page.locator('.dashboard-page h1')).to_be_visible(timeout=30000)
        route('/learning')
        page.get_by_role('button',name='新建任务',exact=True).click()
        dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
        dialog.get_by_label('任务标题').fill('浏览器测试任务')
        dialog.get_by_label('标签（逗号分隔，最多 12 个）').fill('测试、数据库')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog).not_to_be_visible()
        task=call('GET','/tasks')[0];assert task['title']=='浏览器测试任务' and task['tags']==['测试','数据库']
        page.get_by_role('button',name='标记为完成',exact=True).click()
        expect(page.locator('.task-row.completed')).to_have_count(1)
        assert call('GET','/tasks')[0]['status']=='done'
        mark('task_create_complete_readback')
        page.get_by_role('tab',name='课程表').click();page.get_by_role('button',name='添加课程',exact=True).click()
        dialog.get_by_label('课程名称').fill('数据库测试课');dialog.get_by_label('教师',exact=True).fill('测试教师')
        dialog.get_by_label('教室',exact=True).fill('测试教室')
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert call('GET','/courses')[0]['name']=='数据库测试课';mark('course_create_readback')
        page.get_by_role('tab',name='考试安排').click();page.get_by_role('button',name='添加考试',exact=True).click()
        dialog.get_by_label('考试科目').fill('数据库测试考试');dialog.get_by_label('考试日期').fill('2026-12-31')
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert call('GET','/exams')[0]['subject']=='数据库测试考试';mark('exam_create_readback')
        page.get_by_role('tab',name='学习记录').click();page.get_by_role('button',name='记录学习',exact=True).click()
        dialog.get_by_label('学科 / 学习内容').fill('验收测试时长');dialog.get_by_label('已学习分钟').fill('25')
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert call('GET','/dashboard/summary')['study_minutes']==25;mark('record_statistics_real_data')
        route('/plans');page.get_by_role('button',name='手工计划',exact=True).click()
        dialog.get_by_label('计划名称').fill('浏览器测试计划');dialog.get_by_label('学习目标').fill('测试手工计划闭环')
        dialog.get_by_label('开始日期').fill('2026-10-01');dialog.get_by_label('结束日期').fill('2026-10-02')
        dialog.get_by_role('button',name='创建草案',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='发布到任务清单').click()
        expect(page.locator('.plan-detail').get_by_text('已发布',exact=True)).to_be_visible()
        assert len(call('GET','/tasks'))==3;mark('plan_create_publish_to_tasks')
        route('/knowledge');page.get_by_role('button',name='写一条笔记',exact=True).click()
        dialog.get_by_label('标题',exact=True).fill('浏览器测试笔记');dialog.get_by_label('内容',exact=True).fill('数据库主键唯一标识每一条记录。')
        dialog.get_by_role('button',name='保存笔记').click();expect(dialog).not_to_be_visible()
        assert call('GET','/notes')[0]['title']=='浏览器测试笔记';mark('note_create_readback')
        route('/documents')
        expect(page.get_by_role('button',name='上传文档',exact=True)).to_be_enabled()
        page.locator('input[type=file]').set_input_files({'name':'浏览器测试资料.txt','mimeType':'text/plain','buffer':'数据库主键唯一标识每条记录。外键引用另一表的主键。'.encode('utf-8')})
        expect(page.locator('.document-row')).to_have_count(1,timeout=60000)
        docs=call('GET','/documents');assert len(docs)==1 and docs[0]['status']=='ready'
        if page.locator('.document-detail').count()==0:
            page.locator('.document-select').first.click()
        expect(page.locator('.preview-box pre')).to_contain_text('数据库主键')
        mark('document_upload_extract_preview')
        route('/chat');page.get_by_label('发送给 AI 的消息').fill('未配置模型边界验收')
        page.get_by_role('button',name='发送消息',exact=True).click()
        expect(page.locator('.chat-composer-wrap .error-banner')).to_contain_text('尚未配置')
        conv=call('GET','/conversations')[0]
        assert call('GET','/conversations/'+conv['id']+'/messages')==[];mark('ai_missing_key_error_no_fake_reply')
        for view in ['/questions','/agent','/analytics','/settings','/search?q=浏览器测试']:
            route(view)
            assert page.locator('.error-banner:visible').count()==0,page.locator('.error-banner:visible').all_text_contents()
            mark('route_'+view.split('?')[0].strip('/'))
        route('/analytics');page.get_by_role('button',name='生成报告',exact=False).click()
        expect(page.locator('.report-body')).to_contain_text('数据库统计摘要')
        assert call('GET','/reports')[0]['source']=='data_summary';mark('report_explicit_data_summary')
        route('/dashboard');page.screenshot(path=str(OUT/'dashboard-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});page.reload(wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2')
        page.get_by_role('button',name='展开导航').click();expect(page.locator('.sidebar.open')).to_be_visible()
        page.screenshot(path=str(OUT/'dashboard-mobile.png'),full_page=True);mark('mobile_layout_and_navigation')
        assert not errors,errors
        mark('no_javascript_errors')
        browser.close()
except Exception:
    try:
        print('FAIL_PAGE',page.url,page.locator('body').inner_text()[:7000],flush=True)
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
    except Exception: pass
    raise
finally:
    persist()
    if account:
        # Delete only this script's disposable user and generated documents.
        for doc in call('GET','/documents'): call('DELETE','/documents/'+doc['id'])
        with core.db() as conn: conn.execute('DELETE FROM users WHERE id=?',(account['user']['id'],))
    api.close()
print(json.dumps({'checks':len(results),'all_ok':all(r['ok'] for r in results),'page_errors':errors},ensure_ascii=False))
