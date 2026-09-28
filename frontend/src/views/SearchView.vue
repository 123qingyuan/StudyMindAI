<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type Data } from '../api/client'
import { useRequest } from '../composables/useRequest'
import PageHeader from '../components/PageHeader.vue'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
const route = useRoute(); const router = useRouter(); const { run, busy, error } = useRequest(); const query = ref(String(route.query.q || '')); const results = ref<Data | null>(null); const loadedQuery = ref('');
const groups = computed(() => [{ key: 'documents', label: '文档', icon: 'file', items: results.value?.documents || [], title: (x: Data) => x.original_name, text: (x: Data) => x.snippet, to: '/documents' }, { key: 'notes', label: '笔记', icon: 'edit', items: results.value?.notes || [], title: (x: Data) => x.title, text: (x: Data) => x.snippet, to: '/knowledge' }, { key: 'tasks', label: '任务', icon: 'check', items: results.value?.tasks || [], title: (x: Data) => x.title, text: (x: Data) => `${x.category || '学习'} · ${x.due_date || '无截止日期'}`, to: '/learning' }])
const total = computed(() => groups.value.reduce((n, x) => n + x.items.length, 0))
async function search() { const value = query.value.trim(); if (!value) { results.value = null; return }; await run(async () => { results.value = await api.get(`/search?q=${encodeURIComponent(value)}`); loadedQuery.value = value; await router.replace({ path: '/search', query: { q: value } }) }) }
function navigate(group: Data, item: Data) { if (group.key === 'tasks') void router.push({ path: '/learning', query: { id: item.id } }); else void router.push(group.to) }
watch(() => route.query.q, value => { if (String(value || '').trim() && String(value) !== loadedQuery.value) { query.value = String(value); void search() } })
onMounted(() => { if (query.value) void search() })
</script>
<template><section class="page"><PageHeader title="全局搜索" eyebrow="把已经学过的内容重新找回来" description="搜索任务、笔记与文档标题和已提取文本"><form class="search-hero" @submit.prevent="search"><Icon name="search" :size="22" /><input v-model="query" maxlength="100" autofocus placeholder="输入关键词，例如：主键、Python、期末复习" /><button class="primary" :disabled="busy || !query.trim()">{{ busy ? '搜索中…' : '搜索' }}</button></form></PageHeader><div v-if="error" class="error-banner" role="alert">{{ error }}<button class="text-button" @click="search">重试</button></div><template v-if="results"><div class="search-summary"><strong>“{{ loadedQuery }}”</strong><span>找到 {{ total }} 条结果</span></div><div class="search-results"><section v-for="group in groups" :key="group.key" class="panel result-group"><div class="panel-head"><h2><Icon :name="group.icon" :size="19" /> {{ group.label }} <span class="count-badge">{{ group.items.length }}</span></h2></div><button v-for="item in group.items" :key="item.id" class="result-item" @click="navigate(group, item)"><Icon :name="group.icon" :size="18" /><div><strong>{{ group.title(item) }}</strong><p>{{ group.text(item) || '没有匹配片段' }}</p></div><Icon name="arrow" :size="16" /></button><EmptyState v-if="!group.items.length" :title="`没有命中的${group.label}`" icon="search" /></section></div></template><EmptyState v-else title="从一个关键词开始" description="搜索会读取你的任务、笔记和已上传文档，不会搜索其他账户的数据。" icon="search"><p class="muted">支持回车搜索，结果可跳转回对应页面。</p></EmptyState></section></template>
