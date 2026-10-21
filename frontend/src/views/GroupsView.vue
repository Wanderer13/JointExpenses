<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, money } from '../api'
import PersonLink from '../components/PersonLink.vue'
import { DEFAULT_REMINDER_DAYS, GROUP_STATUS, MAX_REMINDER_DAYS, MIN_REMINDER_DAYS } from '../constants'
import { CURRENCIES, suggestCurrency } from '../currencies'
import { useOverviewStore } from '../stores/overview'
import type { Group, PendingSettlement } from '../types'

const overview = useOverviewStore()
const groups = ref<Group[]>([])
const name = ref('')
const currency = ref(suggestCurrency())
const reminderDays = ref(DEFAULT_REMINDER_DAYS)
const error = ref('')
const loading = ref(false)
const actionError = ref('')

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
    await api('/api/groups', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value,
        currency: currency.value,
        reminder_days: reminderDays.value,
      }),
    })
    name.value = ''
    currency.value = suggestCurrency()
    await load()
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
    <section class="panel stack">
      <h1>Home</h1>
      <p class="muted">
        Pending settlements, your balances, and open expenses across groups. Completing an expense
        locks edits — clearing debt still goes through Balances → Settlements.
      </p>
    </section>

    <div class="grid-2">
      <section class="panel stack">
        <h2>
          Pending settlements
          <span v-if="overview.data?.pending_settlement_count" class="badge pending">{{
            overview.data.pending_settlement_count
          }}</span>
        </h2>
        <p v-if="actionError" class="error">{{ actionError }}</p>
        <div class="list">
          <div
            v-for="s in overview.data?.pending_settlements || []"
            :key="s.id"
            class="item"
          >
            <div class="row" style="justify-content: space-between; align-items: flex-start">
              <div>
                <div>
                  {{ money(s.amount_cents, s.currency) }} with
                  <PersonLink
                    :user-id="s.counterpart_user_id"
                    :name="s.counterpart_name"
                    :email="s.counterpart_email"
                    show-email
                  />
                </div>
                <div class="muted" style="margin-top: 0.35rem">
                  {{ s.group_name }} · debtor
                  <PersonLink :user-id="s.from_user_id" :name="s.from_name" />
                  → loaner
                  <PersonLink :user-id="s.to_user_id" :name="s.to_name" />
                  · awaiting confirm
                </div>
              </div>
              <RouterLink class="muted" :to="`/groups/${s.group_id}?tab=settlements`"
                >Open</RouterLink
              >
            </div>
            <div class="row" style="margin-top: 0.5rem; gap: 0.5rem">
              <button type="button" @click="settlementAction(s, 'confirm')">Confirm</button>
              <button class="secondary" type="button" @click="settlementAction(s, 'reject')">
                Reject
              </button>
            </div>
          </div>
          <p v-if="!(overview.data?.pending_settlements || []).length" class="muted">
            No pending settlements.
          </p>
        </div>
      </section>

      <section class="panel stack">
        <h2>Your balances</h2>
        <div v-if="(overview.data?.balances_by_currency || []).length" class="list">
          <div
            v-for="c in overview.data?.balances_by_currency || []"
            :key="c.currency"
            class="item"
          >
            <strong>{{ c.currency }}</strong>
            <div class="muted">
              You owe
              <span class="neg">{{ money(c.you_owe_cents, c.currency) }}</span>
              · Owed to you
              <span class="pos">{{ money(c.owed_to_you_cents, c.currency) }}</span>
            </div>
          </div>
        </div>
        <p v-else class="muted">No balances yet.</p>
        <div class="list" style="margin-top: 0.75rem">
          <RouterLink
            v-for="b in overview.data?.group_balances || []"
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
        </div>
      </section>
    </div>

    <section class="panel stack">
      <h2>Open expenses</h2>
      <p class="muted">Expenses still marked open that you are involved in.</p>
      <div class="list">
        <div v-for="e in overview.data?.open_expenses || []" :key="e.id" class="item">
          <div class="row" style="justify-content: space-between">
            <div>
              <strong>{{ e.category }} · {{ money(e.amount_cents, e.currency) }}</strong>
              <div class="muted">
                {{ e.group_name }} · {{ e.expense_date }} · paid by
                <PersonLink :user-id="e.payer_id" :name="e.payer_name" :email="e.payer_email" />
              </div>
            </div>
            <RouterLink :to="`/groups/${e.group_id}?tab=expenses`">Open</RouterLink>
          </div>
        </div>
        <p v-if="!(overview.data?.open_expenses || []).length" class="muted">No open expenses.</p>
      </div>
    </section>

    <div class="grid-2">
      <section class="panel stack">
        <h2>Your groups</h2>
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
              <span class="badge" :class="{ closed: g.status === GROUP_STATUS.CLOSED }">{{
                g.status
              }}</span>
            </div>
            <div class="muted">
              {{ g.currency }} · {{ g.members.length }} members · reminders {{ g.reminder_days }}d
            </div>
          </RouterLink>
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
