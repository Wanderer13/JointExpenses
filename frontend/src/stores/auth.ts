import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setToken, getToken } from '../api'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)

  const isAuthenticated = computed(() => !!user.value)

  async function bootstrap() {
    if (!getToken()) {
      ready.value = true
      return
    }
    try {
      user.value = await api<User>('/api/auth/me')
    } catch {
      setToken(null)
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function login(email: string, password: string) {
    const res = await api<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(res.access_token)
    user.value = res.user
  }

  async function register(name: string, email: string, password: string) {
    const res = await api<{ access_token: string; user: User }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    })
    setToken(res.access_token)
    user.value = res.user
  }

  async function loginWithGoogle(credential: string) {
    const res = await api<{ access_token: string; user: User }>('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    })
    setToken(res.access_token)
    user.value = res.user
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return { user, ready, isAuthenticated, bootstrap, login, register, loginWithGoogle, logout }
})
