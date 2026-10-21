<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api'
import type { NotificationItem } from '../types'

const items = ref<NotificationItem[]>([])

const LABELS: Record<string, string> = {
  settlement_pending: 'Settlement awaiting confirm',
  settlement_confirmed: 'Settlement confirmed',
  settlement_rejected: 'Settlement rejected',
  expense_created: 'Expense added',
  expense_updated: 'Expense updated',
  expense_deleted: 'Expense deleted',
  expense_completed: 'Expense completed',
  expense_reopened: 'Expense reopened',
  member_joined: 'Member joined',
  group_closed: 'Group closed',
  group_reopened: 'Group reopened',
  invite_sent: 'Invite sent',
}

function labelFor(n: NotificationItem): string {
  return LABELS[n.notification_type] || n.notification_type.replace(/_/g, ' ')
}

function groupId(n: NotificationItem): number | null {
  const raw = n.payload?.group_id
  return typeof raw === 'number' ? raw : null
}

function summary(n: NotificationItem): string {
  const parts: string[] = []
  if (typeof n.payload.settlement_id === 'number') {
    parts.push(`Settlement #${n.payload.settlement_id}`)
  }
  if (typeof n.payload.expense_id === 'number') {
    parts.push(`Expense #${n.payload.expense_id}`)
  }
  if (typeof n.payload.amount_cents === 'number') {
    parts.push(`${(n.payload.amount_cents / 100).toFixed(2)}`)
  }
  return parts.join(' · ') || 'Tap through to the group for details.'
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
          <strong>{{ labelFor(n) }}</strong>
          <span class="badge" v-if="!n.read_at">new</span>
        </div>
        <p class="muted" style="margin: 0.35rem 0 0">{{ summary(n) }}</p>
        <div class="muted" style="margin-top: 0.25rem">
          {{ new Date(n.created_at).toLocaleString() }}
        </div>
        <div class="row" style="margin-top: 0.6rem; gap: 0.5rem">
          <RouterLink
            v-if="groupId(n)"
            :to="`/groups/${groupId(n)}?tab=${n.notification_type.startsWith('settlement') ? 'settlements' : 'activity'}`"
          >
            Open group
          </RouterLink>
          <button v-if="!n.read_at" class="secondary" type="button" @click="markRead(n.id)">
            Mark read
          </button>
        </div>
      </div>
      <p v-if="!items.length" class="muted">No notifications.</p>
    </div>
  </section>
</template>
