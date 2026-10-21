<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api'
import { eventLabel, notificationTab } from '../eventLabels'
import type { NotificationItem } from '../types'

const items = ref<NotificationItem[]>([])

function groupId(n: NotificationItem): number | null {
  const raw = n.payload?.group_id
  return typeof raw === 'number' ? raw : null
}

function summary(n: NotificationItem): string {
  const parts: string[] = []
  if (typeof n.payload.settlement_id === 'number') {
    parts.push(`Payment #${n.payload.settlement_id}`)
  }
  if (typeof n.payload.expense_id === 'number') {
    parts.push(`Expense #${n.payload.expense_id}`)
  }
  if (typeof n.payload.amount_cents === 'number') {
    parts.push(`${(n.payload.amount_cents / 100).toFixed(2)}`)
  }
  return parts.join(' · ') || 'Open the group for details.'
}

function deepLink(n: NotificationItem): string | null {
  const gid = groupId(n)
  if (!gid) return null
  return `/groups/${gid}?tab=${notificationTab(n.notification_type)}`
}

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
          <strong>{{ eventLabel(n.notification_type) }}</strong>
          <span class="badge" v-if="!n.read_at">new</span>
        </div>
        <p class="muted" style="margin: 0.35rem 0 0">{{ summary(n) }}</p>
        <div class="muted" style="margin-top: 0.25rem">
          {{ new Date(n.created_at).toLocaleString() }}
        </div>
        <div class="row" style="margin-top: 0.6rem; gap: 0.5rem">
          <RouterLink v-if="deepLink(n)" :to="deepLink(n)!">Open</RouterLink>
          <button v-if="!n.read_at" class="secondary touch-btn" type="button" @click="markRead(n.id)">
            Mark read
          </button>
        </div>
      </div>
      <p v-if="!items.length" class="muted">No notifications.</p>
    </div>
  </section>
</template>
