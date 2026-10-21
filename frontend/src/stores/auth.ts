import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setToken } from '../api'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function bootstrap() {
    try {
      const refreshed = await api<{ access_token: string; user: User }>('/api/auth/refresh', {
        method: 'POST',
      })
      setToken(refreshed.access_token)
      user.value = refreshed.user
    } catch {
      try {
        user.value = await api<User>('/api/auth/me')
      } catch {
        setToken(null)
        user.value = null
      }
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

  async function loginWithGoogle(credential: string, password?: string) {
    const res = await api<{ access_token: string; user: User }>('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential, password: password || null }),
    })
    setToken(res.access_token)
    user.value = res.user
  }

  async function logout() {
    try {
      await api('/api/auth/logout', { method: 'POST' })
    } catch {
      /* ignore */
    }
    setToken(null)
    user.value = null
  }

  return { user, ready, isAuthenticated, isAdmin, bootstrap, login, register, loginWithGoogle, logout }
})
