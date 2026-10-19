<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api'
import type { Group } from '../types'

const groups = ref<Group[]>([])
const name = ref('')
const currency = ref('USD')
const reminderDays = ref(7)
const error = ref('')
const loading = ref(false)

async function load() {
  groups.value = await api<Group[]>('/api/groups')
}

async function createGroup() {
  error.value = ''
  loading.value = true
  try {
    await api('/api/groups', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value,
        currency: currency.value,
        reminder_days: reminderDays.value,
      }),
    })
    name.value = ''
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="grid-2">
    <section class="panel stack">
      <h1>Your groups</h1>
      <p class="muted">Trips, flats, shared wallets — pick a group to manage expenses.</p>
      <div class="list">
        <RouterLink
          v-for="g in groups"
          :key="g.id"
          class="item"
          :to="`/groups/${g.id}`"
        >
          <div class="row" style="justify-content: space-between">
            <strong>{{ g.name }}</strong>
            <span class="badge" :class="{ closed: g.status === 'closed' }">{{ g.status }}</span>
          </div>
          <div class="muted">{{ g.currency }} · {{ g.members.length }} members · reminders {{ g.reminder_days }}d</div>
        </RouterLink>
        <p v-if="!groups.length" class="muted">No groups yet — create one.</p>
      </div>
    </section>

    <section class="panel stack">
      <h2>New group</h2>
      <form class="stack" @submit.prevent="createGroup">
        <label>Name <input v-model="name" required /></label>
        <label>Currency <input v-model="currency" maxlength="8" required /></label>
        <label>Reminder after (days) <input v-model.number="reminderDays" type="number" min="1" max="365" /></label>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">Create</button>
      </form>
    </section>
  </div>
</template>
