export interface CurrencyOption {
  code: string
  label: string
}

/** Curated ISO-4217 codes used by the group currency selector. */
export const CURRENCIES: CurrencyOption[] = [
  { code: 'USD', label: 'US Dollar' },
  { code: 'EUR', label: 'Euro' },
  { code: 'GBP', label: 'British Pound' },
  { code: 'RUB', label: 'Russian Ruble' },
  { code: 'KZT', label: 'Kazakhstani Tenge' },
  { code: 'TRY', label: 'Turkish Lira' },
  { code: 'JPY', label: 'Japanese Yen' },
  { code: 'CNY', label: 'Chinese Yuan' },
  { code: 'INR', label: 'Indian Rupee' },
  { code: 'CAD', label: 'Canadian Dollar' },
  { code: 'AUD', label: 'Australian Dollar' },
  { code: 'CHF', label: 'Swiss Franc' },
  { code: 'PLN', label: 'Polish Złoty' },
  { code: 'CZK', label: 'Czech Koruna' },
  { code: 'UAH', label: 'Ukrainian Hryvnia' },
  { code: 'BRL', label: 'Brazilian Real' },
  { code: 'MXN', label: 'Mexican Peso' },
  { code: 'SEK', label: 'Swedish Krona' },
  { code: 'NOK', label: 'Norwegian Krone' },
  { code: 'DKK', label: 'Danish Krone' },
  { code: 'NZD', label: 'New Zealand Dollar' },
  { code: 'SGD', label: 'Singapore Dollar' },
  { code: 'HKD', label: 'Hong Kong Dollar' },
  { code: 'KRW', label: 'South Korean Won' },
  { code: 'AED', label: 'UAE Dirham' },
  { code: 'SAR', label: 'Saudi Riyal' },
  { code: 'ILS', label: 'Israeli Shekel' },
  { code: 'THB', label: 'Thai Baht' },
  { code: 'VND', label: 'Vietnamese Dong' },
  { code: 'IDR', label: 'Indonesian Rupiah' },
  { code: 'MYR', label: 'Malaysian Ringgit' },
  { code: 'PHP', label: 'Philippine Peso' },
  { code: 'ZAR', label: 'South African Rand' },
]

const CODES = new Set(CURRENCIES.map((c) => c.code))

export function isSupportedCurrency(code: string): boolean {
  return CODES.has(code.toUpperCase())
}

export function currencyLabel(code: string): string {
  const found = CURRENCIES.find((c) => c.code === code.toUpperCase())
  return found ? `${found.code} — ${found.label}` : code
}

/** Suggest a group currency from the browser locale; fall back to USD. */
export function suggestCurrency(): string {
  try {
    const code = Intl.NumberFormat().resolvedOptions().currency?.toUpperCase()
    if (code && CODES.has(code)) return code
  } catch {
    /* ignore */
  }
  return 'USD'
}
