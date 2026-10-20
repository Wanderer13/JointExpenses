<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, money, wsUrl } from '../api'
import { CURRENCIES } from '../currencies'
import { useAuthStore } from '../stores/auth'
import type { Activity, Expense, Group, GroupBalances, Settlement } from '../types'

const props = defineProps<{ id: string }>()
const auth = useAuthStore()

const tab = ref<'expenses' | 'balances' | 'settlements' | 'activity' | 'invite'>('expenses')
const group = ref<Group | null>(null)
const expenses = ref<Expense[]>([])
const balances = ref<GroupBalances | null>(null)
const settlements = ref<Settlement[]>([])
const activity = ref<Activity[]>([])
const error = ref('')
const inviteEmail = ref('')
const joinToken = ref('')
const editCurrency = ref('USD')
const currencySaving = ref(false)
let socket: WebSocket | null = null

const amount = ref('')
const category = ref('general')
const expenseDate = ref(new Date().toISOString().slice(0, 10))
const comment = ref('')
const splitType = ref<'equal' | 'shares' | 'exact'>('equal')
const payerId = ref<number | null>(null)
const selected = ref<Record<number, boolean>>({})
const shares = ref<Record<number, number>>({})
const exact = ref<Record<number, string>>({})
const receiptFile = ref<File | null>(null)

const closed = computed(() => group.value?.status === 'closed')
const isOwner = computed(
  () => group.value?.members.some((m) => m.user_id === auth.user?.id && m.role === 'owner') ?? false,
)
const inviteLink = computed(() =>
  group.value ? `${window.location.origin}/join/${group.value.invite_token}` : '',
)

function centsFromInput(value: string): number {
  return Math.round(parseFloat(value || '0') * 100)
}

async function refreshAll() {
  const gid = Number(props.id)
  group.value = await api<Group>(`/api/groups/${gid}`)
  expenses.value = await api<Expense[]>(`/api/groups/${gid}/expenses`)
  balances.value = await api<GroupBalances>(`/api/groups/${gid}/balances`)
  settlements.value = await api<Settlement[]>(`/api/groups/${gid}/settlements`)
  activity.value = await api<Activity[]>(`/api/groups/${gid}/activity`)
  if (!payerId.value && auth.user) payerId.value = auth.user.id
  if (group.value) {
    editCurrency.value = group.value.currency
    for (const m of group.value.members) {
      if (selected.value[m.user_id] === undefined) selected.value[m.user_id] = true
      if (!shares.value[m.user_id]) shares.value[m.user_id] = 1
      if (!exact.value[m.user_id]) exact.value[m.user_id] = ''
    }
  }
}

function connectWs() {
  socket?.close()
  socket = new WebSocket(wsUrl(Number(props.id)))
  socket.onmessage = () => {
    void refreshAll()
  }
}

async function createExpense() {
  error.value = ''
  if (!group.value || !payerId.value) return
  const participants = group.value.members
    .filter((m) => selected.value[m.user_id])
    .map((m) => {
      if (splitType.value === 'shares') {
        return { user_id: m.user_id, shares: shares.value[m.user_id] || 1 }
      }
      if (splitType.value === 'exact') {
        return { user_id: m.user_id, amount_cents: centsFromInput(exact.value[m.user_id] || '0') }
      }
      return { user_id: m.user_id }
    })
  try {
    const created = await api<Expense>(`/api/groups/${group.value.id}/expenses`, {
      method: 'POST',
      body: JSON.stringify({
        payer_id: payerId.value,
        amount_cents: centsFromInput(amount.value),
        split_type: splitType.value,
        participants,
        category: category.value,
        expense_date: expenseDate.value,
        comment: comment.value || null,
      }),
    })
    if (receiptFile.value) {
      const fd = new FormData()
      fd.append('file', receiptFile.value)
      await api(`/api/expenses/${created.id}/receipt`, { method: 'POST', body: fd })
    }
    amount.value = ''
    comment.value = ''
    receiptFile.value = null
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function deleteExpense(expenseId: number) {
  await api(`/api/expenses/${expenseId}`, { method: 'DELETE' })
  await refreshAll()
}

async function settle(fromId: number, toId: number, amountCents: number) {
  if (!group.value) return
  await api(`/api/groups/${group.value.id}/settlements`, {
    method: 'POST',
    body: JSON.stringify({
      from_user_id: fromId,
      to_user_id: toId,
      amount_cents: amountCents,
    }),
  })
  await refreshAll()
}

async function settlementAction(id: number, action: 'confirm' | 'reject') {
  await api(`/api/settlements/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  await refreshAll()
}

async function invite() {
  if (!group.value) return
  await api(`/api/groups/${group.value.id}/invite-email`, {
    method: 'POST',
    body: JSON.stringify({ email: inviteEmail.value }),
  })
  inviteEmail.value = ''
  await refreshAll()
}

async function joinWithToken() {
  const g = await api<Group>(`/api/groups/join/${joinToken.value}`, { method: 'POST' })
  joinToken.value = ''
  if (g.id === Number(props.id)) await refreshAll()
}

async function closeOrReopen() {
  if (!group.value) return
  const path = group.value.status === 'open' ? 'close' : 'reopen'
  await api(`/api/groups/${group.value.id}/${path}`, { method: 'POST' })
  await refreshAll()
}

async function saveCurrency() {
  if (!group.value || !isOwner.value) return
  if (editCurrency.value === group.value.currency) return
  error.value = ''
  currencySaving.value = true
  try {
    group.value = await api<Group>(`/api/groups/${group.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ currency: editCurrency.value }),
    })
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
    editCurrency.value = group.value.currency
  } finally {
    currencySaving.value = false
  }
}

