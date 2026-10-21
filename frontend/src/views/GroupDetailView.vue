<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, money, receiptUrl, wsUrl } from '../api'
import PersonLink from '../components/PersonLink.vue'
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
import { eventLabel } from '../eventLabels'
import { useAuthStore } from '../stores/auth'
import { useOverviewStore } from '../stores/overview'
import {
  SPLIT_TYPE_LABELS,
  type Activity,
  type Expense,
  type Group,
  type GroupBalances,
  type Settlement,
  type SplitType,
} from '../types'

type GroupTab = 'people' | 'expenses' | 'settle' | 'activity'
type ExpenseFilter = 'open' | 'completed' | 'all'

const TAB_LABELS: Record<GroupTab, string> = {
  people: 'People',
  expenses: 'Expenses',
  settle: 'Settle',
  activity: 'Activity',
}

const TAB_SUBTITLES: Record<GroupTab, string> = {
  people: 'Invite others — the link works even before they register.',
  expenses: 'Add what was paid. Settle later under Settle.',
  settle: 'Mark what you paid, or confirm a pending payment.',
  activity: 'What happened in this group.',
}

const TAB_ALIASES: Record<string, GroupTab> = {
  people: 'people',
  expenses: 'expenses',
  settle: 'settle',
  activity: 'activity',
  share: 'expenses',
  invite: 'people',
  balances: 'settle',
  settlements: 'settle',
}

const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const overview = useOverviewStore()
const route = useRoute()
const router = useRouter()

const checklistDismissed = ref(false)
const showSettings = ref(false)
const showAdvancedSplit = ref(false)
const linkCopied = ref(false)
const flash = ref('')
let flashTimer: ReturnType<typeof setTimeout> | null = null
const tablistEl = ref<HTMLElement | null>(null)

function resolveTab(raw: unknown): GroupTab | null {
  if (typeof raw !== 'string') return null
  return TAB_ALIASES[raw] || null
}

function defaultTab(): GroupTab {
  const members = group.value?.members.length ?? 0
  return members <= 1 ? 'people' : 'expenses'
}

function tabFromQuery(): GroupTab {
  return resolveTab(route.query.tab) || defaultTab()
}

const tab = ref<GroupTab>('expenses')
const expenseFilter = ref<ExpenseFilter>('open')
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
const showJoinToken = ref(false)
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
const alone = computed(() => (group.value?.members.length ?? 0) <= 1)
const inviteLink = computed(() =>
  group.value ? `${window.location.origin}/join/${group.value.invite_token}` : '',
)
const formTitle = computed(() => (editingExpenseId.value ? 'Edit expense' : 'Add expense'))
const tabLabel = computed(() => TAB_LABELS[tab.value])

const filteredExpenses = computed(() => {
  if (expenseFilter.value === 'all') return expenses.value
  if (expenseFilter.value === 'completed') {
    return expenses.value.filter((e) => e.status === EXPENSE_STATUS.COMPLETED)
  }
  return expenses.value.filter((e) => e.status !== EXPENSE_STATUS.COMPLETED)
})

const pendingSettlements = computed(() =>
  settlements.value.filter((s) => s.status === SETTLEMENT_STATUS.PENDING),
)
const historySettlements = computed(() =>
  settlements.value.filter((s) => s.status !== SETTLEMENT_STATUS.PENDING),
)
const actionablePendingCount = computed(
  () => pendingSettlements.value.filter((s) => canActOnSettlement(s)).length,
)

const myNet = computed(() => {
  if (!auth.user || !balances.value) return null
  return balances.value.nets.find((n) => n.user_id === auth.user!.id) || null
})

const myTransfers = computed(() => {
  if (!auth.user || !balances.value) return []
  return balances.value.suggested_transfers.filter(
    (t) => t.from_user_id === auth.user!.id || t.to_user_id === auth.user!.id,
  )
})

const iNeedToPay = computed(() =>
  myTransfers.value.filter((t) => auth.user && t.from_user_id === auth.user.id),
)
const theyNeedToPayMe = computed(() =>
  myTransfers.value.filter((t) => auth.user && t.to_user_id === auth.user.id),
)

function memberAwaiting(userId: number): boolean {
  return group.value?.members.some((m) => m.user_id === userId && m.awaiting_signup) ?? false
}

