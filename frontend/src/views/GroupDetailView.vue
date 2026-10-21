<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, money, receiptUrl, wsUrl } from '../api'
import {
  AMOUNT_INPUT_MIN,
  AMOUNT_INPUT_STEP,
  DEFAULT_CATEGORY,
  DEFAULT_CURRENCY,
  DEFAULT_SPLIT_TYPE,
  EXPENSE_STATUS,
  GROUP_STATUS,
  MEMBER_ROLE,
  SETTLEMENT_STATUS,
  SPLIT_TYPE,
  formatMajorInput,
  majorToCents,
} from '../constants'
import { CURRENCIES } from '../currencies'
import { useAuthStore } from '../stores/auth'
import {
  SPLIT_TYPE_LABELS,
  type Activity,
  type Expense,
  type Group,
  type GroupBalances,
  type Settlement,
  type SplitType,
} from '../types'

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
const inviteSentUrl = ref('')
const inviteSentMessage = ref('')
const joinToken = ref('')
const editCurrency = ref(DEFAULT_CURRENCY)
const currencySaving = ref(false)
const editingExpenseId = ref<number | null>(null)
let socket: WebSocket | null = null

const amount = ref('')
const category = ref(DEFAULT_CATEGORY)
const expenseDate = ref(new Date().toISOString().slice(0, 10))
const comment = ref('')
const splitType = ref<SplitType>(DEFAULT_SPLIT_TYPE)
const payerId = ref<number | null>(null)
const selected = ref<Record<number, boolean>>({})
const shares = ref<Record<number, number>>({})
const exact = ref<Record<number, string>>({})
const receiptFile = ref<File | null>(null)

const closed = computed(() => group.value?.status === GROUP_STATUS.CLOSED)
const isOwner = computed(
  () =>
    group.value?.members.some(
      (m) => m.user_id === auth.user?.id && m.role === MEMBER_ROLE.OWNER,
    ) ?? false,
)
const inviteLink = computed(() =>
  group.value ? `${window.location.origin}/join/${group.value.invite_token}` : '',
)
const formTitle = computed(() => (editingExpenseId.value ? 'Edit expense' : 'Add expense'))

function canMutateExpense(_e: Expense): boolean {
  return Boolean(auth.user && group.value)
}

function isExpenseOpen(e: Expense): boolean {
  return e.status !== EXPENSE_STATUS.COMPLETED
}

function netLabel(balanceCents: number, isYou: boolean): string {
  if (balanceCents === 0) return isYou ? 'You are settled' : 'Settled'
  if (balanceCents < 0) {
    return isYou ? 'You owe' : 'Owes'
  }
  return isYou ? 'You are owed' : 'Is owed'
}

function settlementStatusLabel(s: Settlement): string {
  const debtor = s.from_name || 'Debtor'
  const loaner = s.to_name || 'Loaner'
  if (s.status === SETTLEMENT_STATUS.PENDING) {
    return `Pending — debtor ${debtor} pays loaner ${loaner} (either party can confirm)`
  }
  if (s.status === SETTLEMENT_STATUS.CONFIRMED) {
    const when = s.confirmed_at ? ` · ${new Date(s.confirmed_at).toLocaleString()}` : ''
    return `Confirmed — ${debtor} paid ${loaner}${when}`
  }
  return `Rejected — ${debtor} → ${loaner}`
}

function transferRoleHint(t: { from_user_id: number; to_user_id: number }): string {
  if (!auth.user) return ''
  if (auth.user.id === t.from_user_id) return 'You owe this amount (debtor).'
  if (auth.user.id === t.to_user_id) return 'You are owed this amount (loaner).'
  return ''
}

function canActOnSettlement(s: Settlement): boolean {
  if (!auth.user || s.status !== SETTLEMENT_STATUS.PENDING) return false
  return auth.user.id === s.from_user_id || auth.user.id === s.to_user_id
}

