<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, type Data } from '../api/client'
import { useRequest } from '../composables/useRequest'
import { confirmAction } from '../lib/ui'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'
import MarkdownContent from '../components/MarkdownContent.vue'
const {run,busy,error}=useRequest();const questions=ref<Data[]>([]),stats=ref<Data>({}),answers=reactive<Record<string,any>>({}),results=reactive<Record<string,Data>>({})
const filter=ref('全部'),statusFilter=ref('全部'),manualDialog=ref(false)
const manual=reactive({subject:'通识课程',type:'单选题',difficulty:'简单',stem:'',options:'',answer:'',explanation:'',knowledge_points:''})
const types=['单选题','多选题','判断题','填空题','简答题','编程题']
const filtered=computed(()=>questions.value.filter(q=>(filter.value==='全部'||q.subject===filter.value)&&(statusFilter.value==='全部'||(statusFilter.value==='已作答')===!!results[q.id])))
const pageNumber=ref(1), pageSize=20
const pageCount=computed(()=>Math.max(1,Math.ceil(filtered.value.length/pageSize)))
const visibleQuestions=computed(()=>filtered.value.slice((pageNumber.value-1)*pageSize,pageNumber.value*pageSize))
watch([filter,statusFilter],()=>{pageNumber.value=1})
watch(pageCount,value=>{pageNumber.value=Math.min(pageNumber.value,value)})
const subjectList=computed(()=>['全部',...new Set(questions.value.map(x=>x.subject))])
async function refresh(){const [daily,s]=await Promise.all([api.get<Data>('/questions/daily'),api.get('/questions/stats/overview')]);questions.value=daily.questions||[];stats.value={...s,daily_count:daily.count,daily_date:daily.date}}
function toggleMulti(id:string,option:string,checked:boolean){const current=Array.isArray(answers[id])?answers[id]:[];answers[id]=checked?[...new Set([...current,option])]:current.filter((x:string)=>x!==option)}
async function submit(q:Data){const value=answers[q.id];if(value===undefined||value===''||(Array.isArray(value)&&!value.length)){error.value='请先填写答案。';return}await run(async()=>{results[q.id]=await api.post(`/questions/${q.id}/answer`,{answer:value});stats.value=await api.get('/questions/stats/overview')},'评分完成')}
async function remove(q:Data){if(!await confirmAction('删除这道题及其作答记录？'))return;await run(async()=>{await api.delete(`/questions/${q.id}`);delete answers[q.id];delete results[q.id];await refresh()},'题目已删除')}
function manualPayload(){const options=manual.options.split('\n').map((x:string)=>x.trim()).filter(Boolean);let answer:any=manual.answer.trim();if(manual.type==='多选题')answer=answer.split(/[，,\n]/).map((x:string)=>x.trim()).filter(Boolean);else if(manual.type==='判断题')answer=['正确','true','是'].includes(answer.toLowerCase());else if(manual.type==='填空题'&&answer.includes('\n'))answer=answer.split('\n').map((x:string)=>x.trim()).filter(Boolean);return{...manual,options,answer,knowledge_points:manual.knowledge_points.split(/[，,]/).map((x:string)=>x.trim()).filter(Boolean)}}
async function createManual(){await run(async()=>{await api.post('/questions/manual',manualPayload());manual.stem='';manual.options='';manual.answer='';manual.explanation='';manual.knowledge_points='';manualDialog.value=false;await refresh()},'题目已加入练习库')}
onMounted(()=>run(refresh))
</script>
<template><section class="page questions-page"><PageHeader title="多专业练习题库" eyebrow="去重练习 · 按实际题量展示" description="每类最多100题，题源不足时只展示实际题量，不复制凑数；当前不承诺每日新增100题"><button class="primary" @click="manualDialog=true"><Icon name="plus" :size="16"/>添加题目</button></PageHeader>
<div v-if="error" class="error-banner" role="alert">{{error}}<button class="text-button" @click="error=''">关闭</button></div>
<div class="practice-stats"><div><span class="stat-icon"><Icon name="question" :size="17"/></span><p>本次可用题目</p><strong>{{stats.daily_count||0}}</strong><small>{{stats.daily_date||'今日'}} · 现有题库轮换，非每日新增</small></div><div><span class="stat-icon"><Icon name="check" :size="17"/></span><p>累计作答</p><strong>{{stats.answered||0}}</strong><small>每次提交都留痕</small></div><div><span class="stat-icon"><Icon name="chart" :size="17"/></span><p>客观题正确率</p><strong>{{stats.accuracy==null?'—':`${stats.accuracy}%`}}</strong><small>{{stats.objective||0}} 次有效判定</small></div><div><span class="stat-icon"><Icon name="spark" :size="17"/></span><p>平均得分</p><strong>{{stats.average_score==null?'—':stats.average_score}}</strong><small>满分 100</small></div></div>
<section class="panel library-banner" aria-labelledby="library-banner-title">
  <div class="generator-icon" aria-hidden="true"><Icon name="book" :size="25"/></div>
  <div class="library-copy"><h2 id="library-banner-title">知识与练习相互对应</h2><p>按学科选择练习，遇到疑问时回到知识库查阅资料，让理解与巩固同步进行。</p></div>
  <RouterLink class="secondary library-link" to="/knowledge">查看知识库<Icon name="book" :size="16"/></RouterLink>
