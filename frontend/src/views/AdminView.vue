<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import type { AdminActionLog, AdminUser, AppRole, ClearLinkedUsersResult } from '../types'

const users = ref<AdminUser[]>([])
const logs = ref<AdminActionLog[]>([])
const error = ref('')
const message = ref('')
const loading = ref(false)
const clearing = ref(false)

async function loadUsers() {
  users.value = await api<AdminUser[]>('/api/admin/users')
}

async function loadLogs() {
  logs.value = await api<AdminActionLog[]>('/api/admin/action-logs?limit=50')
}

async function load() {
  error.value = ''
  loading.value = true
  try {
    await Promise.all([loadUsers(), loadLogs()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load admin data'
  } finally {
    loading.value = false
  }
}

async function setRole(user: AdminUser, role: AppRole) {
  error.value = ''
  message.value = ''
  try {
    await api(`/api/admin/users/${user.id}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    })
    message.value = `Updated ${user.email} to ${role}`
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to update role'
  }
}

async function clearLinked() {
  if (
    !window.confirm(
      'Delete all registered users except seed defaults (alice/bob/cara@example.com)? This cannot be undone.',
    )
  ) {
    return
  }
  error.value = ''
  message.value = ''
  clearing.value = true
  try {
    const res = await api<ClearLinkedUsersResult>('/api/admin/users/clear-linked', {
      method: 'POST',
    })
    message.value = `Cleared ${res.deleted_count} user(s)`
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to clear users'
  } finally {
    clearing.value = false
  }
}

function authMethod(u: AdminUser): string {
  const parts: string[] = []
  if (u.has_password) parts.push('password')
  if (u.google_linked) parts.push('Google')
  return parts.join(' + ') || '—'
}

function payloadSummary(log: AdminActionLog): string {
  try {
    return JSON.stringify(log.payload)
  } catch {
    return ''
  }
}

onMounted(load)
</script>

<template>
  <div class="stack">
    <section class="panel stack">
      <h1>Admin</h1>
      <p class="muted">Manage roles, clear test users, and review the action log.</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message" class="pos">{{ message }}</p>
      <div class="row">
        <button type="button" class="secondary" :disabled="loading" @click="load">Refresh</button>
        <button type="button" class="danger" :disabled="clearing || loading" @click="clearLinked">
          Clear linked users
        </button>
      </div>
    </section>

    <section class="panel stack">
      <h2>Users</h2>
      <div class="list">
        <div v-for="u in users" :key="u.id" class="item">
          <div class="row" style="justify-content: space-between">
            <div>
              <strong>{{ u.name }}</strong>
              <div class="muted">{{ u.email }} · {{ authMethod(u) }}</div>
            </div>
            <span class="badge">{{ u.role }}</span>
          </div>
          <div class="row">
            <button
              v-if="u.role !== 'admin'"
              type="button"
              class="secondary"
              @click="setRole(u, 'admin')"
            >
              Promote to admin
            </button>
            <button
              v-if="u.role === 'admin'"
              type="button"
              class="secondary"
              @click="setRole(u, 'user')"
            >
              Demote to user
            </button>
          </div>
        </div>
        <p v-if="!users.length && !loading" class="muted">No users.</p>
      </div>
    </section>

    <section class="panel stack">
      <h2>Action log</h2>
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Target</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td>{{ new Date(log.created_at).toLocaleString() }}</td>
              <td>{{ log.actor_email || '—' }}</td>
              <td>{{ log.action }}</td>
              <td>
                <span v-if="log.target_type">{{ log.target_type }} #{{ log.target_id }}</span>
                <span v-else>—</span>
              </td>
              <td class="muted mono">{{ payloadSummary(log) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!logs.length && !loading" class="muted">No actions logged yet.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.admin-table th,
.admin-table td {
  text-align: left;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.admin-table th {
  color: var(--muted);
  font-weight: 600;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
  word-break: break-word;
  max-width: 280px;
}
</style>
