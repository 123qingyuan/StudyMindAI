<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type Data } from '../api/client'
import { useRequest } from '../composables/useRequest'
import { confirmAction, dateText, localDay, statusText } from '../lib/ui'
import PageHeader from '../components/PageHeader.vue'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
const route = useRoute(); const router = useRouter(); const { run, busy, error } = useRequest()
const tabs = [{ id: 'tasks', label: '任务清单' }, { id: 'courses', label: '课程表' }, { id: 'exams', label: '考试安排' }, { id: 'records', label: '学习记录' }]
const tab = ref('tasks'); const tasks = ref<Data[]>([]); const courses = ref<Data[]>([]); const exams = ref<Data[]>([]); const records = ref<Data[]>([])
const loaded = ref(false); const query = ref(''); const status = ref('all'); const dialog = ref(false); const editing = ref(''); const kind = ref('tasks'); const tags = ref('')
const taskForm = reactive({ title: '', description: '', status: 'todo', priority: 2, due_date: '', category: '学习', estimated_minutes: 30 })
const courseForm = reactive({ name: '', teacher: '', classroom: '', weekday: 1, start_time: '08:00', end_time: '09:40', start_week: 1, end_week: 20, week_pattern: 'all', term_start_date: '' })
const examForm = reactive({ subject: '', exam_date: localDay(), location: '', notes: '' })
const recordForm = reactive({ subject: '', minutes: 30, note: '' })
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const filtered = computed(() => tasks.value.filter(t => (status.value === 'all' || t.status === status.value || status.value === 'overdue' && t.overdue) && `${t.title} ${t.description} ${t.category} ${(t.tags || []).join(' ')}`.toLowerCase().includes(query.value.toLowerCase())))
const stats = computed(() => [{ label: '待完成', count: tasks.value.filter(x => x.status === 'todo').length }, { label: '进行中', count: tasks.value.filter(x => x.status === 'doing').length }, { label: '已完成', count: tasks.value.filter(x => x.status === 'done').length }, { label: '已逾期', count: tasks.value.filter(x => x.overdue).length }])
async function refresh() {
  const [t, c, e, r] = await Promise.all([api.get<Data[]>('/tasks'), api.get<Data[]>('/courses'), api.get<Data[]>('/exams'), api.get<Data[]>('/study-records')])
  tasks.value = t; courses.value = c; exams.value = e; records.value = r; loaded.value = true
}
async function load() { await run(refresh); syncRoute() }
function syncRoute() {
  tab.value = tabs.some(x => x.id === route.query.tab) ? String(route.query.tab) : 'tasks'
  if (route.query.id && loaded.value) { const found = tasks.value.find(x => x.id === route.query.id); if (found) open('tasks', found) }
}
function selectTab(value: string) { dialog.value = false; void router.replace({ path: '/learning', query: { tab: value } }) }
function open(value = tab.value, item?: Data) {
  kind.value = value; editing.value = item?.id || ''
  if (value === 'tasks') {
    Object.assign(taskForm, { title: '', description: '', status: 'todo', priority: 2, due_date: '', category: '学习', estimated_minutes: 30 })
    if (item) for (const key of Object.keys(taskForm)) (taskForm as Data)[key] = item[key] ?? ''
    tags.value = (item?.tags || []).join('、')
  }
  if (value === 'courses') {
    Object.assign(courseForm, { name: '', teacher: '', classroom: '', weekday: 1, start_time: '08:00', end_time: '09:40', start_week: 1, end_week: 20, week_pattern: 'all', term_start_date: '' })
    if (item) for (const key of Object.keys(courseForm)) (courseForm as Data)[key] = item[key] ?? ''
  }
  if (value === 'exams') Object.assign(examForm, { subject: item?.subject || '', exam_date: item?.exam_date || localDay(), location: item?.location || '', notes: item?.notes || '' })
  if (value === 'records') Object.assign(recordForm, { subject: '', minutes: 30, note: '' })
  dialog.value = true
}
const endpoint = (value: string) => value === 'records' ? '/study-records' : `/${value}`
async function save() {
  await run(async () => {
    let payload: Data
    if (kind.value === 'tasks') payload = { ...taskForm, due_date: taskForm.due_date || null, tags: [...new Set(tags.value.split(/[,，、]/).map(x => x.trim()).filter(Boolean))] }
    else if (kind.value === 'courses') { if (courseForm.start_time >= courseForm.end_time || courseForm.start_week > courseForm.end_week) throw new Error('结束时间或周数必须晚于开始。'); payload = { ...courseForm, term_start_date: courseForm.term_start_date || null } }
    else if (kind.value === 'exams') payload = { ...examForm }
    else payload = { ...recordForm }
    const path = endpoint(kind.value)
    if (editing.value) await api.patch(`${path}/${editing.value}`, payload); else await api.post(path, payload)
    await refresh(); dialog.value = false
  }, '已保存并刷新学习记录')
}
async function changeStatus(item: Data, value: string) { await run(async () => { await api.patch(`/tasks/${item.id}`, { status: value }); await refresh() }, '任务状态已更新') }
async function remove(value: string, item: Data) {
  if (!await confirmAction(`确定删除「${item.title || item.name || item.subject}」？此操作无法撤销。`)) return
  await run(async () => { await api.delete(`${endpoint(value)}/${item.id}`); await refresh(); if (editing.value === item.id) dialog.value = false }, '已删除')
}
watch(() => [route.query.tab, route.query.id], syncRoute)
onMounted(load)
</script>
<template>
  <section class="page">
    <PageHeader title="我的学习" eyebrow="让每一次努力，有明确的落点" description="课程、任务、考试与记录，在一个空间里安排清楚。">
      <RouterLink class="secondary" to="/plans"><Icon name="calendar" :size="17" /> 学习计划</RouterLink>
      <button class="primary" :disabled="busy" @click="open()"><Icon name="plus" :size="17" /> {{ tab === 'records' ? '记录学习' : tab === 'courses' ? '添加课程' : tab === 'exams' ? '添加考试' : '新建任务' }}</button>
    </PageHeader>
    <div class="tabs" role="tablist" aria-label="学习分类"><button v-for="item in tabs" :key="item.id" role="tab" :aria-selected="tab === item.id" :class="{ active: tab === item.id }" @click="selectTab(item.id)">{{ item.label }}</button></div>
    <div v-if="error" class="error-banner" role="alert">{{ error }}<button class="text-button" :disabled="busy" @click="load">重试</button></div>
    <div v-if="busy && !loaded" class="loading-panel">正在加载你的学习安排…</div>
    <template v-if="tab === 'tasks' && loaded">
      <div class="mini-stat-grid"><div v-for="item in stats" :key="item.label" class="mini-stat"><span>{{ item.label }}</span><strong>{{ item.count }}</strong></div></div>
      <section class="panel">
        <div class="panel-head wrap"><h2>任务清单 <span class="count-badge">{{ filtered.length }}</span></h2><div class="filters"><input v-model="query" placeholder="搜索标题、分类、标签…" aria-label="搜索任务" /><select v-model="status" aria-label="筛选任务状态"><option value="all">所有状态</option><option value="todo">待完成</option><option value="doing">进行中</option><option value="done">已完成</option><option value="overdue">已逾期</option></select></div></div>
        <div v-for="task in filtered" :key="task.id" class="task-row" :class="{ completed: task.status === 'done' }">
          <button class="task-check" :class="{ checked: task.status === 'done' }" :disabled="busy" :aria-label="task.status === 'done' ? '重新打开任务' : '标记为完成'" @click="changeStatus(task, task.status === 'done' ? 'todo' : 'done')"><Icon v-if="task.status === 'done'" name="check" :size="14" /></button>
          <div class="task-main"><button class="task-title" :disabled="busy" @click="open('tasks', task)">{{ task.title }}</button><p v-if="task.description" class="line-clamp">{{ task.description }}</p><div class="meta-row"><span>{{ task.category }} · {{ task.estimated_minutes }} 分钟</span><span :class="{ 'danger-text': task.overdue }">{{ task.due_date ? `截止 ${dateText(task.due_date)}` : '无截止日期' }}{{ task.overdue ? ' · 已逾期' : '' }}</span><span v-for="tag in task.tags" :key="tag" class="tag">{{ tag }}</span></div></div>
          <span :class="`priority p${task.priority}`">{{ ['', '高', '中', '低'][task.priority] }}</span>
          <select class="compact-select" :value="task.status" :disabled="busy" aria-label="更新任务状态" @change="changeStatus(task, ($event.target as HTMLSelectElement).value)"><option value="todo">待完成</option><option value="doing">进行中</option><option value="done">已完成</option></select>
          <button class="icon-button danger-text" :disabled="busy" title="删除任务" @click="remove('tasks', task)"><Icon name="trash" :size="17" /></button>
        </div>
        <EmptyState v-if="!filtered.length" :title="query || status !== 'all' ? '没有符合筛选条件的任务' : '从一个具体的小目标开始'" description="任务会同步到总览、学习计划和数据中心。" icon="check"><button class="text-button" :disabled="busy" @click="open('tasks')">创建任务 →</button></EmptyState>
      </section>
    </template>
    <section v-if="tab === 'courses' && loaded" class="panel">
      <div class="panel-head"><div><h2>每周课程表</h2><p>点开课程可编辑单双周、起止周与学期起始日期</p></div><span class="count-badge">{{ courses.length }} 门</span></div>
      <div class="week-grid"><div v-for="(day, index) in weekdays" :key="day" class="week-column"><h3>{{ day }}</h3><button v-for="course in courses.filter(c => c.weekday === index + 1)" :key="course.id" class="course-card" :disabled="busy" @click="open('courses', course)"><small>{{ course.start_time.slice(0, 5) }}–{{ course.end_time.slice(0, 5) }}</small><strong>{{ course.name }}</strong><span>{{ course.classroom || '地点待定' }}</span><span>{{ course.teacher || '教师未填写' }}</span><small>第 {{ course.start_week }}–{{ course.end_week }} 周 · {{ course.week_pattern === 'odd' ? '单周' : course.week_pattern === 'even' ? '双周' : '每周' }}</small></button><span v-if="!courses.some(c => c.weekday === index + 1)" class="week-empty">没有课程</span></div></div>
      <EmptyState v-if="!courses.length" title="把课程放进每周的节奏" description="添加课程后，总览会根据星期、学期周次筛选今日课程。" icon="calendar" />
    </section>
    <section v-if="tab === 'exams' && loaded" class="panel">
      <div class="panel-head"><h2>考试安排</h2><span class="count-badge">{{ exams.length }}</span></div>
      <div v-for="exam in exams" :key="exam.id" class="exam-row"><div class="date-block"><strong>{{ exam.exam_date.slice(8) }}</strong><span>{{ exam.exam_date.slice(5, 7) }} 月</span></div><div class="grow"><strong>{{ exam.subject }}</strong><small>{{ exam.exam_date }} · {{ exam.location || '地点待定' }}</small><p v-if="exam.notes" class="muted">{{ exam.notes }}</p></div><button class="secondary small" :disabled="busy" @click="open('exams', exam)">编辑</button><button class="icon-button danger-text" :disabled="busy" title="删除考试" @click="remove('exams', exam)"><Icon name="trash" :size="17" /></button></div>
      <EmptyState v-if="!exams.length" title="暂时没有考试安排" description="提前记下时间与地点，让复习更从容。" icon="calendar" />
    </section>
    <section v-if="tab === 'records' && loaded" class="panel"><div class="panel-head"><div><h2>真实学习记录</h2><p>每次记录都会计入统计 · 最近最多 1000 条</p></div><RouterLink class="text-button" to="/analytics">查看数据 →</RouterLink></div><div class="table-scroll" v-if="records.length"><table><thead><tr><th>学科 / 内容</th><th>学习分钟</th><th>记录时间</th><th>备注</th><th>操作</th></tr></thead><tbody><tr v-for="record in records" :key="record.id"><td><strong>{{ record.subject }}</strong></td><td>{{ record.minutes }} 分钟</td><td>{{ new Date(record.studied_at).toLocaleString('zh-CN') }}</td><td class="table-note">{{ record.note || '—' }}</td><td><button class="icon-button danger-text" :disabled="busy" title="删除记录" @click="remove('records', record)"><Icon name="trash" :size="17" /></button></td></tr></tbody></table></div><EmptyState v-else title="第一次专注，从这里留下记录" description="记录已完成的学习，不把预计时间算作实际学习。" icon="clock" /></section>
    <ElDialog v-model="dialog" :title="`${editing ? '编辑' : '添加'}${kind === 'tasks' ? '任务' : kind === 'courses' ? '课程' : kind === 'exams' ? '考试' : '学习记录'}`" width="600px" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <form class="stack-form" @submit.prevent="save">
        <fieldset :disabled="busy">
          <template v-if="kind === 'tasks'"><label>任务标题<input v-model.trim="taskForm.title" required maxlength="120" placeholder="例如：完成数据库第三章笔记" /></label><label>说明<textarea v-model="taskForm.description" rows="3" maxlength="5000" /></label><div class="form-row"><label>截止日期<input v-model="taskForm.due_date" type="date" /></label><label>预计分钟<input v-model.number="taskForm.estimated_minutes" type="number" min="1" max="1440" required /></label></div><div class="form-row"><label>优先级<select v-model.number="taskForm.priority"><option :value="1">高优先级</option><option :value="2">普通</option><option :value="3">低优先级</option></select></label><label>状态<select v-model="taskForm.status"><option v-for="s in ['todo', 'doing', 'done']" :value="s" :key="s">{{ statusText(s) }}</option></select></label></div><div class="form-row"><label>分类<input v-model="taskForm.category" maxlength="50" /></label><label>标签（逗号分隔，最多 12 个）<input v-model="tags" placeholder="复习、数据库" maxlength="370" /></label></div></template>
          <template v-else-if="kind === 'courses'"><label>课程名称<input v-model.trim="courseForm.name" required maxlength="80" /></label><div class="form-row"><label>教师<input v-model="courseForm.teacher" maxlength="80" /></label><label>教室<input v-model="courseForm.classroom" maxlength="120" /></label></div><div class="form-row"><label>星期<select v-model.number="courseForm.weekday"><option v-for="(day, i) in weekdays" :key="day" :value="i + 1">{{ day }}</option></select></label><label>上课周期<select v-model="courseForm.week_pattern"><option value="all">每周</option><option value="odd">单周</option><option value="even">双周</option></select></label></div><div class="form-row"><label>开始时间<input v-model="courseForm.start_time" type="time" required /></label><label>结束时间<input v-model="courseForm.end_time" type="time" required /></label></div><div class="form-row"><label>起始周<input v-model.number="courseForm.start_week" type="number" min="1" max="60" required /></label><label>结束周<input v-model.number="courseForm.end_week" type="number" min="1" max="60" required /></label></div><label>学期起始日期（可选）<input v-model="courseForm.term_start_date" type="date" /></label><p class="field-help">用于计算今日课程所属周次；未设置时只按星期显示。</p></template>
          <template v-else-if="kind === 'exams'"><label>考试科目<input v-model.trim="examForm.subject" required maxlength="80" /></label><label>考试日期<input v-model="examForm.exam_date" type="date" required /></label><label>考试地点<input v-model="examForm.location" maxlength="160" /></label><label>复习 / 注意事项<textarea v-model="examForm.notes" rows="4" maxlength="5000" /></label></template>
          <template v-else><label>学科 / 学习内容<input v-model.trim="recordForm.subject" required maxlength="80" /></label><label>已学习分钟<input v-model.number="recordForm.minutes" type="number" min="1" max="1440" required /></label><label>备注<textarea v-model="recordForm.note" rows="4" maxlength="5000" /></label><p class="field-help">时间由服务端记录为当前时间，请仅填写真实完成的学习时长。</p></template>
        </fieldset>
        <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
        <div class="dialog-actions"><button v-if="editing && kind === 'courses'" type="button" class="danger mr-auto" :disabled="busy" @click="remove('courses', { id: editing, name: courseForm.name })">删除课程</button><button type="button" class="secondary" :disabled="busy" @click="dialog = false">取消</button><button class="primary" :disabled="busy">{{ busy ? '正在保存…' : '保存' }}</button></div>
      </form>
    </ElDialog>
  </section>
</template>
