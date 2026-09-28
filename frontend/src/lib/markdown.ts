import MarkdownIt, { type RendererRule, type StateBlock, type StateInline, type Token } from 'markdown-it'
import katex from 'katex'
import hljs from 'highlight.js/lib/common'
import DOMPurify from 'dompurify'
let md: InstanceType<typeof MarkdownIt>
const highlight = (code: string, language: string): string => `<pre class="hljs"><code>${language && hljs.getLanguage(language) ? hljs.highlight(code, { language, ignoreIllegals: true }).value : md.utils.escapeHtml(code)}</code></pre>`
md = new MarkdownIt({ html: false, linkify: true, breaks: true, highlight })
function math(source: string, displayMode = false) { try { return katex.renderToString(source, { displayMode, throwOnError: false, trust: false, strict: 'ignore', output: 'htmlAndMathml' }) } catch { return md.utils.escapeHtml(source) } }
md.inline.ruler.before('escape', 'math_inline', (state: StateInline, silent: boolean) => {
  if (state.src[state.pos] !== '$' || state.src[state.pos + 1] === '$') return false
  let end = state.pos + 1
  while ((end = state.src.indexOf('$', end)) !== -1 && state.src[end - 1] === '\\') end++
  if (end < 0 || end === state.pos + 1 || state.src.slice(state.pos + 1, end).includes('\n')) return false
  if (!silent) { const token = state.push('math_inline', 'math', 0); token.content = state.src.slice(state.pos + 1, end) }
  state.pos = end + 1; return true
})
md.renderer.rules.math_inline = ((tokens: Token[], index: number) => math(tokens[index].content))
md.block.ruler.before('fence', 'math_block', (state: StateBlock, startLine: number, endLine: number, silent: boolean) => {
  const start = state.bMarks[startLine] + state.tShift[startLine]
  if (!state.src.slice(start, state.eMarks[startLine]).startsWith('$$')) return false
  if (silent) return true
  let line = startLine; let content = state.src.slice(start + 2, state.eMarks[startLine]); let found = content.trimEnd().endsWith('$$')
  if (found) content = content.trimEnd().slice(0, -2)
  else {
    while (++line < endLine) {
      const text = state.src.slice(state.bMarks[line] + state.tShift[line], state.eMarks[line])
      if (text.trimEnd().endsWith('$$')) { content += '\n' + text.trimEnd().slice(0, -2); found = true; break }
      content += '\n' + text
    }
  }
  if (!found) return false
  const token = state.push('math_block', 'math', 0); token.content = content; token.block = true
  state.line = line + 1; return true
})
md.renderer.rules.math_block = (tokens: Token[], index: number) => `<div class="math-block">${math(tokens[index].content, true)}</div>`
const defaultLink = md.renderer.rules.link_open
md.renderer.rules.link_open = (tokens, index, options, env, self) => { tokens[index].attrSet('target', '_blank'); tokens[index].attrSet('rel', 'noopener noreferrer'); return defaultLink ? defaultLink(tokens, index, options, env, self) : self.renderToken(tokens, index, options) }
// Remote images in untrusted document text are not loaded (privacy and tracking).
md.renderer.rules.image = (tokens, index) => `<span class="image-alt">[图片：${md.utils.escapeHtml(tokens[index].content || '未命名')}]</span>`
export function renderMarkdown(value: string) {
  return DOMPurify.sanitize(md.render(value || ''), { ADD_ATTR: ['target'], FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'style'] })
}
