export async function confirmAction(message: string, title = '请确认操作') {
  return window.confirm(`${title}\n\n${message}`)
}
export async function promptText(message: string, value: string) {
  const result = window.prompt(message, value)
  return result?.trim() && result.trim().length <= 120 ? result.trim() : null
}
export async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); window.dispatchEvent(new CustomEvent('studymind:toast', { detail: { message: '已复制到剪贴板', type: 'success' } })) } catch { window.dispatchEvent(new CustomEvent('studymind:toast', { detail: { message: '复制失败，请手动选择文字复制。', type: 'error' } })) }
}
export const dateText = (value?: string) => value ? value.slice(0, 10) : '未设置'
export const localDay = (offset = 0) => { const date = new Date(); date.setDate(date.getDate() + offset); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
export const labels: Record<string, string> = { todo: '待完成', doing: '进行中', done: '已完成', ready: '可阅读', indexed: '已索引', completed: '已完成', generating: '生成中', failed: '失败', parse_failed: '解析失败', ocr_pending: '待识别', unsupported: '格式不支持', draft: '草稿', published: '已发布', pending_confirmation: '待审核', cancelled: '已取消', cancelled_by_user: '已停止', stopped: '已停止', running: '执行中', pending: '等待中', low: '低', medium: '中', high: '高' }
Object.assign(labels, { semantic: '语义索引', keyword: '关键词检索', not_indexed: '未索引', superseded: '已由新回答替代' })
export const statusText = (status: string) => labels[status] || status
export const modes = [{ value: 'tutor', label: '学习导师', desc: '拆解概念，循序理解' }, { value: 'general', label: '通用助手', desc: '日常问题，清晰解答' }, { value: 'code', label: '代码导师', desc: '从思路到可运行代码' }, { value: 'paper', label: '论文助手', desc: '梳理论点与文章结构' }, { value: 'english', label: '英语老师', desc: '纠错、表达与练习' }, { value: 'math', label: '数学老师', desc: '逐步推导，掌握方法' }]
