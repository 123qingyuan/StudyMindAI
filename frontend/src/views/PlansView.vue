<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, type Data } from '../api/client'
import { useRequest } from '../composables/useRequest'
import { confirmAction, localDay, statusText } from '../lib/ui'
import PageHeader from '../components/PageHeader.vue'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
const { run, busy, error } = useRequest()
const plans = ref<Data[]>([]); const loaded = ref(false); const currentId = ref(''); const dialog = ref(false); const editDialog = ref(false); const itemId = ref('')
const current = computed(() => plans.value.find(x => x.id === currentId.value))
const form = reactive({ title: '', goal: '', start_date: localDay(), end_date: localDay(6), daily_minutes: 60 })
const itemForm = reactive({ title: '', description: '', plan_date: '', estimated_minutes: 30, status: 'todo' })
async function refresh() { plans.value = await api.get<Data[]>('/study-plans'); loaded.value = true; if (!plans.value.some(x => x.id === currentId.value)) currentId.value = plans.value[0]?.id || '' }
async function load() { await run(refresh) }
function create() { dialog.value = true }
async function save() {
  await run(async () => {
    if (form.start_date > form.end_date) throw new Error('结束日期不能早于开始日期。')
    const result = await api.post('/study-plans', { ...form })
    await refresh(); currentId.value = result.id; dialog.value = false
  }, '草案已保存，请审阅并编辑每日安排后发布')
}
function edit(item: Data) { itemId.value = item.id; for (const key of Object.keys(itemForm)) (itemForm as Data)[key] = item[key]; editDialog.value = true }
async function saveItem() { await run(async () => { await api.patch(`/study-plans/${currentId.value}/items/${itemId.value}`, { ...itemForm }); await refresh(); editDialog.value = false }, '条目已更新') }
async function publish() {
  if (!current.value || !await confirmAction(`发布「${current.value.title}」？将创建 ${current.value.items?.length || 0} 个关联学习任务。发布后修改条目会同步关联任务。`, '发布学习计划')) return
  await run(async () => { await api.post(`/study-plans/${currentId.value}/publish`); await refresh() }, '计划已发布，关联任务可在「我的学习」查看')
}
async function remove() {
  if (!current.value || !await confirmAction('删除此计划？已经发布的学习任务不会随计划一起删除。')) return
  await run(async () => { await api.delete(`/study-plans/${currentId.value}`); await refresh() }, '计划已删除')
}
onMounted(load)
</script>
<template><section class="page">
  <PageHeader title="学习计划" eyebrow="从目标到每天可执行的一步" description="自主安排每日任务，调整确认后再发布到任务清单。"><button class="primary" :disabled="busy" @click="create"><Icon name="plus" :size="17" /> 新建计划</button></PageHeader>
  <div v-if="error" class="error-banner" role="alert">{{ error }}<button class="text-button" :disabled="busy" @click="load">刷新</button></div>
  <div class="notice"><Icon name="shield" /><p>计划默认保存为草案；未经你发布，不会创建学习任务。</p></div>
  <div v-if="busy && !loaded" class="loading-panel">正在读取计划…</div>
  <div v-if="plans.length" class="master-detail">
    <aside class="panel master-list"><div class="panel-head"><h2>我的计划</h2><span class="count-badge">{{ plans.length }}</span></div><button v-for="plan in plans" :key="plan.id" class="master-item" :class="{ selected: plan.id === currentId }" :disabled="busy" @click="currentId = plan.id"><strong>{{ plan.title }}</strong><span>{{ plan.start_date }} — {{ plan.end_date }}</span><div class="meta-row"><span class="pill">{{ statusText(plan.status) }}</span><small>自主计划</small></div></button></aside>
    <section v-if="current" class="panel plan-detail"><div class="panel-head"><div><h2>{{ current.title }}</h2><p>{{ current.start_date }} 至 {{ current.end_date }} · 每天 {{ current.daily_minutes }} 分钟</p></div><span class="pill" :class="{ success: current.status === 'published' }">{{ statusText(current.status) }}</span></div><div class="pad"><p class="plan-goal">{{ current.goal }}</p><div class="toolbar"><span class="muted">{{ current.items?.length || 0 }} 个条目 · 自主创建，可逐条调整</span><div class="button-row"><button class="danger small" :disabled="busy" @click="remove">删除计划</button><button v-if="current.status === 'draft'" class="primary small" :disabled="busy" @click="publish">{{ busy ? '处理中…' : '发布到任务清单' }}</button><RouterLink v-else class="secondary small" to="/learning">查看任务 →</RouterLink></div></div></div><div class="plan-timeline"><div v-for="(item, index) in current.items || []" :key="item.id" class="plan-day"><span class="timeline-number">{{ Number(index) + 1 }}</span><div class="grow"><div class="meta-row"><span class="pill">{{ item.plan_date }}</span><span>{{ item.estimated_minutes }} 分钟 · {{ statusText(item.status) }}</span></div><h3>{{ item.title }}</h3><p>{{ item.description }}</p></div><button class="icon-button" :disabled="busy" title="编辑每日安排" @click="edit(item)"><Icon name="edit" :size="18" /></button></div></div></section>
  </div>
  <EmptyState v-else-if="loaded" title="方向明确，行动就轻一点" description="创建一份适合当前节奏的学习计划。" icon="calendar"><button class="primary" :disabled="busy" @click="create">创建第一份计划</button></EmptyState>
  <ElDialog v-model="dialog" title="创建学习计划" width="600px" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy"><form class="stack-form" @submit.prevent="save"><fieldset :disabled="busy"><label>计划名称<input v-model.trim="form.title" required maxlength="120" placeholder="例如：数据库期末复习" /></label><label>学习目标<textarea v-model.trim="form.goal" rows="4" required maxlength="3000" placeholder="学习范围、当前基础和你希望达到的目标…" /></label><div class="form-row"><label>开始日期<input v-model="form.start_date" type="date" required /></label><label>结束日期<input v-model="form.end_date" type="date" :min="form.start_date" required /></label></div><label>每天计划分钟<input v-model.number="form.daily_minutes" type="number" min="1" max="1440" required /></label><p class="field-help">日期跨度不超过一年，系统会为每天创建可编辑条目。</p></fieldset><p v-if="error" class="error-banner" role="alert">{{ error }}</p><div class="dialog-actions"><button type="button" class="secondary" :disabled="busy" @click="dialog = false">取消</button><button class="primary" :disabled="busy">{{ busy ? '正在保存…' : '创建草案' }}</button></div></form></ElDialog>
  <ElDialog v-model="editDialog" title="编辑计划条目" width="580px" :close-on-click-modal="!busy" :show-close="!busy"><form class="stack-form" @submit.prevent="saveItem"><fieldset :disabled="busy"><label>标题<input v-model.trim="itemForm.title" required maxlength="120" /></label><label>具体安排<textarea v-model="itemForm.description" rows="4" maxlength="5000" /></label><div class="form-row"><label>计划日期<input v-model="itemForm.plan_date" type="date" :min="current?.start_date" :max="current?.end_date" required /></label><label>预计分钟<input v-model.number="itemForm.estimated_minutes" type="number" min="1" max="1440" required /></label></div><label>状态<select v-model="itemForm.status"><option v-for="s in ['todo', 'doing', 'done']" :key="s" :value="s">{{ statusText(s) }}</option></select></label><p v-if="current?.status === 'published'" class="field-help">此计划已发布，保存将同步更新关联任务。</p></fieldset><p v-if="error" class="error-banner">{{ error }}</p><div class="dialog-actions"><button type="button" class="secondary" :disabled="busy" @click="editDialog = false">取消</button><button class="primary" :disabled="busy">{{ busy ? '正在保存…' : '保存条目' }}</button></div></form></ElDialog>
</section></template>
