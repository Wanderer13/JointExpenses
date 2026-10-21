export type AppRole = 'user' | 'admin'

export interface User {
  id: number
  email: string
  name: string
  role: AppRole
}

export interface AdminUser {
  id: number
  email: string
  name: string
  role: AppRole
  has_password: boolean
  google_linked: boolean
}

export interface AdminActionLog {
  id: number
  actor_id: number | null
  actor_email: string | null
  action: string
  target_type: string | null
  target_id: number | null
  payload: Record<string, unknown>
  created_at: string
}

export interface ClearLinkedUsersResult {
  deleted_user_ids: number[]
  deleted_count: number
}

export interface Member {
  user_id: number
  role: 'owner' | 'member'
  name: string
  email: string
}

export interface Group {
  id: number
  name: string
  currency: string
  reminder_days: number
  status: 'open' | 'closed'
  invite_token: string
  created_at: string
  members: Member[]
}

export interface Split {
  user_id: number
  amount_cents: number
  shares: number | null
  name?: string | null
  email?: string | null
}

export type SplitType = 'equal' | 'shares' | 'exact'

export const SPLIT_TYPE_LABELS: Record<SplitType, string> = {
  equal: 'Split equally',
  shares: 'By shares',
  exact: 'Exact amounts',
}

export type ExpenseStatus = 'open' | 'completed'

export interface Expense {
  id: number
  group_id: number
  payer_id: number
  created_by_id: number
  amount_cents: number
  split_type: SplitType
  category: string
  expense_date: string
  comment: string | null
  receipt_path: string | null
  status: ExpenseStatus
  created_at: string
  updated_at: string
  splits: Split[]
  payer_name?: string | null
  payer_email?: string | null
}

export interface NetBalance {
  user_id: number
  name: string
  email?: string | null
  balance_cents: number
}

export interface Transfer {
  from_user_id: number
  from_name: string
  from_email?: string | null
  to_user_id: number
  to_name: string
  to_email?: string | null
  amount_cents: number
}

export interface GroupBalances {
  group_id: number
  currency: string
  nets: NetBalance[]
  suggested_transfers: Transfer[]
  sum_check: number
}

export interface Settlement {
  id: number
  group_id: number
  from_user_id: number
  to_user_id: number
  amount_cents: number
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: string
  confirmed_at: string | null
  from_name?: string | null
  from_email?: string | null
  to_name?: string | null
  to_email?: string | null
}

export interface PendingSettlement {
  id: number
  group_id: number
  group_name: string
  currency: string
  from_user_id: number
  to_user_id: number
  amount_cents: number
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: string
  from_name: string
  from_email: string
  to_name: string
  to_email: string
  counterpart_user_id: number
  counterpart_name: string
  counterpart_email: string
  needs_my_action: boolean
}

export interface CurrencyBalanceSummary {
  currency: string
  you_owe_cents: number
  owed_to_you_cents: number
}

export interface OpenExpenseItem {
  id: number
  group_id: number
  group_name: string
  currency: string
  category: string
  amount_cents: number
  expense_date: string
  payer_id: number
  payer_name: string
  payer_email: string
}

export interface MyBalance {
  group_id: number
  group_name: string
  currency: string
  balance_cents: number
}

export interface Overview {
  pending_settlements: PendingSettlement[]
  balances_by_currency: CurrencyBalanceSummary[]
  group_balances: MyBalance[]
  open_expenses: OpenExpenseItem[]
  pending_settlement_count: number
}

export interface SharedGroup {
  id: number
  name: string
  currency: string
  status: 'open' | 'closed'
}

export interface UserProfile {
  id: number
  name: string
  email: string
  shared_groups: SharedGroup[]
}

export interface Activity {
  id: number
  group_id: number
  actor_id: number | null
  actor_name: string | null
  event_type: string
  payload: Record<string, unknown>
  created_at: string
}

export interface NotificationItem {
  id: number
  notification_type: string
  payload: Record<string, unknown>
  read_at: string | null
  created_at: string
}
