import { ref } from 'vue'
export function useRequest() {
  const busy = ref(false); const error = ref('')
  function toast(message: string, type: 'success' | 'error') { window.dispatchEvent(new CustomEvent('studymind:toast', { detail: { message, type } })) }
  async function run<T>(action: () => Promise<T>, message = ''): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true; error.value = ''
    try { const value = await action(); if (message) toast(message, 'success'); return value }
    catch (e) { error.value = e instanceof Error ? e.message : String(e); toast(error.value, 'error'); return undefined }
    finally { busy.value = false }
  }
  return { busy, error, run }
}
