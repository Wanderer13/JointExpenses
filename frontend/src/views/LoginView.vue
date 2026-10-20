<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../api'
import {
  GOOGLE_LINK_PASSWORD_HINT,
  HTTP_CONFLICT,
  safeRedirectPath,
} from '../constants'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const name = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const googleClientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined)?.trim() || ''
const googleBtn = ref<HTMLElement | null>(null)
let googleScript: HTMLScriptElement | null = null

async function afterAuth() {
  await router.push(safeRedirectPath(route.query.redirect))
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (mode.value === 'login') await auth.login(email.value, password.value)
    else await auth.register(name.value, email.value, password.value)
    await afterAuth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  } finally {
    loading.value = false
  }
}

async function handleGoogleCredential(credential: string) {
  error.value = ''
  loading.value = true
  try {
    try {
      await auth.loginWithGoogle(credential)
    } catch (e) {
      const needsPassword =
        e instanceof ApiError &&
        e.status === HTTP_CONFLICT &&
        e.message.includes(GOOGLE_LINK_PASSWORD_HINT)
      if (needsPassword && password.value) {
        await auth.loginWithGoogle(credential, password.value)
      } else {
        throw e
      }
    }
    await afterAuth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Google sign-in failed'
  } finally {
    loading.value = false
  }
}

function renderGoogleButton() {
  if (!googleClientId || !googleBtn.value || !window.google?.accounts?.id) return
  window.google.accounts.id.initialize({
    client_id: googleClientId,
    callback: (response) => {
      if (response.credential) void handleGoogleCredential(response.credential)
    },
  })
  googleBtn.value.innerHTML = ''
  window.google.accounts.id.renderButton(googleBtn.value, {
    theme: 'outline',
    size: 'large',
    width: googleBtn.value.offsetWidth || 320,
    text: 'continue_with',
  })
}

function loadGoogleScript() {
  if (!googleClientId) return
  if (window.google?.accounts?.id) {
    renderGoogleButton()
    return
  }
  googleScript = document.createElement('script')
  googleScript.src = 'https://accounts.google.com/gsi/client'
  googleScript.async = true
  googleScript.onload = () => renderGoogleButton()
  document.head.appendChild(googleScript)
}

onMounted(() => {
  loadGoogleScript()
})

onUnmounted(() => {
  googleScript?.remove()
})
</script>

<template>
  <div class="auth-wrap">
    <form class="panel auth-card stack" @submit.prevent="submit">
      <div>
        <div class="brand">Shared Expenses</div>
        <p class="muted">Track who paid, who owes, settle with confirmation.</p>
      </div>

      <div class="tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">Login</button>
        <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">
          Register
        </button>
      </div>

      <template v-if="googleClientId">
        <div ref="googleBtn" class="google-btn" />
        <div class="auth-divider"><span>or continue with email</span></div>
      </template>

      <label v-if="mode === 'register'">
        Name
        <input v-model="name" required />
      </label>
      <label>
        Email
        <input v-model="email" type="email" required />
      </label>
      <label>
        Password
        <input v-model="password" type="password" minlength="6" required />
      </label>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '…' : mode === 'login' ? 'Log in' : 'Create account' }}</button>
      <p class="muted">Demo: alice@example.com / password123</p>
    </form>
  </div>
</template>
