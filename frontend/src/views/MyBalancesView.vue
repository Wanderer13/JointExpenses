<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, money } from '../api'
import type { MyBalance } from '../types'

const items = ref<MyBalance[]>([])

onMounted(async () => {
  items.value = await api<MyBalance[]>('/api/balances/me')
})
</script>

<template>
  <section class="panel stack">
    <h1>My balances</h1>
    <p class="muted">Across all groups. Positive means others owe you.</p>
    <div class="list">
      <RouterLink v-for="b in items" :key="b.group_id" class="item" :to="`/groups/${b.group_id}`">
        <div class="row" style="justify-content: space-between">
          <strong>{{ b.group_name }}</strong>
          <span :class="b.balance_cents >= 0 ? 'pos' : 'neg'">{{ money(b.balance_cents, b.currency) }}</span>
        </div>
      </RouterLink>
      <p v-if="!items.length" class="muted">No balances yet.</p>
    </div>
  </section>
</template>
