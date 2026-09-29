import { createRouter, createWebHashHistory } from 'vue-router'

export const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: () => import('../views/AuthView.vue'), meta: { title: '账户登录', public: true } },
  { path: '/dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '学习总览' } },

  { path: '/chat', component: () => import('../views/ChatView.vue'), meta: { title: 'AI 学习助手' } },
  { path: '/learning', component: () => import('../views/LearningView.vue'), meta: { title: '我的学习' } },
  { path: '/plans', component: () => import('../views/PlansView.vue'), meta: { title: '学习计划' } },
  { path: '/documents', component: () => import('../views/DocumentsView.vue'), meta: { title: '资料管理' } },
  { path: '/knowledge', component: () => import('../views/KnowledgeView.vue'), meta: { title: '知识库' } },
  { path: '/questions', component: () => import('../views/QuestionsView.vue'), meta: { title: '练习题库' } },

  { path: '/analytics', component: () => import('../views/AnalyticsView.vue'), meta: { title: '数据与报告' } },
  { path: '/settings', component: () => import('../views/SettingsView.vue'), meta: { title: '空间设置' } },
  { path: '/search', component: () => import('../views/SearchView.vue'), meta: { title: '全局搜索' } },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach(to => {
  if (!to.meta.public && !sessionStorage.getItem('studymind_token')) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && sessionStorage.getItem('studymind_token')) return '/dashboard'
})
router.afterEach(to => { document.title = `${to.meta.title || '学习空间'} · StudyMind` })
export default router
