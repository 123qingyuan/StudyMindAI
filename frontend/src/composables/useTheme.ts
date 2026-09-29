import { ref } from 'vue'
export type ThemeMode = 'system' | 'light' | 'dark'
const query = window.matchMedia('(prefers-color-scheme: dark)')
function stored(): ThemeMode {
  try { const value = localStorage.getItem('studymind.theme'); if (value === 'dark' || value === 'light') return value } catch { /* Storage may be disabled. */ }
  return 'system'
}
const mode = ref<ThemeMode>(stored())
const resolved = ref<'light' | 'dark'>('light')
function apply() {
  resolved.value = mode.value === 'system' ? (query.matches ? 'dark' : 'light') : mode.value
  document.documentElement.classList.toggle('dark', resolved.value === 'dark')
  document.documentElement.dataset.theme = resolved.value
  document.documentElement.style.colorScheme = resolved.value
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved.value === 'dark' ? '#10151f' : '#f3f5f8')
}
function setTheme(value: ThemeMode) {
  mode.value = value
  try { localStorage.setItem('studymind.theme', value) } catch { /* Still apply for this session. */ }
  apply()
}
query.addEventListener('change', apply)
window.addEventListener('storage', e => { if (e.key === 'studymind.theme') { mode.value = stored(); apply() } })
apply()
export function useTheme() { return { mode, resolved, setTheme } }
