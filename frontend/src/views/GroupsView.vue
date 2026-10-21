<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, money } from '../api'
import PersonLink from '../components/PersonLink.vue'
import { DEFAULT_REMINDER_DAYS, GROUP_STATUS, MAX_REMINDER_DAYS, MIN_REMINDER_DAYS } from '../constants'
import { CURRENCIES, suggestCurrency } from '../currencies'
import { useOverviewStore } from '../stores/overview'
import type { Group, MyBalance, PendingSettlement } from '../types'

const overview = useOverviewStore()
const router = useRouter()
const groups = ref<Group[]>([])
const name = ref('')
const currency = ref(suggestCurrency())
const reminderDays = ref(DEFAULT_REMINDER_DAYS)
const error = ref('')
const loading = ref(false)
const actionError = ref('')

const balanceByGroup = computed(() => {
  const map = new Map<number, MyBalance>()
  for (const b of overview.data?.group_balances || []) map.set(b.group_id, b)
  return map
})

const pendingByGroup = computed(() => {
  const map = new Map<number, PendingSettlement[]>()
  for (const s of overview.data?.pending_settlements || []) {
    const list = map.get(s.group_id) || []
    list.push(s)
    map.set(s.group_id, list)
  }
  return map
})

const needsYouGroups = computed(() => {
  return groups.value.filter((g) => {
    const pending = (pendingByGroup.value.get(g.id) || []).length > 0
    const bal = balanceByGroup.value.get(g.id)
    const unpaid = bal != null && bal.balance_cents !== 0
    return pending || unpaid
  })
})

function positionLabel(balanceCents: number): string {
  if (balanceCents === 0) return 'Settled'
  if (balanceCents < 0) return 'You owe'
  return 'You are owed'
}

async function loadGroups() {
  groups.value = await api<Group[]>('/api/groups')
}

async function load() {
  await Promise.all([overview.refresh(), loadGroups()])
}

async function createGroup() {
  error.value = ''
  loading.value = true
  try {
    const created = await api<Group>('/api/groups', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value,
        currency: currency.value,
        reminder_days: reminderDays.value,
      }),
    })
    name.value = ''
    currency.value = suggestCurrency()
    await router.push(`/groups/${created.id}?tab=people`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  } finally {
    loading.value = false
  }
}

async function settlementAction(s: PendingSettlement, action: 'confirm' | 'reject') {
  actionError.value = ''
  try {
    await api(`/api/settlements/${s.id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    await overview.refresh()
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Failed'
  }
}

onMounted(load)
</script>

<template>
  <div class="stack" style="gap: 1.25rem">
    <section v-if="needsYouGroups.length" class="panel stack">
      <h1>Needs you</h1>
      <p class="muted">Payments to confirm or balances that are not settled.</p>
      <p v-if="actionError" class="error">{{ actionError }}</p>
      <div class="list">
        <div v-for="g in needsYouGroups" :key="'need-' + g.id" class="item">
          <div class="row" style="justify-content: space-between">
            <RouterLink :to="`/groups/${g.id}?tab=settle`">
              <strong>{{ g.name }}</strong>
            </RouterLink>
            <span
              v-if="balanceByGroup.get(g.id)"
              :class="balanceByGroup.get(g.id)!.balance_cents >= 0 ? 'pos' : 'neg'"
            >
              {{ positionLabel(balanceByGroup.get(g.id)!.balance_cents) }}
              {{ money(Math.abs(balanceByGroup.get(g.id)!.balance_cents), g.currency) }}
            </span>
          </div>
          <div
            v-for="s in pendingByGroup.get(g.id) || []"
            :key="s.id"
            class="item"
            style="margin-top: 0.65rem; background: rgba(255, 237, 213, 0.45)"
          >
            <div>
              Payment {{ money(s.amount_cents, s.currency) }} with
              <PersonLink
                :user-id="s.counterpart_user_id"
                :name="s.counterpart_name"
                :email="s.counterpart_email"
              />
            </div>
            <div class="row" style="margin-top: 0.5rem; gap: 0.5rem">
              <button type="button" class="touch-btn" @click="settlementAction(s, 'confirm')">
                Confirm
              </button>
              <button
                class="secondary touch-btn"
                type="button"
                @click="settlementAction(s, 'reject')"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="grid-2">
      <section class="panel stack">
        <h2>Your groups</h2>
        <p v-if="(overview.data?.balances_by_currency || []).length" class="muted">
          <span v-for="(c, i) in overview.data?.balances_by_currency || []" :key="c.currency">
            <template v-if="i"> · </template>
            {{ c.currency }}: owe
            <span class="neg">{{ money(c.you_owe_cents, c.currency) }}</span>
            / owed
            <span class="pos">{{ money(c.owed_to_you_cents, c.currency) }}</span>
          </span>
        </p>
        <div class="list">
          <div v-for="g in groups" :key="g.id" class="item">
            <div class="row" style="justify-content: space-between; align-items: flex-start">
              <div>
                <RouterLink :to="`/groups/${g.id}`">
                  <strong>{{ g.name }}</strong>
                </RouterLink>
                <div class="muted">
                  {{ g.currency }} · {{ g.members.length }} members
                  <span class="badge" :class="{ closed: g.status === GROUP_STATUS.CLOSED }">{{
                    g.status
                  }}</span>
                </div>
              </div>
              <div v-if="balanceByGroup.get(g.id)" style="text-align: right">
                <div class="muted">{{ positionLabel(balanceByGroup.get(g.id)!.balance_cents) }}</div>
                <span :class="balanceByGroup.get(g.id)!.balance_cents >= 0 ? 'pos' : 'neg'">{{
                  money(Math.abs(balanceByGroup.get(g.id)!.balance_cents), g.currency)
                }}</span>
              </div>
            </div>
          </div>
          <p v-if="!groups.length" class="muted">No groups yet — create one.</p>
        </div>
      </section>

      <section class="panel stack">
        <h2>New group</h2>
        <form class="stack" @submit.prevent="createGroup">
          <label>Name <input v-model="name" required /></label>
          <label>
            Currency
            <select v-model="currency" required>
              <option v-for="c in CURRENCIES" :key="c.code" :value="c.code">
                {{ c.code }} — {{ c.label }}
              </option>
            </select>
          </label>
          <label>
            Reminder after (days)
            <input
              v-model.number="reminderDays"
              type="number"
              :min="MIN_REMINDER_DAYS"
              :max="MAX_REMINDER_DAYS"
            />
          </label>
          <p v-if="error" class="error">{{ error }}</p>
          <button type="submit" :disabled="loading">Create</button>
        </form>
      </section>
    </div>
  </div>
</template>
