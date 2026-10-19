<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import type { NotificationItem } from '../types'

const items = ref<NotificationItem[]>([])

async function load() {
  items.value = await api<NotificationItem[]>('/api/notifications')
}

async function markRead(id: number) {
  await api(`/api/notifications/${id}/read`, { method: 'POST' })
  await load()
}

onMounted(load)
</script>

<template>
  <section class="panel stack">
    <h1>Notifications</h1>
    <div class="list">
      <div v-for="n in items" :key="n.id" class="item">
        <div class="row" style="justify-content: space-between">
          <strong>{{ n.notification_type }}</strong>
          <span class="badge" v-if="!n.read_at">new</span>
        </div>
        <pre class="muted" style="white-space: pre-wrap; margin: 0.4rem 0 0; font-family: inherit">{{
          JSON.stringify(n.payload, null, 2)
        }}</pre>
        <button v-if="!n.read_at" class="secondary" style="margin-top: 0.6rem" @click="markRead(n.id)">
          Mark read
        </button>
      </div>
      <p v-if="!items.length" class="muted">No notifications.</p>
    </div>
  </section>
</template>
