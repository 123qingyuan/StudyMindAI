<script setup lang="ts">
import { useTheme, type ThemeMode } from '../composables/useTheme'
defineProps<{ compact?: boolean }>()
const { mode, setTheme } = useTheme()
const options: { value: ThemeMode; label: string }[] = [{ value: 'light', label: '浅色' }, { value: 'dark', label: '深色' }, { value: 'system', label: '跟随系统' }]
</script>
<template>
  <label v-if="compact" class="theme-compact"><span class="sr-only">外观主题</span><select aria-label="外观主题" :value="mode" @change="setTheme(($event.target as HTMLSelectElement).value as ThemeMode)"><option v-for="item in options" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
  <div v-else class="theme-options" role="group" aria-label="外观主题"><button v-for="item in options" :key="item.value" type="button" :aria-pressed="mode === item.value" @click="setTheme(item.value)"><span class="theme-preview" :class="item.value" aria-hidden="true"><i /><i /></span><strong>{{ item.label }}</strong><span>{{ mode === item.value ? '已选择' : '选择外观' }}</span></button></div>
</template>
<style scoped>
.theme-compact select { width:112px; min-height:36px; background:var(--surface); color:var(--ink-soft); font-size:12px; }
.theme-options { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.theme-options button { display:grid; gap:7px; padding:12px; text-align:left; color:var(--ink); background:var(--surface); border:1px solid var(--line-strong); border-radius:9px; }
.theme-options button[aria-pressed=true] { border-color:var(--primary); background:var(--primary-soft); }
.theme-options button:hover { border-color:var(--primary); }
.theme-options strong { font-size:13px; }.theme-options button>span:last-child { font-size:12px; color:var(--muted); }
.theme-preview { display:flex; gap:8px; height:60px; padding:8px; border:1px solid var(--line-strong); border-radius:6px; background:#f3f5f8; }
.theme-preview i:first-child { width:24%; background:#dfe4ec; border-radius:3px; }.theme-preview i:last-child { flex:1; background:#fff; border-radius:3px; }
.theme-preview.dark { background:#10151f; }.theme-preview.dark i:first-child { background:#222b3a; }.theme-preview.dark i:last-child { background:#191f2b; }
.theme-preview.system { background:linear-gradient(90deg,#f3f5f8 50%,#10151f 50%); }.theme-preview.system i { opacity:.45; }
.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
@media(max-width:640px) { .theme-compact select { width:100px; min-height:44px; }.theme-options { gap:8px; }.theme-options button { padding:9px; }.theme-preview { height:45px; } }
</style>
