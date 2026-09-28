type Message = string | { message: string; duration?: number }
function notify(value: Message, type: 'success' | 'error' | 'warning') {
  const detail = typeof value === 'string' ? { message: value, type } : { ...value, type }
  window.dispatchEvent(new CustomEvent('studymind:toast', { detail }))
}
export const ElMessage = {
  success: (value: Message) => notify(value, 'success'),
  error: (value: Message) => notify(value, 'error'),
  warning: (value: Message) => notify(value, 'warning'),
}