watch(
  () => props.id,
  async () => {
    await refreshAll()
    connectWs()
  },
)

onMounted(async () => {
  await refreshAll()
  connectWs()
})

onUnmounted(() => socket?.close())
</script>

<template>
  <div v-if="group" class="stack">
    <section class="panel">
      <div class="row" style="justify-content: space-between">
        <div>
          <h1>{{ group.name }}</h1>
          <p class="muted">
            {{ group.currency }} · {{ group.members.length }} members · reminders after
            {{ group.reminder_days }} days
          </p>
        </div>
        <div class="row">
          <span class="badge" :class="{ closed: closed }">{{ group.status }}</span>
          <button v-if="isOwner" class="secondary" type="button" @click="closeOrReopen">
            {{ closed ? 'Reopen group' : 'Close group' }}
          </button>
        </div>
      </div>
      <form
        v-if="isOwner"
        class="row"
        style="margin-top: 0.75rem; align-items: flex-end; gap: 0.75rem; flex-wrap: wrap"
        @submit.prevent="saveCurrency"
      >
        <label style="margin: 0">
          Group currency
          <select v-model="editCurrency">
            <option v-for="c in CURRENCIES" :key="c.code" :value="c.code">
              {{ c.code }} — {{ c.label }}
            </option>
          </select>
        </label>
        <button type="submit" :disabled="currencySaving || editCurrency === group.currency">
          {{ currencySaving ? 'Saving…' : 'Update currency' }}
        </button>
        <span class="muted" style="font-size: 0.85rem">
          Changes the display currency only — amounts are not converted.
        </span>
      </form>
      <div class="tabs" style="margin-top: 1rem">
        <button type="button" :class="{ active: tab === 'expenses' }" @click="tab = 'expenses'">Expenses</button>
        <button type="button" :class="{ active: tab === 'balances' }" @click="tab = 'balances'">Balances</button>
        <button type="button" :class="{ active: tab === 'settlements' }" @click="tab = 'settlements'">
          Settlements
        </button>
        <button type="button" :class="{ active: tab === 'activity' }" @click="tab = 'activity'">Activity</button>
        <button type="button" :class="{ active: tab === 'invite' }" @click="tab = 'invite'">Invite</button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="tab === 'expenses'" class="grid-2">
      <div class="panel stack">
        <h2>Expenses</h2>
        <div class="list">
          <div v-for="e in expenses" :key="e.id" class="item">
            <div class="row" style="justify-content: space-between">
              <strong>{{ e.category }} · {{ money(e.amount_cents, group.currency) }}</strong>
              <span class="muted">{{ e.expense_date }}</span>
            </div>
            <div class="muted">
              Paid by {{ e.payer_name }} · split {{ e.split_type }}
              <span v-if="e.comment"> · {{ e.comment }}</span>
            </div>
            <div class="muted">
              {{ e.splits.map((s) => `${s.name}: ${money(s.amount_cents, group.currency)}`).join(' · ') }}
            </div>
            <a v-if="e.receipt_path" :href="`/uploads/${e.receipt_path}`" target="_blank">Receipt</a>
            <button
              v-if="!closed"
              class="danger"
              style="margin-top: 0.5rem"
              type="button"
              @click="deleteExpense(e.id)"
            >
              Delete
            </button>
          </div>
          <p v-if="!expenses.length" class="muted">No expenses yet.</p>
        </div>
      </div>

      <form class="panel stack" @submit.prevent="createExpense">
        <h2>Add expense</h2>
        <p v-if="closed" class="muted">Group is closed — new expenses are blocked.</p>
        <fieldset :disabled="closed" class="stack" style="border: 0; padding: 0; margin: 0">
          <label>Amount <input v-model="amount" type="number" step="0.01" min="0.01" required /></label>
          <label>
            Payer
            <select v-model.number="payerId">
              <option v-for="m in group.members" :key="m.user_id" :value="m.user_id">{{ m.name }}</option>
            </select>
          </label>
          <label>
            Split type
            <select v-model="splitType">
              <option value="equal">Equal</option>
              <option value="shares">shares</option>
              <option value="exact">exact amounts</option>
            </select>
          </label>
          <div class="stack">
            <strong>Participants</strong>
            <label v-for="m in group.members" :key="m.user_id" class="row">
              <input v-model="selected[m.user_id]" type="checkbox" />
              <span style="min-width: 5rem">{{ m.name }}</span>
              <input
                v-if="splitType === 'shares'"
                v-model.number="shares[m.user_id]"
                type="number"
                min="1"
                style="width: 5rem"
              />
              <input
                v-if="splitType === 'exact'"
                v-model="exact[m.user_id]"
                type="number"
                step="0.01"
                min="0"
                style="width: 7rem"
                placeholder="0.00"
              />
            </label>
          </div>
          <label>Category <input v-model="category" /></label>
          <label>Date <input v-model="expenseDate" type="date" required /></label>
          <label>Comment <input v-model="comment" /></label>
          <label>Receipt <input type="file" @change="receiptFile = ($event.target as HTMLInputElement).files?.[0] || null" /></label>
          <button type="submit">Save expense</button>
        </fieldset>
      </form>
    </section>

    <section v-else-if="tab === 'balances'" class="grid-2">
      <div class="panel stack">
        <h2>Net balances</h2>
        <p class="muted">Sum check: {{ balances?.sum_check ?? 0 }} (must be 0)</p>
        <div class="list">
          <div v-for="n in balances?.nets || []" :key="n.user_id" class="item row" style="justify-content: space-between">
            <span>{{ n.name }}</span>
            <span :class="n.balance_cents >= 0 ? 'pos' : 'neg'">{{ money(n.balance_cents, group.currency) }}</span>
          </div>
        </div>
      </div>
      <div class="panel stack">
        <h2>Suggested transfers</h2>
        <p class="muted">Minimal set so everyone is settled.</p>
        <div class="list">
          <div v-for="(t, idx) in balances?.suggested_transfers || []" :key="idx" class="item">
            <div>
              <strong>{{ t.from_name }}</strong> → <strong>{{ t.to_name }}</strong>:
              {{ money(t.amount_cents, group.currency) }}
            </div>
            <button
              v-if="!closed && auth.user && (auth.user.id === t.from_user_id || auth.user.id === t.to_user_id)"
              class="secondary"
              style="margin-top: 0.5rem"
              type="button"
              @click="settle(t.from_user_id, t.to_user_id, t.amount_cents)"
            >
              Propose settlement
            </button>
          </div>
          <p v-if="!(balances?.suggested_transfers || []).length" class="muted">All settled.</p>
        </div>
      </div>
    </section>

    <section v-else-if="tab === 'settlements'" class="panel stack">
      <h2>Settlements</h2>
      <p class="muted">Count only after the recipient confirms.</p>
      <div class="list">
        <div v-for="s in settlements" :key="s.id" class="item">
          <div class="row" style="justify-content: space-between">
            <span
              >{{ s.from_name }} → {{ s.to_name }}: {{ money(s.amount_cents, group.currency) }}</span
            >
            <span class="badge" :class="{ pending: s.status === 'pending' }">{{ s.status }}</span>
          </div>
          <div v-if="s.status === 'pending' && auth.user?.id === s.to_user_id" class="row" style="margin-top: 0.5rem">
            <button type="button" @click="settlementAction(s.id, 'confirm')">Confirm</button>
            <button class="secondary" type="button" @click="settlementAction(s.id, 'reject')">Reject</button>
          </div>
        </div>
        <p v-if="!settlements.length" class="muted">No settlements yet.</p>
      </div>
    </section>

    <section v-else-if="tab === 'activity'" class="panel stack">
      <h2>Activity</h2>
      <div class="list">
        <div v-for="a in activity" :key="a.id" class="item">
          <strong>{{ a.event_type }}</strong>
          <div class="muted">{{ a.actor_name || 'system' }} · {{ new Date(a.created_at).toLocaleString() }}</div>
        </div>
      </div>
    </section>

    <section v-else class="panel stack">
      <h2>Invite members</h2>
      <p class="muted">
        Share link:
        <code>{{ inviteLink }}</code>
      </p>
      <form class="stack" @submit.prevent="invite">
        <label>Invite by email <input v-model="inviteEmail" type="email" required /></label>
        <button type="submit">Send invite (stub mailbox)</button>
      </form>
      <form class="stack" @submit.prevent="joinWithToken">
        <label>Or join with token <input v-model="joinToken" required /></label>
        <button class="secondary" type="submit">Join</button>
      </form>
      <div>
        <h3>Members</h3>
        <div class="list">
          <div v-for="m in group.members" :key="m.user_id" class="item">
            {{ m.name }} · {{ m.email }} · {{ m.role }}
          </div>
        </div>
      </div>
    </section>
  </div>
  <p v-else class="muted">Loading…</p>
</template>
