<script setup lang="ts">
import { watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useOverviewStore } from './stores/overview'

const auth = useAuthStore()
const overview = useOverviewStore()
const route = useRoute()
const router = useRouter()

watch(
  () => auth.isAuthenticated,
  (ok) => {
    if (ok) void overview.refresh()
    else overview.clear()
  },
  { immediate: true },
)

async function logout() {
  await auth.logout()
  overview.clear()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="route.name === 'login' || (route.name === 'join' && !auth.isAuthenticated)">
    <RouterView />
  </div>
  <div v-else class="shell">
    <header class="topbar">
      <div class="brand">Shared Expenses</div>
      <nav class="nav" v-if="auth.isAuthenticated">
        <RouterLink to="/">
          Home
          <span
            v-if="overview.data?.pending_settlement_count"
            class="badge pending nav-badge"
            >{{ overview.data.pending_settlement_count }}</span
          >
        </RouterLink>
        <RouterLink to="/notifications">Notifications</RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin">Admin</RouterLink>
        <span class="muted">{{ auth.user?.name }}</span>
        <button class="linkish" type="button" @click="logout">Log out</button>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
