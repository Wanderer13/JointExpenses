import { DEFAULT_CURRENCY, HTTP_NO_CONTENT, centsToMajor } from './constants'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** In-memory access token for Authorization header / WS fallback (cookies are primary). */
let accessToken: string | null = null

export function getToken(): string | null {
  return accessToken
}

export function setToken(token: string | null) {
  accessToken = token
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(path, { ...options, headers, credentials: 'include' })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === HTTP_NO_CONTENT) return undefined as T
  return res.json()
}

export function money(cents: number, currency = DEFAULT_CURRENCY): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(centsToMajor(cents))
}

export function wsUrl(groupId: number): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const q = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}://${location.host}/ws/groups/${groupId}${q}`
}

export function receiptUrl(expenseId: number): string {
  return `/api/expenses/${expenseId}/receipt`
}