</section>
<section class="panel practice-toolbar" aria-label="练习筛选">
  <div class="subject-filter"><div class="filter-heading"><h2 id="subject-filter-title">学科</h2><span>{{subjectList.length-1}} 个学科可选</span></div><div class="filter-pills" role="group" aria-labelledby="subject-filter-title"><button v-for="item in subjectList" :key="item" type="button" :class="{active:filter===item}" :aria-pressed="filter===item" @click="filter=item">{{item}}</button></div></div>
  <div class="status-filter"><label for="question-status-filter">作答状态</label><select id="question-status-filter" v-model="statusFilter" class="compact-select"><option>全部</option><option>未作答</option><option>已作答</option></select><span class="filter-result" aria-live="polite">当前显示 {{filtered.length}} 道题</span></div>
</section>
<div class="question-layout"><main class="question-list"><article v-for="(q,index) in visibleQuestions" :key="q.id" class="panel question-card"><header class="question-head"><div><span class="question-number">{{String((pageNumber-1)*pageSize+Number(index)+1).padStart(2,'0')}}</span><span class="pill">{{q.subject}}</span><span class="pill">{{q.type}}</span><span class="pill difficulty" :class="q.difficulty">{{q.difficulty}}</span></div><button class="icon-button danger-text" title="删除题目" @click="remove(q)"><Icon name="trash" :size="15"/></button></header><MarkdownContent class="question-stem" :content="q.stem" />
<div v-if="q.type==='单选题'" class="option-list"><label v-for="(option,i) in q.options" :key="option" class="option"><input v-model="answers[q.id]" type="radio" :name="q.id" :value="option" :disabled="!!results[q.id]"/><b>{{String.fromCharCode(65+Number(i))}}</b><span>{{option}}</span></label></div>
<div v-else-if="q.type==='多选题'" class="option-list"><label v-for="(option,i) in q.options" :key="option" class="option"><input type="checkbox" :checked="answers[q.id]?.includes(option)" :disabled="!!results[q.id]" @change="toggleMulti(q.id,option,($event.target as HTMLInputElement).checked)"/><b>{{String.fromCharCode(65+Number(i))}}</b><span>{{option}}</span></label></div>
<div v-else-if="q.type==='判断题'" class="judgement-row"><label class="option"><input v-model="answers[q.id]" type="radio" :name="q.id" :value="true" :disabled="!!results[q.id]"/>正确</label><label class="option"><input v-model="answers[q.id]" type="radio" :name="q.id" :value="false" :disabled="!!results[q.id]"/>错误</label></div>
<textarea v-else :aria-label="`第 ${Number(index)+1} 题作答`" v-model="answers[q.id]" class="answer-textarea" :disabled="!!results[q.id]" :rows="q.type==='编程题'?8:4" :placeholder="q.type==='填空题'?'填写答案；多空题按顺序用换行分隔':'写下你的完整作答…'"></textarea>
<footer class="question-foot"><span class="muted">{{q.knowledge_points?.length?`知识点：${q.knowledge_points.join(' · ')}`:'提交后显示答案与解析'}}</span><button v-if="!results[q.id]" class="primary small" :disabled="busy" @click="submit(q)">提交答案</button><span v-else class="pill success">已完成评分</span></footer><div v-if="results[q.id]" class="answer-result" :class="results[q.id].correct===true?'correct':results[q.id].correct===false?'wrong':'reviewed'"><div class="result-score"><strong>{{results[q.id].score}}</strong><span>{{results[q.id].grading_method==='self_review'?'请对照答案订正':'分 · 确定性规则评分'}}</span></div><p><b>参考答案：</b>{{Array.isArray(results[q.id].answer)?results[q.id].answer.join('；'):String(results[q.id].answer)}}</p><p><b>解析：</b>{{results[q.id].explanation||results[q.id].feedback||'暂无解析'}}</p><p v-if="results[q.id].feedback&&results[q.id].feedback!==results[q.id].explanation"><b>反馈：</b>{{results[q.id].feedback}}</p></div></article><nav v-if="filtered.length" class="button-row" aria-label="题目分页"><button class="secondary" :disabled="pageNumber===1" @click="pageNumber--">上一页</button><label>页码<select v-model.number="pageNumber" aria-label="题目页码"><option v-for="n in pageCount" :key="n" :value="n">{{n}}</option></select></label><span class="muted">共 {{pageCount}} 页 · {{filtered.length}} 题</span><button class="secondary" :disabled="pageNumber===pageCount" @click="pageNumber++">下一页</button></nav><EmptyState v-if="!filtered.length" title="当前筛选下没有题目" description="可以手工添加题目，或切换到其他专业分类。" icon="question"/></main>
<aside class="panel question-aside"><div class="panel-head"><div><h3>练习闭环</h3><p>从理解到掌握</p></div><Icon name="chart"/></div><div class="practice-step"><span>1</span><div><strong>题源可控</strong><p>内置题目或手工录入，答案不会提前公开</p></div></div><div class="practice-step"><span>2</span><div><strong>即时反馈</strong><p>客观题规则评分，主观题对照参考答案自评</p></div></div><div class="practice-step"><span>3</span><div><strong>数据沉淀</strong><p>作答记录进入学习统计与后续复习</p></div></div><div v-if="stats.by_subject?.length" class="subject-mini"><h3>学科表现</h3><div v-for="item in stats.by_subject.slice(0,5)" :key="item.subject"><span>{{item.subject}}</span><strong>{{item.average_score==null?'未作答':`${Math.round(item.average_score)} 分`}}</strong></div></div></aside></div>
<ElDialog v-model="manualDialog" title="手工添加练习题" width="620px"><form class="stack-form" @submit.prevent="createManual"><div class="form-row"><label>学科<input v-model.trim="manual.subject" required maxlength="120"/></label><label>题型<select v-model="manual.type"><option v-for="item in types" :key="item">{{item}}</option></select></label></div><div class="form-row"><label>难度<select v-model="manual.difficulty"><option>简单</option><option>中等</option><option>困难</option></select></label><label>知识点（逗号分隔）<input v-model="manual.knowledge_points" placeholder="如：循环结构，边界条件"/></label></div><label>题干<textarea v-model.trim="manual.stem" required rows="4"></textarea></label><label v-if="['单选题','多选题'].includes(manual.type)">选项（每行一个）<textarea v-model="manual.options" required rows="5" placeholder="每行填写一个完整选项"></textarea></label><label>参考答案<textarea v-model="manual.answer" required rows="3" :placeholder="manual.type==='多选题'?'填写完整选项，用逗号分隔':manual.type==='判断题'?'正确 或 错误':'填写参考答案'"></textarea></label><label>解析<textarea v-model="manual.explanation" rows="4" placeholder="解释正确答案与关键知识点"></textarea></label><div class="dialog-actions"><button type="button" class="secondary" @click="manualDialog=false">取消</button><button class="primary" :disabled="busy">保存题目</button></div></form></ElDialog></section></template>

