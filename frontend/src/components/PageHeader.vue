<script setup lang="ts">defineProps<{ title: string; description?: string; eyebrow?: string }>()</script>
<template><div class="page-heading"><div><h1>{{ title }}</h1><p v-if="description">{{ description }}</p></div><div class="heading-actions"><slot /></div></div></template>