const checklistInviteDone = computed(() => (group.value?.members.length ?? 0) >= 2)
const checklistExpenseDone = computed(() => expenses.value.length > 0)
const checklistSettleDone = computed(
  () =>
    settlements.value.some((s) => s.status === SETTLEMENT_STATUS.CONFIRMED) ||
    (myNet.value !== null && myNet.value.balance_cents === 0 && expenses.value.length > 0),
)
const showChecklist = computed(
  () =>
    !checklistDismissed.value &&
    !(checklistInviteDone.value && checklistExpenseDone.value && checklistSettleDone.value),
)

function showFlash(msg: string) {
  flash.value = msg
  if (flashTimer) clearTimeout(flashTimer)
  flashTimer = setTimeout(() => {
    flash.value = ''
  }, 3500)
}

async function setTab(next: GroupTab) {
  tab.value = next
  await router.replace({ query: { ...route.query, tab: next } })
  await nextTick()
  const active = tablistEl.value?.querySelector<HTMLElement>('button.active')
  active?.focus()
}

function canMutateExpense(e: Expense): boolean {
  if (!auth.user || !group.value) return false
  if (auth.user.id === e.payer_id || auth.user.id === e.created_by_id) return true
  return group.value.members.some(
    (m) => m.user_id === auth.user?.id && m.role === MEMBER_ROLE.OWNER,
  )
}

function isExpenseOpen(e: Expense): boolean {
  return e.status !== EXPENSE_STATUS.COMPLETED
}

function isReceiptImage(path: string | null | undefined): boolean {
  if (!path) return false
  return /\.(jpe?g|png|webp)$/i.test(path)
}

function plainNetLabel(balanceCents: number, isYou: boolean, name: string): string {
  if (balanceCents === 0) return isYou ? 'You are settled' : `${name} is settled`
  if (balanceCents < 0) return isYou ? 'You owe' : `${name} owes`
  return isYou ? 'You are owed' : `${name} is owed`
}

