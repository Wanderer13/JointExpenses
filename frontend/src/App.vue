<script setup lang="ts">
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div v-if="route.name === 'login'">
    <RouterView />
  </div>
  <div v-else class="shell">
    <header class="topbar">
      <div class="brand">Shared Expenses</div>
      <nav class="nav" v-if="auth.isAuthenticated">
        <RouterLink to="/">Groups</RouterLink>
        <RouterLink to="/balances">My balances</RouterLink>
        <RouterLink to="/notifications">Notifications</RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin">Admin</RouterLink>
        <span class="muted">{{ auth.user?.name }}</span>
        <button class="linkish" type="button" @click="logout">Log out</button>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
