/** Human-readable labels for activity / notification event types. */

export const EVENT_LABELS: Record<string, string> = {
  settlement_pending: 'Payment awaiting confirm',
  settlement_confirmed: 'Payment confirmed',
  settlement_rejected: 'Payment rejected',
  expense_created: 'Expense added',
  expense_updated: 'Expense updated',
  expense_deleted: 'Expense deleted',
  expense_completed: 'Expense completed',
  expense_reopened: 'Expense reopened',
  member_joined: 'Member joined',
  group_closed: 'Group closed',
  group_reopened: 'Group reopened',
  invite_sent: 'Invite sent',
}

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] || type.replace(/_/g, ' ')
}

/** Map notification type → group tab for deep links. */
export function notificationTab(type: string): 'settle' | 'expenses' | 'activity' | 'people' {
  if (type.startsWith('settlement')) return 'settle'
  if (type.startsWith('expense')) return 'expenses'
  if (type === 'invite_sent' || type === 'member_joined') return 'people'
  return 'activity'
}
