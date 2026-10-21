<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import type { Group } from '../types'

const props = defineProps<{ token: string }>()
const router = useRouter()
const auth = useAuthStore()

const preview = ref<{ name: string; status: string; currency: string } | null>(null)
const error = ref('')
const joining = ref(false)

async function loadPreview() {
  try {
    preview.value = await api(`/api/groups/join/${props.token}/preview`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Invite not found'
  }
}

async function joinNow() {
  error.value = ''
  joining.value = true
  try {
    if (!auth.isAuthenticated) {
      await router.push({ name: 'login', query: { redirect: `/join/${props.token}` } })
      return
    }
    const group = await api<Group>(`/api/groups/join/${props.token}`, { method: 'POST' })
    await router.replace(`/groups/${group.id}?tab=expenses`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to join'
  } finally {
    joining.value = false
  }
}

onMounted(async () => {
  await loadPreview()
  if (auth.isAuthenticated && preview.value && preview.value.status !== 'closed') {
    // Auto-join when already logged in
    await joinNow()
  }
})
</script>

<template>
  <div class="auth-wrap">
    <section class="panel auth-card stack">
      <div class="brand">Shared Expenses</div>
      <template v-if="preview && !error">
        <h1>Join {{ preview.name }}</h1>
        <p class="muted">
          {{ preview.currency }} · Create an account or log in to join this group.
        </p>
        <p v-if="preview.status === 'closed'" class="error">This group is closed.</p>
        <template v-else>
          <button
            v-if="auth.isAuthenticated"
            type="button"
            :disabled="joining"
            @click="joinNow"
          >
            {{ joining ? 'Joining…' : 'Join group' }}
          </button>
          <div v-else class="stack">
            <RouterLink class="btn" :to="{ name: 'login', query: { redirect: `/join/${token}` } }">
              Log in to join
            </RouterLink>
            <p class="muted">
              New here?
              <RouterLink :to="{ name: 'login', query: { redirect: `/join/${token}` } }"
                >Register on the login page</RouterLink
              >
              then open this link again.
            </p>
          </div>
        </template>
      </template>
      <template v-else>
        <h1>Join group</h1>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-else class="muted">Loading invite…</p>
      </template>
    </section>
  </div>
</template>
