<script setup lang="ts">
import { computed } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
const props = defineProps<{ value: unknown }>()
const text = computed(() => {
  const value = props.value as any
  if (typeof value === 'string') return value
  if (!value) return ''
  if (typeof value.summary === 'string') return value.summary
  if (typeof value.content === 'string') return `${value.title ? `## ${value.title}\n\n` : ''}${value.content}`
  if (Array.isArray(value.keywords)) return value.keywords.map((x: unknown) => `- ${String(x)}`).join('\n')
  if (Array.isArray(value.points)) return value.points.map((x: any) => `### ${x.title || ''}\n\n${x.description || ''}`).join('\n\n')
  if (Array.isArray(value.questions)) return value.questions.map((x: any, i: number) => `### ${i + 1}. ${x.stem || ''}\n\n**参考答案**：${typeof x.answer === 'string' ? x.answer : JSON.stringify(x.answer)}\n\n${x.explanation || ''}`).join('\n\n')
  if (value.root && Array.isArray(value.children)) {
    const walk = (items: any[], depth = 0): string => depth > 12 ? '' : items.map(x => `${'  '.repeat(depth)}- ${x.title || x.name || ''}\n${Array.isArray(x.children) ? walk(x.children, depth + 1) : ''}`).join('\n')
    return `## ${value.root}\n\n${walk(value.children)}`
  }
  return ''
})
const json = computed(() => JSON.stringify(props.value, null, 2))
</script>
<template><MarkdownContent v-if="text" :content="text" /><pre v-else-if="value != null" class="json-result">{{ json }}</pre><p v-else class="muted">服务没有返回可展示的内容。</p></template>
