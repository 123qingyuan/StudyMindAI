<script setup lang="ts">
withDefaults(defineProps<{ name?: string; size?: number }>(), { name: 'spark', size: 20 })
const paths: Record<string, string> = {
  home: 'm3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Zm6 11v-8h6v8',
  spark: 'm12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z',
  book: 'M12 6C8 3 4 4 2 5v15c3-2 7-1 10 1 3-2 7-3 10-1V5c-3-1-6-2-10 1v15',
  file: 'M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8l-6-6v6h6M8 13h8M8 17h5',
  layers: 'm12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5',
  agent: 'M8 4h8M12 4V2M5 7h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2ZM8 12h.01M16 12h.01M8 17h8M1 12h2M21 12h2',
  chart: 'M4 3v18h18M8 17v-5M13 17V8M18 17V4',
  check: 'm5 12 4 4L19 6',
  question: 'M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 18h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  settings: 'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM9 3l1-1h4l1 3 3 1 3 1 1 4-2 2 1 4-3 3-4-1-2 2-4-1-1-3-3-1-1-4 2-2-1-4 3-3 3 1Z',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  plus: 'M12 5v14M5 12h14', menu: 'M4 6h16M4 12h16M4 18h16', close: 'm6 6 12 12M6 18 18 6',
  arrow: 'M4 12h16m-6-6 6 6-6 6', send: 'm3 3 19 9-19 9 4-9-4-9Zm4 9h15',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7',
  edit: 'm15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z',
  clock: 'M12 7v5l3 3M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6', logout: 'M9 3H3v18h6M9 12h12m-4-4 4 4-4 4',
  copy: 'M9 9h12v12H9V9ZM5 15H3V3h12v2', refresh: 'M20 7V2m0 5h-5M4 17v5m0-5h5M5 7a8 8 0 0 1 15 0M4 17a8 8 0 0 0 15 0',
  calendar: 'M4 5h16v16H4V5ZM8 2v6M16 2v6M4 10h16', stop: 'M6 6h12v12H6V6Z',
  shield: 'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-4 10 3 3 5-6'
}
</script>
<template><svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.spark" /></svg></template>