<style scoped>
.library-banner { display:flex; align-items:center; gap:20px; padding:26px 28px; background:var(--surface); border:1px solid var(--line-strong); }
.library-banner .generator-icon { width:54px; height:54px; border-radius:16px; }
.library-copy { flex:1; min-width:0; }
.library-copy h2 { margin:8px 0; color:#292b45; font-size:21px; line-height:1.4; }
.library-copy p { margin:0; max-width:680px; color:#586176; font-size:14px; line-height:1.8; overflow-wrap:anywhere; }
.library-link { display:inline-flex; align-items:center; justify-content:center; gap:9px; flex:none; min-height:44px; padding:10px 17px; color:#5140a0; background:#fff; border:1px solid #d9d3ef; white-space:nowrap; font-size:14px; }
.practice-toolbar { display:grid; grid-template-columns:minmax(0,1fr) 160px; align-items:start; gap:24px; margin:20px 0; padding:22px 24px; background:#fff; border:1px solid #e1e5ef; border-radius:16px; }
.subject-filter { min-width:0; }
.filter-heading { display:flex; align-items:baseline; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
.filter-heading h2,.status-filter label { margin:0; color:#30364b; font-size:14px; font-weight:700; line-height:1.5; }
.filter-heading span,.filter-result { color:#626b7e; font-size:12px; line-height:1.6; }
.practice-toolbar .filter-pills { display:flex; flex-wrap:wrap; gap:9px; margin:0; }
.filter-pills button { min-height:40px; max-width:100%; padding:8px 14px; border:1px solid #dce1ec; border-radius:9px; background:#f6f8fc; color:#46516a; font-size:14px; font-weight:500; line-height:1.5; overflow-wrap:anywhere; cursor:pointer; transition:background .15s,border-color .15s; }
.filter-pills button:hover { color:#4b3a97; background:#f0ecff; border-color:#b8abdf; box-shadow:none; }
.filter-pills button.active { color:var(--primary-dark); background:var(--primary-soft); border-color:var(--primary); box-shadow:none; font-weight:700; }
.filter-pills button:focus-visible,.compact-select:focus-visible,.library-link:focus-visible { outline:3px solid #9784d7; outline-offset:3px; }
.status-filter { display:flex; flex-direction:column; gap:12px; min-width:0; padding-left:22px; border-left:1px solid #e6e9f1; }
.status-filter .compact-select { width:100%; min-height:42px; padding:8px 12px; border:1px solid #d4dae7; border-radius:9px; color:#39445b; background:#fff; font-size:14px; }
@media (max-width:700px) {
  .library-banner { flex-direction:column; align-items:flex-start; gap:15px; padding:22px 20px; }
  .library-copy h2 { font-size:20px; }
  .library-link { width:100%; white-space:normal; }
  .practice-toolbar { grid-template-columns:minmax(0,1fr); gap:20px; padding:20px 16px; }
  .practice-toolbar .filter-pills { gap:8px; }
  .filter-pills button { min-height:44px; padding:9px 12px; }
  .status-filter { padding:17px 0 0; border-left:0; border-top:1px solid #e6e9f1; }
  .status-filter .compact-select { min-height:44px; }
}
</style>