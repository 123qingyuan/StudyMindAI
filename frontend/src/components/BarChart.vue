<script setup lang="ts">
import { computed } from 'vue'
import EmptyState from './EmptyState.vue'
const props = defineProps<{ items: { day: string; minutes: number }[] }>()
const max = computed(() => Math.max(...props.items.map(x => x.minutes), 1))
</script>
<template><div v-if="items.length" class="bar-chart" role="img" aria-label="每日学习分钟柱状图"><div v-for="item in items" :key="item.day" class="bar-column"><span class="bar-number">{{ item.minutes }}</span><div class="bar-track"><div class="bar-fill" :style="{ height: `${item.minutes / max * 100}%` }" :title="`${item.day}：${item.minutes} 分钟`"></div></div><span class="bar-label">{{ item.day.slice(5) }}</span></div></div><EmptyState v-else title="数据从第一次记录开始" description="记录一段学习后，这里将呈现你的真实学习趋势。" icon="chart" /></template>
