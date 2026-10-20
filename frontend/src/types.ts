export interface User {
  id: number
  email: string
  name: string
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
}

export type SplitType = 'equal' | 'shares' | 'exact'

export const SPLIT_TYPE_LABELS: Record<SplitType, string> = {
  equal: 'Split equally',
  shares: 'By shares',
  exact: 'Exact amounts',
}

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
  created_at: string
  updated_at: string
  splits: Split[]
  payer_name?: string | null
}

export interface NetBalance {
  user_id: number
  name: string
  balance_cents: number
}

export interface Transfer {
  from_user_id: number
  from_name: string
  to_user_id: number
  to_name: string
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
  to_name?: string | null
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

export interface MyBalance {
  group_id: number
  group_name: string
  currency: string
  balance_cents: number
}
