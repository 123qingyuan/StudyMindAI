<script setup lang="ts">import Icon from './Icon.vue'; withDefaults(defineProps<{ title?: string; description?: string; icon?: string }>(), { title: '这里还没有内容', icon: 'layers' })</script>
<template><div class="empty-state"><div class="empty-icon"><Icon :name="icon" :size="28" /></div><h3>{{ title }}</h3><p v-if="description">{{ description }}</p><slot /></div></template>
