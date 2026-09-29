import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { ElDialog, ElMessage } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/message/style/css'
import 'katex/dist/katex.min.css'
import App from './App.vue'
import router from './router'
import './tokens.css'
import './composables/useTheme'
import './style.css'
import './workspace.css'

// Never migrate legacy persistent credentials into the new session-only store.
localStorage.removeItem('studymind_token')
localStorage.removeItem('studymind_user')
window.addEventListener('studymind:toast', event => {
  const detail = (event as CustomEvent).detail
  if (detail?.message) ElMessage({ message: String(detail.message), type: detail.type || 'info', duration: 4000 })
})
const app = createApp(App).use(createPinia()).use(router).component('ElDialog', ElDialog)
// Wait for the authentication guard before mounting private layout requests.
void router.isReady().then(() => app.mount('#app'))
