from datetime import date, datetime
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.locale_formatter import (
    format_currency,
    format_date,
    format_number,
    get_supported_locales,
    normalize_locale,
)


def test_us_and_gb_currency_formatting():
    assert format_currency(1234567.89, "USD", "en-US") == "$1,234,567.89"
    assert format_currency(1234567.89, "GBP", "en-GB") == "£1,234,567.89"


def test_indian_lakh_crore_grouping():
    assert format_currency(1234567.89, "INR", "en-IN") == "₹12,34,567.89"
    assert format_number(10000000, locale="hi-IN", decimals=0) == "1,00,00,000"


def test_european_decimal_and_suffix_currency():
    assert format_currency(1234.56, "EUR", "de-DE") == "1.234,56 €"
    assert format_currency(1234.56, "EUR", "fr-FR") == "1 234,56 €"


def test_zero_and_three_decimal_currencies():
    assert format_currency(15890.4, "JPY", "ja-JP") == "¥15,890"
    assert format_currency(42.5, "BHD", "en-US") == "BD42.500"


def test_negative_and_accounting_style_currency():
    assert format_currency(-250.5, "USD", "en-US", accounting_style=False) == "-$250.50"
    assert format_currency(-250.5, "USD", "en-US", accounting_style=True) == "($250.50)"


def test_locale_aware_date_formatting():
    d = date(2026, 11, 5)
    assert format_date(d, "en-US") == "11/05/2026"
    assert format_date(d, "en-GB") == "05/11/2026"
    assert format_date(d, "de-DE") == "05.11.2026"
    assert format_date(d, "iso-8601") == "2026-11-05"
    assert format_date("2026-11-05T14:30:00Z", "ja-JP", include_time=True) == "2026/11/05 14:30"


def test_normalize_locale_and_supported_list():
    assert normalize_locale("en_in") == "en-IN"
    assert normalize_locale("de") == "de-DE"
    assert normalize_locale("unknown-XX") == "en-US"
    locales = get_supported_locales()
    assert len(locales) >= 8