function resetExpenseForm() {
  editingExpenseId.value = null
  amount.value = ''
  category.value = DEFAULT_CATEGORY
  expenseDate.value = new Date().toISOString().slice(0, 10)
  comment.value = ''
  splitType.value = DEFAULT_SPLIT_TYPE
  receiptFile.value = null
  if (auth.user) payerId.value = auth.user.id
  if (group.value) {
    for (const m of group.value.members) {
      selected.value[m.user_id] = true
      shares.value[m.user_id] = 1
      exact.value[m.user_id] = ''
    }
  }
}

function startEdit(e: Expense) {
  if (!isExpenseOpen(e)) return
  editingExpenseId.value = e.id
  amount.value = formatMajorInput(e.amount_cents)
  category.value = e.category
  expenseDate.value = e.expense_date
  comment.value = e.comment || ''
  splitType.value = e.split_type
  payerId.value = e.payer_id
  receiptFile.value = null
  if (group.value) {
    const splitIds = new Set(e.splits.map((s) => s.user_id))
    for (const m of group.value.members) {
      selected.value[m.user_id] = splitIds.has(m.user_id)
      const split = e.splits.find((s) => s.user_id === m.user_id)
      shares.value[m.user_id] = split?.shares || 1
      exact.value[m.user_id] = split ? formatMajorInput(split.amount_cents) : ''
    }
  }
  tab.value = 'expenses'
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
      // While editing, do not auto-include newly joined members in the split.
      if (selected.value[m.user_id] === undefined) {
        selected.value[m.user_id] = editingExpenseId.value == null
      }
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

function buildParticipants() {
  if (!group.value) return []
  return group.value.members
    .filter((m) => selected.value[m.user_id])
    .map((m) => {
      if (splitType.value === SPLIT_TYPE.SHARES) {
        return { user_id: m.user_id, shares: shares.value[m.user_id] || 1 }
      }
      if (splitType.value === SPLIT_TYPE.EXACT) {
        return { user_id: m.user_id, amount_cents: majorToCents(exact.value[m.user_id] || '0') }
      }
      return { user_id: m.user_id }
    })
}

async function saveExpense() {
  error.value = ''
  if (!group.value || !payerId.value) return
  const participants = buildParticipants()
  const body = {
    payer_id: payerId.value,
    amount_cents: majorToCents(amount.value),
    split_type: splitType.value,
    participants,
    category: category.value,
    expense_date: expenseDate.value,
    comment: comment.value || null,
  }
  try {
    let expenseId = editingExpenseId.value
    if (expenseId) {
      await api<Expense>(`/api/expenses/${expenseId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
    } else {
      const created = await api<Expense>(`/api/groups/${group.value.id}/expenses`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      expenseId = created.id
    }
    if (receiptFile.value && expenseId) {
      const fd = new FormData()
      fd.append('file', receiptFile.value)
      await api(`/api/expenses/${expenseId}/receipt`, { method: 'POST', body: fd })
    }
    resetExpenseForm()
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function deleteExpense(expenseId: number) {
  error.value = ''
  try {
    await api(`/api/expenses/${expenseId}`, { method: 'DELETE' })
    if (editingExpenseId.value === expenseId) resetExpenseForm()
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function setExpenseStatus(expenseId: number, status: 'open' | 'completed') {
  error.value = ''
  try {
    await api(`/api/expenses/${expenseId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    if (status === EXPENSE_STATUS.COMPLETED && editingExpenseId.value === expenseId) {
      resetExpenseForm()
    }
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function settle(fromId: number, toId: number, amountCents: number) {
  if (!group.value) return
  error.value = ''
  try {
    await api(`/api/groups/${group.value.id}/settlements`, {
      method: 'POST',
      body: JSON.stringify({
        from_user_id: fromId,
        to_user_id: toId,
        amount_cents: amountCents,
      }),
    })
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function settlementAction(id: number, action: 'confirm' | 'reject') {
  error.value = ''
  try {
    await api(`/api/settlements/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function invite() {
  if (!group.value) return
  error.value = ''
  inviteSentMessage.value = ''
  inviteSentUrl.value = ''
  try {
    const res = await api<{ message: string; join_url: string }>(
      `/api/groups/${group.value.id}/invite-email`,
      {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail.value }),
      },
    )
    inviteSentMessage.value = res.message
    inviteSentUrl.value = res.join_url
    inviteEmail.value = ''
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to send invite'
  }
}

async function joinWithToken() {
  const g = await api<Group>(`/api/groups/join/${joinToken.value}`, { method: 'POST' })
  joinToken.value = ''
  if (g.id === Number(props.id)) await refreshAll()
}

async function closeOrReopen() {
  if (!group.value) return
  const path = group.value.status === GROUP_STATUS.OPEN ? 'close' : 'reopen'
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
    resetExpenseForm()
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
        <p class="muted">
          Completing an expense marks it done. To clear what someone owes, use
          <strong>Balances</strong> (propose) then <strong>Settlements</strong> (confirm).
        </p>
        <div class="list">
          <div v-for="e in expenses" :key="e.id" class="item">
            <div class="row" style="justify-content: space-between">
              <strong>{{ e.category }} · {{ money(e.amount_cents, group.currency) }}</strong>
              <span class="row" style="gap: 0.4rem">
                <span
                  class="badge"
                  :class="{ completed: e.status === EXPENSE_STATUS.COMPLETED }"
                  >{{ e.status }}</span
                >
                <span class="muted">{{ e.expense_date }}</span>
              </span>
            </div>
            <div class="muted">
              Paid by {{ e.payer_name }} · {{ SPLIT_TYPE_LABELS[e.split_type] }}
              <span v-if="e.comment"> · {{ e.comment }}</span>
            </div>
            <div class="muted">
              {{
                e.splits
                  .map((s) => `${s.name}: ${money(s.amount_cents, group!.currency)}`)
                  .join(' · ')
              }}
            </div>
            <a v-if="e.receipt_path" :href="receiptUrl(e.id)" target="_blank" rel="noopener">Receipt</a>
            <div v-if="!closed && canMutateExpense(e)" class="row" style="margin-top: 0.5rem; gap: 0.5rem">
              <button
                v-if="isExpenseOpen(e)"
                class="secondary"
                type="button"
                @click="setExpenseStatus(e.id, EXPENSE_STATUS.COMPLETED)"
              >
                Complete
              </button>
              <button
                v-else
                class="secondary"
                type="button"
                @click="setExpenseStatus(e.id, EXPENSE_STATUS.OPEN)"
              >
                Reopen
              </button>
              <button
                v-if="isExpenseOpen(e)"
                class="secondary"
                type="button"
                @click="startEdit(e)"
              >
                Edit
              </button>
              <button
                v-if="isExpenseOpen(e)"
                class="danger"
                type="button"
                @click="deleteExpense(e.id)"
              >
                Delete
              </button>
            </div>
          </div>
          <p v-if="!expenses.length" class="muted">No expenses yet.</p>
        </div>
      </div>

      <form class="panel stack" @submit.prevent="saveExpense">
        <div class="row" style="justify-content: space-between">
          <h2>{{ formTitle }}</h2>
          <button
            v-if="editingExpenseId"
            class="secondary"
            type="button"
            @click="resetExpenseForm"
          >
            Cancel edit
          </button>
        </div>
        <p v-if="closed" class="muted">Group is closed — expense changes are blocked.</p>
        <fieldset :disabled="closed" class="stack" style="border: 0; padding: 0; margin: 0">
          <label>
            Amount
            <input v-model="amount" type="number" :step="AMOUNT_INPUT_STEP" :min="AMOUNT_INPUT_MIN" required />
          </label>
          <label>
            Payer
            <select v-model.number="payerId">
              <option v-for="m in group.members" :key="m.user_id" :value="m.user_id">{{ m.name }}</option>
            </select>
          </label>
          <label>
            Split type
            <select v-model="splitType">
              <option v-for="(label, value) in SPLIT_TYPE_LABELS" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </label>
          <div class="stack">
            <strong>Participants</strong>
            <label v-for="m in group.members" :key="m.user_id" class="row">
              <input v-model="selected[m.user_id]" type="checkbox" />
              <span style="min-width: 5rem">{{ m.name }}</span>
              <input
                v-if="splitType === SPLIT_TYPE.SHARES"
                v-model.number="shares[m.user_id]"
                type="number"
                min="1"
                style="width: 5rem"
                title="Shares"
                placeholder="shares"
              />
              <span v-if="splitType === SPLIT_TYPE.SHARES" class="muted">shares</span>
              <input
                v-if="splitType === SPLIT_TYPE.EXACT"
                v-model="exact[m.user_id]"
                type="number"
                :step="AMOUNT_INPUT_STEP"
                min="0"
                style="width: 7rem"
                title="Exact amount"
                placeholder="0.00"
              />
            </label>
          </div>
          <label>Category <input v-model="category" /></label>
          <label>Date <input v-model="expenseDate" type="date" required /></label>
          <label>Comment <input v-model="comment" /></label>
          <label>
            Receipt
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              @change="receiptFile = ($event.target as HTMLInputElement).files?.[0] || null"
            />
          </label>
          <button type="submit">{{ editingExpenseId ? 'Update expense' : 'Save expense' }}</button>
        </fieldset>
      </form>
    </section>

    <section v-else-if="tab === 'balances'" class="grid-2">
      <div class="panel stack">
        <h2>Net balances</h2>
        <p class="muted">
          Your final position in this group after expenses and confirmed settlements. Sum check:
          {{ balances?.sum_check ?? 0 }} (must be 0).
        </p>
        <div class="list">
          <div
            v-for="n in balances?.nets || []"
            :key="n.user_id"
            class="item row"
            style="justify-content: space-between"
          >
            <span>
              <strong v-if="n.user_id === auth.user?.id">You</strong>
              <template v-else>{{ n.name }}</template>
              · {{ netLabel(n.balance_cents, n.user_id === auth.user?.id) }}
            </span>
            <span :class="n.balance_cents >= 0 ? 'pos' : 'neg'">{{
              money(Math.abs(n.balance_cents), group.currency)
            }}</span>
          </div>
        </div>
      </div>
      <div class="panel stack">
        <h2>Suggested transfers</h2>
        <p class="muted">Who pays whom to settle. Propose, then confirm on Settlements.</p>
        <div class="list">
          <div v-for="(t, idx) in balances?.suggested_transfers || []" :key="idx" class="item">
            <div>
              <strong>{{ t.from_name }}</strong> pays <strong>{{ t.to_name }}</strong>:
              {{ money(t.amount_cents, group.currency) }}
            </div>
            <p v-if="transferRoleHint(t)" class="muted" style="margin: 0.35rem 0 0">
              {{ transferRoleHint(t) }}
            </p>
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
      <p class="muted">
        Debtor pays loaner. Balances update only after confirm — either party may confirm or reject.
      </p>
      <div class="list">
        <div v-for="s in settlements" :key="s.id" class="item">
          <div class="row" style="justify-content: space-between; align-items: flex-start">
            <div>
              <div>
                Debtor <strong>{{ s.from_name }}</strong> → loaner <strong>{{ s.to_name }}</strong>:
                {{ money(s.amount_cents, group.currency) }}
              </div>
              <div class="muted" style="margin-top: 0.35rem">{{ settlementStatusLabel(s) }}</div>
            </div>
            <span
              class="badge"
              :class="{
                pending: s.status === SETTLEMENT_STATUS.PENDING,
                closed: s.status === SETTLEMENT_STATUS.REJECTED,
              }"
              >{{ s.status }}</span
            >
          </div>
          <div v-if="canActOnSettlement(s)" class="row" style="margin-top: 0.5rem">
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
        <button type="submit">Send invite</button>
      </form>
      <p v-if="inviteSentMessage" class="muted">
        {{ inviteSentMessage }}. Share this link (also in the email / mail stub):
        <code>{{ inviteSentUrl }}</code>
      </p>
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
