<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, money } from '../api'
import type { MyBalance } from '../types'

const items = ref<MyBalance[]>([])

function positionLabel(balanceCents: number): string {
  if (balanceCents === 0) return 'Settled — no final debt'
  if (balanceCents < 0) return 'You owe (final debt)'
  return 'You are owed (final credit)'
}

onMounted(async () => {
  items.value = await api<MyBalance[]>('/api/balances/me')
})
</script>

<template>
  <section class="panel stack">
    <h1>My balances</h1>
    <p class="muted">
      Your final debt or credit in each group after expenses and confirmed settlements. Open a group
      to propose or confirm repayments.
    </p>
    <div class="list">
      <RouterLink
        v-for="b in items"
        :key="b.group_id"
        class="item"
        :to="`/groups/${b.group_id}?tab=balances`"
      >
        <div class="row" style="justify-content: space-between">
          <div>
            <strong>{{ b.group_name }}</strong>
            <div class="muted">{{ positionLabel(b.balance_cents) }}</div>
          </div>
          <span :class="b.balance_cents >= 0 ? 'pos' : 'neg'">{{
            money(Math.abs(b.balance_cents), b.currency)
          }}</span>
        </div>
      </RouterLink>
      <p v-if="!items.length" class="muted">No balances yet.</p>
    </div>
  </section>
</template>
