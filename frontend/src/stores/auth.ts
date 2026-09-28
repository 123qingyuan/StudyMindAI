import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, ApiError } from '../api/client'

export interface User { id: string; email: string; display_name: string; avatar_url?: string; timezone?: string }

export const useAuthStore = defineStore('auth', () => {
  const token = ref(sessionStorage.getItem('studymind_token') || '')
  const user = ref<User | null>(readUser())
  const busy = ref(false)
  const initials = computed(() => (user.value?.display_name || '智').slice(0, 1).toUpperCase())
  function readUser(): User | null {
    try { return JSON.parse(sessionStorage.getItem('studymind_user') || 'null') } catch { return null }
  }
  function persist() {
    if (token.value) sessionStorage.setItem('studymind_token', token.value)
    else sessionStorage.removeItem('studymind_token')
    if (user.value) sessionStorage.setItem('studymind_user', JSON.stringify(user.value))
    else sessionStorage.removeItem('studymind_user')
  }
  async function login(payload: { email: string; password: string }) {
    busy.value = true
    try { const result = await api.post<{ access_token: string; user: User }>('/auth/login', payload); token.value = result.access_token; user.value = result.user; persist(); return result }
    finally { busy.value = false }
  }
  async function register(payload: { email: string; password: string; display_name: string }) {
    busy.value = true
    try { const result = await api.post<{ access_token: string; user: User }>('/auth/register', payload); token.value = result.access_token; user.value = result.user; persist(); return result }
    finally { busy.value = false }
  }
  async function hydrate() {
    if (!token.value) return
    try { user.value = await api.get<User>('/auth/me'); persist() } catch (e) { if (e instanceof ApiError && e.status === 401) clear() }
  }
  async function logout() { try { if (token.value) await api.post('/auth/logout') } finally { clear() } }
  function clear() { token.value = ''; user.value = null; persist() }
  return { token, user, busy, initials, login, register, hydrate, logout, clear }
})
