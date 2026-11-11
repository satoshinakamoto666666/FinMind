"""
REST endpoints for locale-aware date, currency & number formatting (#131).
"""

from flask import Blueprint, jsonify, request
from app.services.locale_formatter import (
    format_currency,
    format_date,
    format_number,
    get_supported_locales,
    normalize_locale,
)

locale_bp = Blueprint("locale", __name__, url_prefix="/api/locale")


@locale_bp.route("/supported", methods=["GET"])
def list_supported_locales():
    return jsonify({"locales": get_supported_locales()}), 200


@locale_bp.route("/format", methods=["POST"])
def format_payload():
    data = request.get_json(silent=True) or {}
    locale = normalize_locale(data.get("locale", "en-US"))
    currency = data.get("currency")
    result = {"locale": locale}

    if "amount" in data:
        result["formatted_currency"] = format_currency(
            data["amount"],
            currency=currency,
            locale=locale,
            accounting_style=bool(data.get("accounting_style", False)),
        )
    if "number" in data:
        result["formatted_number"] = format_number(
            data["number"],
            locale=locale,
            decimals=int(data.get("decimals", 2)),
        )
    if "date" in data:
        result["formatted_date"] = format_date(
            data["date"],
            locale=locale,
            include_time=bool(data.get("include_time", False)),
        )
    return jsonify(result), 200
