export type Data = Record<string, any>
export class ApiError extends Error {
  constructor(message: string, public status = 0, public code = '') { super(message); this.name = 'ApiError' }
}
function headers(body?: unknown): Headers {
  const value = new Headers()
  if (!(body instanceof FormData)) value.set('Content-Type', 'application/json')
  const token = sessionStorage.getItem('studymind_token')
  if (token) value.set('Authorization', `Bearer ${token}`)
  return value
}
async function checked(response: Response) {
  if (response.ok) return response
  let data: Data = {}
  try { data = await response.json() } catch { /* Non-JSON upstream failure */ }
  const detail = data.detail || data.error
  const validation = detail?.details?.map((x: Data) => `${x.field || '参数'}：${x.message}`).join('；')
  const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => `${x.loc?.slice(1).join('.') || '参数'}：${x.msg}`).join('；') : validation || detail?.message || data.message
  if (response.status === 401 && !response.url.includes('/auth/login')) {
    sessionStorage.removeItem('studymind_token'); sessionStorage.removeItem('studymind_user')
    window.dispatchEvent(new Event('studymind:unauthorized'))
  }
  throw new ApiError(message || (response.status === 404 ? '此接口暂不可用，请检查后端版本。' : `请求失败（${response.status}）`), response.status, detail?.code)
}
async function request<T = Data>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try { response = await fetch(`/api${path}`, { method, headers: headers(body), body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body) }) }
  catch { throw new ApiError('无法连接服务，请检查后端是否启动或网络连接。') }
  await checked(response)
  if (response.status === 204) return undefined as T
  return response.json()
}
export async function downloadFile(path: string, filename: string) {
  let response: Response
  try { response = await fetch(`/api${path}`, { headers: headers() }) } catch { throw new ApiError('文件下载失败，请检查网络连接。') }
  await checked(response)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export const api = {
  get: <T = Data>(path: string) => request<T>('GET', path),
  post: <T = Data>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T = Data>(path: string, body: unknown) => request<T>('PATCH', path, body),
  put: <T = Data>(path: string, body: unknown) => request<T>('PUT', path, body),
  delete: <T = Data>(path: string) => request<T>('DELETE', path),
}
export async function stream(path: string, body: unknown, signal: AbortSignal, onEvent: (event: string, data: Data) => void) {
  const response = await checked(await fetch(`/api${path}`, { method: 'POST', headers: headers(), body: JSON.stringify(body), signal }))
  if (!response.body) throw new ApiError('浏览器不支持流式响应。')
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let ended = false
  function dispatch(part: string) {
    const lines = part.split('\n'); const event = lines.find(x => x.startsWith('event:'))?.slice(6).trim() || 'message'
    const text = lines.filter(x => x.startsWith('data:')).map(x => x.slice(5).trimStart()).join('\n')
    if (!text || text === '[DONE]') return
    let data: Data
    try { data = JSON.parse(text) } catch { throw new ApiError('服务返回了无法解析的流式数据。') }
    if (event === 'message_end') ended = true
    onEvent(event, data)
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) { dispatch(buffer.slice(0, boundary)); buffer = buffer.slice(boundary + 2) }
      if (done) { if (buffer.trim()) dispatch(buffer); break }
    }
    if (!ended && !signal.aborted) throw new ApiError('连接提前结束，回答可能不完整。请重试。')
  } finally { reader.releaseLock() }
}
