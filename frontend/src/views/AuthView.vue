<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Icon from '../components/Icon.vue'
import ThemePicker from '../components/ThemePicker.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const register = ref(false)
const error = ref('')
const showPassword = ref(false)
const heading = ref<HTMLElement | null>(null)
const errorNotice = ref<HTMLElement | null>(null)
const form = reactive({ email: '', password: '', display_name: '' })
async function switchMode() {
  if (auth.busy) return
  register.value = !register.value
  error.value = ''
  form.password = ''
  showPassword.value = false
  await nextTick()
  heading.value?.focus()
}
async function submit() {
  if (auth.busy) return
  error.value = ''
  try {
    if (register.value) await auth.register({ email: form.email, password: form.password, display_name: form.display_name })
    else await auth.login({ email: form.email, password: form.password })
    form.password = ''
    const redirect = String(route.query.redirect || '/dashboard')
    await router.replace(redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/dashboard')
  } catch (e) {
    error.value = e instanceof Error ? e.message : register.value ? '注册暂未完成，请稍后重试。' : '登录暂未完成，请稍后重试。'
    await nextTick()
    errorNotice.value?.focus()
  }
}
</script>

<template>
  <main id="main-content" class="entry-layout">
    <section class="entry-story" aria-label="StudyMind 个人学习空间">
      <div class="ambient" aria-hidden="true"><div class="ambient-glow" /><div class="ambient-grid" /></div>
      <div class="entry-brand"><span class="entry-mark"><Icon name="spark" :size="25" /></span><span>StudyMind<span class="brand-caption">智学 · 个人学习空间</span></span></div>
      <div class="story-body">

        <h1>让好奇心，<br />成为你的<span class="accent-word">引力。</span></h1>
        <p class="story-description">把散落的知识连接起来，<br />在自己的节奏里，走得更远。</p>
        <div class="knowledge-art" aria-hidden="true">
          <div class="orbit orbit-outer" /><div class="orbit orbit-inner" />
          <div class="orbit-axis" /><div class="orbit-core"><Icon name="spark" :size="46" /></div>
          <span class="orbit-node node-one"><Icon name="book" :size="20" /></span>
          <span class="orbit-node node-two"><Icon name="layers" :size="20" /></span>
          <span class="orbit-node node-three"><Icon name="check" :size="20" /></span>
          <span class="orbit-dot dot-one" /><span class="orbit-dot dot-two" />
          <span class="art-caption">探索 / 连接 / 理解</span>
        </div>
      </div>
      <footer class="story-footer"><span>知识积累 · 练习巩固 · 计划复盘</span><span class="footer-line" /><span>专注每一步</span></footer>
    </section>

    <section class="entry-panel" aria-labelledby="auth-title">
      <div class="panel-top"><span class="workspace-label"><span /> 你的个人学习空间</span><ThemePicker compact /></div>
      <div class="entry-form-card">
        <span class="form-symbol"><Icon :name="register ? 'layers' : 'spark'" :size="25" /></span>
        <div class="form-heading">
          <h2 id="auth-title" ref="heading" tabindex="-1">{{ register ? '创建学习空间' : '欢迎回来' }}<span class="heading-dot">.</span></h2>
          <p class="form-description">{{ register ? '一个账户，收纳你的知识、计划与成长。' : '登录 StudyMind，让每一次学习都有所沉淀。' }}</p>
        </div>
        <form :aria-busy="auth.busy" @submit.prevent="submit">
          <fieldset :disabled="auth.busy">
            <div v-if="register" class="entry-field"><label for="auth-name">你的称呼</label><input id="auth-name" v-model.trim="form.display_name" placeholder="怎么称呼你？" autocomplete="nickname" required maxlength="40" /></div>
            <div class="entry-field"><label for="auth-email">邮箱地址</label><input id="auth-email" v-model.trim="form.email" type="email" placeholder="name@example.com" autocomplete="username" inputmode="email" :spellcheck="false" autocapitalize="none" required maxlength="254" /></div>
            <div class="entry-field"><label for="auth-password">密码</label><div class="password-control"><input id="auth-password" v-model="form.password" :type="showPassword ? 'text' : 'password'" :autocomplete="register ? 'new-password' : 'current-password'" :placeholder="register ? '设置至少 8 位密码' : '输入你的密码'" :minlength="register ? 8 : 1" maxlength="128" required :aria-describedby="register ? 'password-help' : undefined" /><button class="password-toggle" type="button" :aria-label="showPassword ? '隐藏输入内容' : '显示输入内容'" :aria-pressed="showPassword" aria-controls="auth-password" @click="showPassword = !showPassword"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /><path v-if="showPassword" d="m3 3 18 18" /></svg></button></div><p v-if="register" id="password-help" class="password-help">至少 8 位，建议组合使用字母、数字与符号。</p></div>
          </fieldset>
          <p v-if="error" id="auth-error" ref="errorNotice" class="entry-error" role="alert" tabindex="-1"><Icon name="question" :size="18" /><span>{{ error }}</span></p>
          <button class="entry-submit" type="submit" :disabled="auth.busy"><span v-if="auth.busy" class="submit-spinner" aria-hidden="true" /><span>{{ auth.busy ? (register ? '正在创建账户…' : '正在登录…') : register ? '创建账户并开始' : '登录学习空间' }}</span><Icon v-if="!auth.busy" name="arrow" :size="18" /></button>
          <span class="sr-only" role="status">{{ auth.busy ? '正在处理，请稍候' : '' }}</span>
        </form>
        <div class="entry-switch"><span>{{ register ? '已经拥有账户？' : '还没有账户？' }}</span><button type="button" :disabled="auth.busy" @click="switchMode">{{ register ? '返回登录' : '立即注册' }}<Icon name="arrow" :size="14" /></button></div>
        <div class="session-note"><Icon name="shield" :size="16" /><p>登录令牌仅保存在当前浏览器会话中</p></div>
      </div>
      <footer class="panel-footer"><span>留一点时间，给更好的自己。</span><span>智学 · StudyMind</span></footer>
    </section>
  </main>
</template>

<style scoped>
.entry-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); min-height: 100vh; min-height: 100svh; background: var(--canvas); }
.entry-story { position: relative; isolation: isolate; display: flex; flex-direction: column; overflow: hidden; min-height: 100vh; padding: 42px clamp(36px, 4.5vw, 76px) 32px; color: #f6f5ff; background: #141627; }
.ambient { position: absolute; z-index: -1; inset: 0; pointer-events: none; overflow: hidden; }
.ambient-glow { position: absolute; inset: -25%; background: radial-gradient(ellipse at 70% 65%, #6755ac66, transparent 48%), radial-gradient(ellipse at 5% 10%, #40547040, transparent 43%), radial-gradient(ellipse at 20% 90%, #294e5a55, transparent 42%); animation: ambient-drift 22s ease-in-out infinite alternate; }
.ambient-grid { position: absolute; inset: 0; opacity: .16; background-image: linear-gradient(#9295c029 1px, transparent 1px), linear-gradient(90deg, #9295c029 1px, transparent 1px); background-size: 64px 64px; mask-image: linear-gradient(transparent, #000 80%); }
.entry-brand { display: flex; align-items: center; gap: 12px; font-size: 21px; font-weight: 650; letter-spacing: -.6px; }
.entry-mark { display: grid; place-items: center; width: 43px; height: 43px; color: #e8e4ff; border: 1px solid #a99cec55; border-radius: 13px; background: url('/studymind-mark.svg') center / cover no-repeat; box-shadow: inset 0 1px #ffffff20; }
.entry-mark svg { visibility: hidden; }
.brand-caption { display: block; margin-top: 4px; font-size: 10px; color: #b5b5cc; font-weight: 400; letter-spacing: 1.2px; }
.story-body { width: 100%; max-width: 520px; margin: auto; padding-top: 66px; }
.story-kicker { display: flex; align-items: center; gap: 10px; color: #c6bfdc; font-size: 12px; letter-spacing: 2px; }
.story-kicker > span { width: 20px; height: 1px; background: #b7a7e4; }
h1 { margin: 24px 0 20px; font-size: clamp(36px, 3.7vw, 58px); line-height: 1.35; font-weight: 550; letter-spacing: -2px; }
.accent-word { color: #c5b7fa; }
.story-description { margin: 0; color: #b6b7ce; font-size: 14px; line-height: 1.95; letter-spacing: .4px; }
.knowledge-art { position: relative; width: 100%; height: 278px; margin-top: 22px; pointer-events: none; }
.orbit { position: absolute; left: 50%; top: 48%; border: 1px solid #b6a5e433; border-radius: 50%; transform: translate(-50%, -50%) rotate(-24deg); }
.orbit-outer { width: 98%; height: 174px; box-shadow: 0 0 50px #8970d90b, inset 0 0 40px #a299ea08; }
.orbit-inner { width: 71%; height: 220px; transform: translate(-50%, -50%) rotate(34deg); border-color: #b6a5e420; }
.orbit-axis { position: absolute; top: 48%; left: 6%; width: 88%; height: 1px; background: linear-gradient(90deg, transparent, #aa98df38, transparent); transform: rotate(-24deg); }
.orbit-core { position: absolute; left: 50%; top: 48%; display: grid; place-items: center; width: 98px; height: 98px; color: #eee7ff; border: 1px solid #c2b4f573; border-radius: 28px; transform: translate(-50%, -50%) rotate(-12deg); background: linear-gradient(140deg, #8672c978, #40376280); box-shadow: inset 0 1px 0 #e7d9ff59, 0 0 75px #a58bf328, 0 20px 40px #0002; }
.orbit-core svg { transform: rotate(12deg); }
.orbit-node { position: absolute; display: grid; place-items: center; width: 43px; height: 43px; border: 1px solid #c1b5e43d; border-radius: 13px; color: #cdc5e9; background: #242439; box-shadow: 0 7px 24px #0002; }
.node-one { left: 6%; top: 52%; transform: rotate(-8deg); }.node-two { right: 8%; top: 15%; transform: rotate(8deg); }.node-three { right: 24%; bottom: 12%; transform: rotate(-5deg); }
.orbit-dot { position: absolute; width: 6px; height: 6px; border-radius: 50%; background: #b2a2e6; box-shadow: 0 0 15px #bfa2ff80; }.dot-one { top: 15%; left: 30%; }.dot-two { bottom: 19%; left: 21%; width: 4px; height: 4px; }
.art-caption { position: absolute; bottom: 0; left: 0; color: #aaa7c3; font-size: 10px; letter-spacing: 3px; }
.story-footer { display: flex; align-items: center; gap: 14px; margin-top: 48px; color: #aaa9c1; font-size: 10px; letter-spacing: .5px; }.footer-line { height: 1px; flex: 1; background: #ffffff1c; }
.entry-panel { display: flex; flex-direction: column; min-width: 0; padding: 42px clamp(32px, 4vw, 64px) 30px; background: var(--canvas); }
.panel-top, .panel-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--ink-soft); font-size: 11px; }
.workspace-label { display: inline-flex; align-items: center; gap: 8px; }.workspace-label > span { width: 6px; height: 6px; border-radius: 50%; background: var(--surface-soft); }.edition-label { color: var(--ink-soft); letter-spacing: 2px; font-size: 9px; }
.entry-form-card { width: min(390px, 100%); margin: auto; padding: 58px 0; }
.form-symbol { display: grid; place-items: center; width: 48px; height: 48px; color: var(--ink-soft); border: 1px solid var(--line-strong); border-radius: 14px; background: var(--surface-soft); box-shadow: 0 4px 10px #43316b05, inset 0 1px #fff; }
.form-heading { margin: 24px 0 30px; }.form-kicker { margin: 0 0 9px; color: var(--ink-soft); font-size: 11px; letter-spacing: 1px; }
h2 { width: fit-content; margin: 0; color: var(--ink); font-size: 34px; font-weight: 650; line-height: 1.3; letter-spacing: -1.5px; }.heading-dot { color: var(--muted); }
.form-description { margin: 13px 0 0; color: var(--ink-soft); font-size: 12px; line-height: 1.8; }
form, fieldset { display: grid; gap: 20px; }.entry-field { display: grid; gap: 9px; min-width: 0; }.entry-field label { color: var(--ink); font-size: 12px; font-weight: 550; }
.entry-field input { min-width: 0; min-height: 49px; padding: 12px 14px; border: 1px solid var(--line-strong); border-radius: 9px; background: var(--surface); color: var(--ink); font-size: 14px; line-height: 1.6; box-shadow: 0 2px 3px #17102503; transition: border-color .18s, box-shadow .18s; }
.entry-field input::placeholder { color: var(--muted); font-size: 13px; }.entry-field input:hover { border-color: var(--line-strong); }.entry-field input:focus { border-color: var(--line-strong); box-shadow: 0 0 0 3px #8063b717; outline: 0; }
.password-control { position: relative; }.password-control input { padding-right: 53px; }input::-ms-reveal { display: none; }
.password-toggle { position: absolute; right: 3px; top: 3px; display: grid; place-items: center; width: 44px; height: 44px; padding: 0; color: var(--ink-soft); border: 0; border-radius: 7px; background: transparent; }.password-toggle:hover { color: var(--ink-soft); background: var(--surface-soft); }
.password-help { margin: 0; font-size: 11px; line-height: 1.6; color: var(--ink-soft); }
.entry-submit { display: flex; justify-content: center; align-items: center; gap: 11px; width: 100%; min-height: 49px; margin-top: 4px; padding: 12px 16px; color: var(--on-action); font-size: 13px; font-weight: 600; border: 1px solid var(--line-strong); border-radius: 9px; background: var(--action); box-shadow: inset 0 1px #ffffff20, 0 4px 9px #53408520; transition: background .18s, box-shadow .18s; }.entry-submit:hover:not(:disabled) { background: var(--action); box-shadow: 0 5px 14px #53408530; }.entry-submit:disabled { opacity: .75; }
.entry-switch { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 21px; font-size: 12px; color: var(--ink-soft); }.entry-switch button { display: inline-flex; align-items: center; gap: 5px; min-height: 44px; padding: 0 4px; background: none; border: 0; border-radius: 4px; font-size: 12px; font-weight: 600; color: var(--ink-soft); }.entry-switch button:hover { text-decoration: underline; }
.session-note { display: flex; justify-content: center; align-items: center; gap: 7px; margin-top: 25px; padding-top: 24px; border-top: 1px solid var(--line-strong); color: var(--ink-soft); }.session-note svg { flex: none; }.session-note p { margin: 0; font-size: 10px; line-height: 1.7; }
.panel-footer { font-size: 10px; color: var(--ink-soft); }
.entry-error { display: flex; align-items: flex-start; gap: 9px; margin: 0; padding: 12px; color: var(--ink-soft); border: 1px solid var(--line-strong); background: var(--surface-soft); border-radius: 8px; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }.entry-error svg { flex: none; margin-top: 1px; }
.entry-layout button:focus-visible, .entry-error:focus-visible, h2:focus-visible { outline: 3px solid var(--line-strong); outline-offset: 4px; }
.submit-spinner { width: 15px; height: 15px; border: 2px solid var(--line-strong); border-top-color: var(--line-strong); border-radius: 50%; animation: submit-spin .8s linear infinite; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@keyframes ambient-drift { to { transform: translate(6%, -3%) rotate(8deg); opacity: .6; } }@keyframes submit-spin { to { transform: rotate(360deg); } }
@media (min-width: 1600px) { .entry-story { padding-left: max(76px, calc((100vw - 1440px) / 2)); }.story-body { margin-left: 0; }.entry-panel { padding-right: max(64px, calc((100vw - 1440px) / 2)); } }
@media (max-width: 1000px) and (min-width: 761px) { .entry-layout { grid-template-columns: 45% 55%; }.entry-story { padding: 32px; }.entry-panel { padding: 34px; }h1 { font-size: 37px; }.story-footer > span:last-child, .edition-label { display: none; }.knowledge-art { height: 245px; } }
@media (max-width: 760px) { .entry-layout { display: flex; flex-direction: column; }.entry-story { min-height: auto; padding: 23px 26px; }.entry-brand { font-size: 20px; }.entry-mark { width: 38px; height: 38px; border-radius: 11px; }.brand-caption { font-size: 9px; }.story-body, .story-footer { display: none; }.entry-panel { flex: 1; padding: 23px 26px 22px; }.panel-top { font-size: 10px; }.edition-label { display: none; }.entry-form-card { padding: 34px 0 32px; }.form-symbol { width: 41px; height: 41px; border-radius: 12px; }.form-heading { margin: 20px 0 27px; }h2 { font-size: 30px; }.form-description { font-size: 12px; }.entry-field input { font-size: 16px; }.session-note { margin-top: 20px; padding-top: 20px; }.panel-footer { margin-top: auto; font-size: 9px; } }
@media (max-width: 350px) { .entry-story { padding: 19px 20px; }.entry-panel { padding: 20px; }.entry-form-card { padding: 27px 0; }.form-description { max-width: 250px; }.panel-footer > span:last-child { display: none; }.session-note { gap: 5px; }.session-note p { font-size: 9px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
