"""ISO-4217 allowlist for group currencies (must stay in sync with frontend)."""

from __future__ import annotations

ALLOWED_CURRENCIES: frozenset[str] = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "RUB",
        "KZT",
        "TRY",
        "JPY",
        "CNY",
        "INR",
        "CAD",
        "AUD",
        "CHF",
        "PLN",
        "CZK",
        "UAH",
        "BRL",
        "MXN",
        "SEK",
        "NOK",
        "DKK",
        "NZD",
        "SGD",
        "HKD",
        "KRW",
        "AED",
        "SAR",
        "ILS",
        "THB",
        "VND",
        "IDR",
        "MYR",
        "PHP",
        "ZAR",
    }
)


def normalize_currency(code: str) -> str:
    return code.strip().upper()


def is_allowed_currency(code: str) -> bool:
    return normalize_currency(code) in ALLOWED_CURRENCIES