function settlementStatusLabel(s: Settlement): string {
  const from = s.from_name || 'Someone'
  const to = s.to_name || 'Someone'
  if (s.status === SETTLEMENT_STATUS.PENDING) {
    return `Pending — ${from} pays ${to} (either can confirm)`
  }
  if (s.status === SETTLEMENT_STATUS.CONFIRMED) {
    const when = s.confirmed_at ? ` · ${new Date(s.confirmed_at).toLocaleString()}` : ''
    return `Confirmed — ${from} paid ${to}${when}`
  }
  return `Rejected — propose again from Settle (${from} → ${to})`
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
  showAdvancedSplit.value = false
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
  showAdvancedSplit.value = e.split_type !== SPLIT_TYPE.EQUAL
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
  void setTab('expenses')
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
    const wasEdit = !!expenseId
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
    showFlash(wasEdit ? 'Expense updated' : 'Expense saved')
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
    showFlash('Expense deleted')
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
    showFlash(status === EXPENSE_STATUS.COMPLETED ? 'Expense completed (edits locked)' : 'Expense reopened')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

async function settle(
  fromId: number,
  toId: number,
  amountCents: number,
  confirmNow = false,
) {
  if (!group.value) return
  error.value = ''
  try {
    await api(`/api/groups/${group.value.id}/settlements`, {
      method: 'POST',
      body: JSON.stringify({
        from_user_id: fromId,
        to_user_id: toId,
        amount_cents: amountCents,
        confirm_now: confirmNow,
      }),
    })
    await refreshAll()
    void overview.refresh()
    showFlash(
      confirmNow
        ? 'Payment recorded — balance updated'
        : 'Payment recorded — confirm below (or wait for the other person)',
    )
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed'
  }
}

/** Debtor declares "I paid" and clears the debt in one step. */
async function iPaid(fromId: number, toId: number, amountCents: number) {
  await settle(fromId, toId, amountCents, true)
}

async function settlementAction(id: number, action: 'confirm' | 'reject') {
  error.value = ''
  try {
    await api(`/api/settlements/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    await refreshAll()
    void overview.refresh()
    showFlash(
      action === 'confirm'
        ? 'Payment confirmed — debt cleared'
        : 'Rejected — propose again from Settle',
    )
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
    showFlash('Invite sent — share the link if they are not registered yet')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to send invite'
  }
}

async function copyInviteLink() {
  if (!inviteLink.value) return
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    linkCopied.value = true
    setTimeout(() => {
      linkCopied.value = false
    }, 2000)
  } catch {
    error.value = 'Could not copy — select the link manually'
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
    checklistDismissed.value = false
    await refreshAll()
    tab.value = tabFromQuery()
    if (!route.query.tab) {
      await router.replace({ query: { ...route.query, tab: tab.value } })
    }
    connectWs()
  },
)

watch(
  () => route.query.tab,
  () => {
    const resolved = resolveTab(route.query.tab)
    if (resolved) tab.value = resolved
  },
)

onMounted(async () => {
  await refreshAll()
  tab.value = tabFromQuery()
  if (!route.query.tab) {
    await router.replace({ query: { ...route.query, tab: tab.value } })
  }
  connectWs()
})

onUnmounted(() => {
  socket?.close()
  if (flashTimer) clearTimeout(flashTimer)
})
</script>

<template>
  <div v-if="group" class="stack group-detail">
    <nav class="breadcrumb muted" aria-label="Breadcrumb">
      <RouterLink to="/">Home</RouterLink>
      <span aria-hidden="true"> / </span>
      <span>{{ group.name }}</span>
      <span aria-hidden="true"> / </span>
      <span aria-current="page">{{ tabLabel }}</span>
    </nav>

    <section class="panel stack">
      <div class="row" style="justify-content: space-between">
        <div>
          <h1>{{ group.name }}</h1>
          <p class="muted">{{ group.currency }} · {{ group.members.length }} members</p>
        </div>
        <span class="badge" :class="{ closed: closed }">{{ group.status }}</span>
      </div>

      <div v-if="showChecklist" class="journey">
        <div class="journey-steps">
          <button
            type="button"
            class="journey-step"
            :class="{ done: checklistInviteDone, current: !checklistInviteDone }"
            @click="setTab('people')"
          >
            <span class="journey-num">1</span>
            Invite
          </button>
          <button
            type="button"
            class="journey-step"
            :class="{
              done: checklistExpenseDone,
              current: checklistInviteDone && !checklistExpenseDone,
            }"
            @click="setTab('expenses')"
          >
            <span class="journey-num">2</span>
            Expense
          </button>
          <button
            type="button"
            class="journey-step"
            :class="{
              done: checklistSettleDone,
              current: checklistExpenseDone && !checklistSettleDone,
            }"
            @click="setTab('settle')"
          >
            <span class="journey-num">3</span>
            Settle
          </button>
        </div>
        <button class="linkish journey-dismiss" type="button" @click="checklistDismissed = true">
          Hide
        </button>
      </div>

      <button v-if="alone" type="button" class="nudge-btn" @click="setTab('people')">
        <strong>Invite people</strong>
        <span>They appear in expenses right away — they finish signup later via the link.</span>
      </button>

      <div ref="tablistEl" class="tabs" role="tablist" aria-label="Group sections">
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'people'"
          :class="{ active: tab === 'people' }"
          @click="setTab('people')"
        >
          People
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'expenses'"
          :class="{ active: tab === 'expenses' }"
          @click="setTab('expenses')"
        >
          Expenses
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'settle'"
          :class="{ active: tab === 'settle' }"
          @click="setTab('settle')"
        >
          Settle
          <span v-if="actionablePendingCount" class="badge pending nav-badge">{{
            actionablePendingCount
          }}</span>
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'activity'"
          :class="{ active: tab === 'activity' }"
          @click="setTab('activity')"
        >
          Activity
        </button>
      </div>
      <p class="muted tab-subtitle">{{ TAB_SUBTITLES[tab] }}</p>

      <div v-if="isOwner">
        <button class="linkish" type="button" @click="showSettings = !showSettings">
          {{ showSettings ? 'Hide group settings' : 'Group settings' }}
        </button>
        <div v-if="showSettings" class="stack" style="margin-top: 0.75rem">
          <form
            class="row"
            style="align-items: flex-end; gap: 0.75rem; flex-wrap: wrap"
            @submit.prevent="saveCurrency"
          >
            <label style="margin: 0">
              Currency
              <select v-model="editCurrency">
                <option v-for="c in CURRENCIES" :key="c.code" :value="c.code">
                  {{ c.code }} — {{ c.label }}
                </option>
              </select>
            </label>
            <button type="submit" :disabled="currencySaving || editCurrency === group.currency">
              {{ currencySaving ? 'Saving…' : 'Update' }}
            </button>
          </form>
          <p class="muted" style="font-size: 0.85rem">
            Display only — amounts are not converted. Reminders after {{ group.reminder_days }} days.
          </p>
          <button class="secondary" type="button" @click="closeOrReopen">
            {{ closed ? 'Reopen group' : 'Close group' }}
          </button>
        </div>
      </div>
    </section>

    <p v-if="flash" class="flash muted">{{ flash }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- People -->
    <section v-if="tab === 'people'" class="panel stack">
      <h2>Invite</h2>
      <div class="row" style="flex-wrap: wrap; gap: 0.5rem">
        <code class="invite-url">{{ inviteLink }}</code>
        <button type="button" class="touch-btn" @click="copyInviteLink">
          {{ linkCopied ? 'Copied' : 'Copy link' }}
        </button>
      </div>
      <form class="stack" @submit.prevent="invite">
        <label>Invite by email <input v-model="inviteEmail" type="email" required /></label>
        <button type="submit" class="touch-btn">Send invite</button>
      </form>
      <p v-if="inviteSentMessage" class="muted">
        {{ inviteSentMessage }}. Link:
        <code>{{ inviteSentUrl }}</code>
      </p>
      <button class="linkish" type="button" @click="showJoinToken = !showJoinToken">
        {{ showJoinToken ? 'Hide' : 'Have a join token?' }}
      </button>
      <form v-if="showJoinToken" class="stack" @submit.prevent="joinWithToken">
        <label>Join token <input v-model="joinToken" required /></label>
        <button class="secondary" type="submit">Join</button>
      </form>
      <h3>Members</h3>
      <p class="muted">Invited people can split expenses before they create an account.</p>
      <div class="list">
        <div v-for="m in group.members" :key="m.user_id" class="item">
          <PersonLink :user-id="m.user_id" :name="m.name" :email="m.email" show-email />
          · {{ m.role }}
          <span v-if="m.awaiting_signup" class="badge pending">invited</span>
        </div>
      </div>
    </section>

    <!-- Expenses -->
    <section v-else-if="tab === 'expenses'" class="grid-2 expenses-layout">
      <div class="panel stack">
        <h2>Expenses</h2>
        <div class="row" style="gap: 0.4rem">
          <button
            type="button"
            class="secondary"
            :class="{ active: expenseFilter === 'open' }"
            @click="expenseFilter = 'open'"
          >
            Open
          </button>
          <button
            type="button"
            class="secondary"
            :class="{ active: expenseFilter === 'completed' }"
            @click="expenseFilter = 'completed'"
          >
            Completed
          </button>
          <button
            type="button"
            class="secondary"
            :class="{ active: expenseFilter === 'all' }"
            @click="expenseFilter = 'all'"
          >
            All
          </button>
        </div>
        <div class="list">
          <div v-for="e in filteredExpenses" :key="e.id" class="item">
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
              Paid by
              <PersonLink
                :user-id="e.payer_id"
                :name="e.payer_name || 'Unknown'"
                :email="e.payer_email"
              />
              · {{ SPLIT_TYPE_LABELS[e.split_type] }}
              <span v-if="e.comment"> · {{ e.comment }}</span>
            </div>
            <div class="muted row" style="gap: 0.35rem; flex-wrap: wrap">
              <span v-for="s in e.splits" :key="s.user_id">
                <PersonLink :user-id="s.user_id" :name="s.name || 'Unknown'" :email="s.email" />:
                {{ money(s.amount_cents, group.currency) }}
              </span>
            </div>
            <div v-if="e.receipt_path" class="receipt-row">
              <img
                v-if="isReceiptImage(e.receipt_path)"
                class="receipt-thumb"
                :src="receiptUrl(e.id)"
                alt="Receipt"
              />
              <a :href="receiptUrl(e.id)" target="_blank" rel="noopener">Receipt</a>
            </div>
            <div v-if="!closed && canMutateExpense(e)" class="row" style="margin-top: 0.5rem; gap: 0.5rem">
              <button
                v-if="isExpenseOpen(e)"
                class="secondary touch-btn"
                type="button"
                @click="setExpenseStatus(e.id, EXPENSE_STATUS.COMPLETED)"
              >
                Complete
              </button>
              <button
                v-else
                class="secondary touch-btn"
                type="button"
                @click="setExpenseStatus(e.id, EXPENSE_STATUS.OPEN)"
              >
                Reopen
              </button>
              <button
                v-if="isExpenseOpen(e)"
                class="secondary touch-btn"
                type="button"
                @click="startEdit(e)"
              >
                Edit
              </button>
              <button
                v-if="isExpenseOpen(e)"
                class="danger touch-btn"
                type="button"
                @click="deleteExpense(e.id)"
              >
                Delete
              </button>
            </div>
          </div>
          <p v-if="!filteredExpenses.length" class="muted">
            <template v-if="!expenses.length">
              No expenses yet —
              <a href="#add-expense">add the first expense</a>.
            </template>
            <template v-else>No expenses match this filter.</template>
          </p>
        </div>
      </div>

      <form id="add-expense" class="panel stack sticky-form" @submit.prevent="saveExpense">
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
          <div class="stack">
            <strong>Participants</strong>
            <label v-for="m in group.members" :key="m.user_id" class="row">
              <input v-model="selected[m.user_id]" type="checkbox" />
              <span style="min-width: 5rem">{{ m.name }}</span>
              <span v-if="m.awaiting_signup" class="badge pending">invited</span>
            </label>
            <p v-if="group.members.length < 2" class="muted">
              Invite someone under People first — they show up here immediately.
            </p>
          </div>
          <button
            class="linkish"
            type="button"
            @click="showAdvancedSplit = !showAdvancedSplit"
          >
            {{ showAdvancedSplit ? 'Hide more options' : 'More options (shares / exact)' }}
          </button>
          <template v-if="showAdvancedSplit">
            <label>
              Split type
              <select v-model="splitType">
                <option v-for="(label, value) in SPLIT_TYPE_LABELS" :key="value" :value="value">
                  {{ label }}
                </option>
              </select>
            </label>
            <label v-for="m in group.members" :key="'adv-' + m.user_id" class="row">
              <span style="min-width: 5rem">{{ m.name }}</span>
              <input
                v-if="splitType === SPLIT_TYPE.SHARES"
                v-model.number="shares[m.user_id]"
                type="number"
                min="1"
                style="width: 5rem"
                title="Shares"
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
              />
            </label>
          </template>
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
          <button type="submit" class="touch-btn">{{ editingExpenseId ? 'Update expense' : 'Save expense' }}</button>
        </fieldset>
      </form>
    </section>

    <!-- Settle -->
    <section v-else-if="tab === 'settle'" class="stack settle-layout">
      <div class="panel stack">
        <h2>Your position</h2>
        <div v-if="myNet" class="item row" style="justify-content: space-between">
          <span>{{ plainNetLabel(myNet.balance_cents, true, 'You') }}</span>
          <span :class="myNet.balance_cents >= 0 ? 'pos' : 'neg'">{{
            money(Math.abs(myNet.balance_cents), group.currency)
          }}</span>
        </div>
        <p class="muted" style="font-size: 0.85rem">
          Reminders after {{ group.reminder_days }} days of unpaid debt (email, at most weekly).
        </p>
      </div>

      <div class="panel stack">
        <h2>Open payments</h2>
        <p class="muted">
          Balances stay until you press a button below. Paying for an expense does not settle debt by
          itself.
        </p>
        <div class="list">
          <div v-for="(t, idx) in iNeedToPay" :key="'pay-' + idx" class="item">
            <div>
              <strong>You owe</strong>
              <PersonLink :user-id="t.to_user_id" :name="t.to_name" :email="t.to_email" />
              {{ money(t.amount_cents, group.currency) }}
              <span v-if="memberAwaiting(t.to_user_id)" class="badge pending">invited</span>
            </div>
            <p class="muted" style="margin: 0.35rem 0 0">
              Press the button after you actually pay — nothing is cleared until then.
            </p>
            <button
              v-if="!closed"
              class="touch-btn"
              style="margin-top: 0.5rem"
              type="button"
              @click="iPaid(t.from_user_id, t.to_user_id, t.amount_cents)"
            >
              I paid {{ money(t.amount_cents, group.currency) }}
            </button>
          </div>

          <div v-for="(t, idx) in theyNeedToPayMe" :key="'owed-' + idx" class="item">
            <div>
              <strong>You are owed</strong>
              —
              <PersonLink :user-id="t.from_user_id" :name="t.from_name" :email="t.from_email" />
              should pay you {{ money(t.amount_cents, group.currency) }}
              <span v-if="memberAwaiting(t.from_user_id)" class="badge pending">invited</span>
            </div>
            <p class="muted" style="margin: 0.35rem 0 0">
              <template v-if="memberAwaiting(t.from_user_id)">
                They have not signed up — you can confirm receipt yourself.
              </template>
              <template v-else>
                When they pay you, confirm it here (or ask them to tap “I paid”).
              </template>
            </p>
            <button
              v-if="!closed"
              class="touch-btn"
              style="margin-top: 0.5rem"
              type="button"
              @click="settle(t.from_user_id, t.to_user_id, t.amount_cents, true)"
            >
              They paid me {{ money(t.amount_cents, group.currency) }}
            </button>
          </div>

          <p v-if="!iNeedToPay.length && !theyNeedToPayMe.length" class="muted">
            <template v-if="myNet && myNet.balance_cents === 0">
              All settled in this group — nothing to pay.
            </template>
            <template v-else>
              No suggested payments yet. Add a shared expense first, or check Everyone below.
            </template>
          </p>
        </div>
      </div>

      <div class="panel stack">
        <h2>Confirm payment</h2>
        <p class="muted">Pending payments you can confirm or reject.</p>
        <div class="list">
          <div v-for="s in pendingSettlements" :key="s.id" class="item">
            <div class="row" style="justify-content: space-between">
              <div>
                <PersonLink
                  :user-id="s.from_user_id"
                  :name="s.from_name || 'Unknown'"
                  :email="s.from_email"
                />
                →
                <PersonLink
                  :user-id="s.to_user_id"
                  :name="s.to_name || 'Unknown'"
                  :email="s.to_email"
                />:
                {{ money(s.amount_cents, group.currency) }}
                <span
                  v-if="memberAwaiting(s.from_user_id) || memberAwaiting(s.to_user_id)"
                  class="badge pending"
                  >invited party</span
                >
              </div>
              <span class="badge pending">pending</span>
            </div>
            <div v-if="canActOnSettlement(s)" class="row" style="margin-top: 0.5rem; gap: 0.5rem">
              <button type="button" class="touch-btn" @click="settlementAction(s.id, 'confirm')">
                Confirm payment
              </button>
              <button
                class="secondary touch-btn"
                type="button"
                @click="settlementAction(s.id, 'reject')"
              >
                Reject
              </button>
            </div>
          </div>
          <p v-if="!pendingSettlements.length" class="muted">No payments waiting for confirm.</p>
        </div>
      </div>

      <div v-if="historySettlements.length" class="panel stack">
        <h2>History</h2>
        <div class="list">
          <div v-for="s in historySettlements" :key="s.id" class="item">
            <div class="row" style="justify-content: space-between">
              <div>
                {{ money(s.amount_cents, group.currency) }} —
                {{ settlementStatusLabel(s) }}
              </div>
              <span
                class="badge"
                :class="{
                  closed: s.status === SETTLEMENT_STATUS.REJECTED,
                  completed: s.status === SETTLEMENT_STATUS.CONFIRMED,
                }"
                >{{ s.status }}</span
              >
            </div>
          </div>
        </div>
      </div>

      <div class="panel stack">
        <h3>Everyone</h3>
        <div class="list">
          <div
            v-for="n in balances?.nets || []"
            :key="n.user_id"
            class="item row"
            style="justify-content: space-between"
          >
            <span>
              <PersonLink :user-id="n.user_id" :name="n.name" :email="n.email" />
              · {{ plainNetLabel(n.balance_cents, n.user_id === auth.user?.id, n.name) }}
            </span>
            <span :class="n.balance_cents >= 0 ? 'pos' : 'neg'">{{
              money(Math.abs(n.balance_cents), group.currency)
            }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Activity -->
    <section v-else class="panel stack">
      <h2>Activity</h2>
      <div class="list">
        <div v-for="a in activity" :key="a.id" class="item">
          <strong>{{ eventLabel(a.event_type) }}</strong>
          <div class="muted">
            <PersonLink
              v-if="a.actor_id && a.actor_name"
              :user-id="a.actor_id"
              :name="a.actor_name"
            />
            <template v-else>{{ a.actor_name || 'system' }}</template>
            · {{ new Date(a.created_at).toLocaleString() }}
          </div>
        </div>
        <p v-if="!activity.length" class="muted">Actions will show up here.</p>
      </div>
    </section>
  </div>
  <p v-else class="muted">Loading…</p>
</template>
