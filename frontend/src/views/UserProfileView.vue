<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api'
import type { UserProfile } from '../types'

const props = defineProps<{ id: string }>()

const profile = ref<UserProfile | null>(null)
const error = ref('')

async function load() {
  error.value = ''
  profile.value = null
  try {
    profile.value = await api<UserProfile>(`/api/users/${props.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'User not found'
  }
}

onMounted(load)
watch(() => props.id, load)
</script>

<template>
  <section class="panel stack">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else-if="profile">
      <h1>{{ profile.name }}</h1>
      <p>
        <a :href="`mailto:${profile.email}`">{{ profile.email }}</a>
      </p>
      <div>
        <h2>Shared groups</h2>
        <div class="list">
          <RouterLink
            v-for="g in profile.shared_groups"
            :key="g.id"
            class="item"
            :to="`/groups/${g.id}`"
          >
            <div class="row" style="justify-content: space-between">
              <strong>{{ g.name }}</strong>
              <span class="badge" :class="{ closed: g.status === 'closed' }">{{ g.status }}</span>
            </div>
            <div class="muted">{{ g.currency }}</div>
          </RouterLink>
          <p v-if="!profile.shared_groups.length" class="muted">No shared groups.</p>
        </div>
      </div>
    </template>
    <p v-else class="muted">Loading…</p>
  </section>
</template>
