"""
Locale-aware date, currency, and number formatting service for FinMind (#131).
Supports ISO, US, EU, UK, Indian (lakh/crore), and Japanese formatting rules.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


LOCALE_PROFILES: dict[str, dict[str, Any]] = {
    "en-US": {
        "name": "English (United States)",
        "currency": "USD",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "standard",
        "date_format": "%m/%d/%Y",
        "datetime_format": "%m/%d/%Y %I:%M %p",
        "symbol_position": "prefix",
    },
    "en-GB": {
        "name": "English (United Kingdom)",
        "currency": "GBP",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "standard",
        "date_format": "%d/%m/%Y",
        "datetime_format": "%d/%m/%Y %H:%M",
        "symbol_position": "prefix",
    },
    "de-DE": {
        "name": "Deutsch (Deutschland)",
        "currency": "EUR",
        "decimal_sep": ",",
        "thousand_sep": ".",
        "grouping": "standard",
        "date_format": "%d.%m.%Y",
        "datetime_format": "%d.%m.%Y %H:%M",
        "symbol_position": "suffix",
    },
    "fr-FR": {
        "name": "Français (France)",
        "currency": "EUR",
        "decimal_sep": ",",
        "thousand_sep": " ",
        "grouping": "standard",
        "date_format": "%d/%m/%Y",
        "datetime_format": "%d/%m/%Y %H:%M",
        "symbol_position": "suffix",
    },
    "en-IN": {
        "name": "English (India)",
        "currency": "INR",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "indian",
        "date_format": "%d/%m/%Y",
        "datetime_format": "%d/%m/%Y %I:%M %p",
        "symbol_position": "prefix",
    },
    "hi-IN": {
        "name": "Hindi (India)",
        "currency": "INR",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "indian",
        "date_format": "%d-%m-%Y",
        "datetime_format": "%d-%m-%Y %H:%M",
        "symbol_position": "prefix",
    },
    "ja-JP": {
        "name": "Japanese (Japan)",
        "currency": "JPY",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "standard",
        "date_format": "%Y/%m/%d",
        "datetime_format": "%Y/%m/%d %H:%M",
        "symbol_position": "prefix",
    },
    "iso-8601": {
        "name": "ISO 8601 International",
        "currency": "USD",
        "decimal_sep": ".",
        "thousand_sep": ",",
        "grouping": "standard",
        "date_format": "%Y-%m-%d",
        "datetime_format": "%Y-%m-%dT%H:%M:%SZ",
        "symbol_position": "prefix",
    },
}

CURRENCY_METADATA: dict[str, dict[str, Any]] = {
    "USD": {"symbol": "$", "decimals": 2},
    "EUR": {"symbol": "€", "decimals": 2},
    "GBP": {"symbol": "£", "decimals": 2},
    "INR": {"symbol": "₹", "decimals": 2},
    "JPY": {"symbol": "¥", "decimals": 0},
    "CAD": {"symbol": "CA$", "decimals": 2},
    "AUD": {"symbol": "A$", "decimals": 2},
    "CHF": {"symbol": "CHF", "decimals": 2},
    "BHD": {"symbol": "BD", "decimals": 3},
}


def normalize_locale(locale_code: str | None) -> str:
    if not locale_code:
        return "en-US"
    cleaned = locale_code.strip().replace("_", "-")
    if cleaned in LOCALE_PROFILES:
        return cleaned
    lower_map = {k.lower(): k for k in LOCALE_PROFILES}
    if cleaned.lower() in lower_map:
        return lower_map[cleaned.lower()]
    lang_prefix = cleaned.split("-")[0].lower()
    for candidate in LOCALE_PROFILES:
        if candidate.lower().startswith(lang_prefix + "-"):
            return candidate
    return "en-US"


def _group_integer_digits(int_str: str, sep: str, mode: str) -> str:
    if len(int_str) <= 3:
        return int_str
    if mode == "indian":
        last_three = int_str[-3:]
        rest = int_str[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        return sep.join(groups + [last_three])
    groups = []
    working = int_str
    while len(working) > 3:
        groups.insert(0, working[-3:])
        working = working[:-3]
    if working:
        groups.insert(0, working)
    return sep.join(groups)


def format_number(
    value: int | float | Decimal | str,
    locale: str = "en-US",
    decimals: int = 2,
) -> str:
    loc = normalize_locale(locale)
    profile = LOCALE_PROFILES[loc]
    dec_val = Decimal(str(value))
    is_neg = dec_val < 0
    abs_val = abs(dec_val)

    quantizer = Decimal("1") if decimals <= 0 else Decimal("1." + ("0" * decimals))
    rounded = abs_val.quantize(quantizer, rounding=ROUND_HALF_UP)
    parts = f"{rounded:f}".split(".")
    grouped_int = _group_integer_digits(parts[0], profile["thousand_sep"], profile["grouping"])

    if decimals > 0:
        frac = parts[1] if len(parts) > 1 else ("0" * decimals)
        formatted = f"{grouped_int}{profile['decimal_sep']}{frac}"
    else:
        formatted = grouped_int

    return f"-{formatted}" if is_neg else formatted


def format_currency(
    amount: int | float | Decimal | str,
    currency: str | None = None,
    locale: str = "en-US",
    accounting_style: bool = False,
) -> str:
    loc = normalize_locale(locale)
    profile = LOCALE_PROFILES[loc]
    curr_code = (currency or profile["currency"]).upper()
    meta = CURRENCY_METADATA.get(curr_code, {"symbol": curr_code + " ", "decimals": 2})

    dec_val = Decimal(str(amount))
    is_neg = dec_val < 0
    formatted_abs = format_number(abs(dec_val), locale=loc, decimals=meta["decimals"])

    if profile["symbol_position"] == "suffix":
        core = f"{formatted_abs} {meta['symbol']}"
    else:
        core = f"{meta['symbol']}{formatted_abs}"

    if is_neg:
        return f"({core})" if accounting_style else f"-{core}"
    return core


def format_date(
    value: str | date | datetime,
    locale: str = "en-US",
    include_time: bool = False,
) -> str:
    loc = normalize_locale(locale)
    profile = LOCALE_PROFILES[loc]
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        raise ValueError(f"Unsupported date value: {value!r}")

    fmt = profile["datetime_format"] if include_time else profile["date_format"]
    return dt.strftime(fmt)


def get_supported_locales() -> list[dict[str, Any]]:
    return [
        {
            "locale": code,
            "name": data["name"],
            "default_currency": data["currency"],
            "date_format": data["date_format"],
            "grouping": data["grouping"],
        }
        for code, data in LOCALE_PROFILES.items()
    ]
