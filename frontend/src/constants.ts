/** Shared UI/domain constants (keep in sync with backend app.constants where applicable). */

export const CENTS_PER_UNIT = 100
export const DEFAULT_CURRENCY = 'USD'
export const DEFAULT_CATEGORY = 'general'
export const DEFAULT_SPLIT_TYPE = 'equal' as const
export const DEFAULT_REMINDER_DAYS = 7
export const MIN_REMINDER_DAYS = 1
export const MAX_REMINDER_DAYS = 365

export const GROUP_STATUS = {
  OPEN: 'open',
  CLOSED: 'closed',
} as const

export const MEMBER_ROLE = {
  OWNER: 'owner',
  MEMBER: 'member',
} as const

export const SETTLEMENT_STATUS = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  REJECTED: 'rejected',
} as const

export const SPLIT_TYPE = {
  EQUAL: 'equal',
  SHARES: 'shares',
  EXACT: 'exact',
} as const

/** Substring of backend GOOGLE_LINK_PASSWORD_REQUIRED detail. */
export const GOOGLE_LINK_PASSWORD_HINT = 'provide password'

export const HTTP_CONFLICT = 409
export const HTTP_NO_CONTENT = 204

export const AMOUNT_INPUT_STEP = '0.01'
export const AMOUNT_INPUT_MIN = '0.01'

export function centsToMajor(cents: number): number {
  return cents / CENTS_PER_UNIT
}

export function majorToCents(major: number | string): number {
  const value = typeof major === 'string' ? parseFloat(major || '0') : major
  return Math.round(value * CENTS_PER_UNIT)
}

export function formatMajorInput(cents: number): string {
  return centsToMajor(cents).toFixed(2)
}

/** In-app destinations that show the main shell tabs after login. */
const APP_TAB_PREFIXES = ['/groups', '/balances', '/notifications', '/join'] as const

/** Only same-origin relative paths; blocks open redirects and the login page. */
export function safeRedirectPath(raw: unknown, fallback = '/'): string {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//')) {
    return fallback
  }
  if (raw === '/login' || raw.startsWith('/login?')) {
    return fallback
  }
  return raw
}

/** Prefer a deep link when safe; otherwise land on Groups. */
export function postLoginPath(raw: unknown): string {
  const path = safeRedirectPath(raw, '/')
  if (path === '/') return '/'
  if (APP_TAB_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) {
    return path
  }
  return '/'
}
