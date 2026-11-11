from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services.ai import monthly_budget_suggestion
from ..services.digest import generate_weekly_digest
import logging

bp = Blueprint("insights", __name__)
logger = logging.getLogger("finmind.insights")


@bp.get("/budget-suggestion")
@jwt_required()
def budget_suggestion():
    uid = int(get_jwt_identity())
    ym = (request.args.get("month") or date.today().strftime("%Y-%m")).strip()
    user_gemini_key = (request.headers.get("X-Gemini-Api-Key") or "").strip() or None
    persona = (request.headers.get("X-Insight-Persona") or "").strip() or None
    suggestion = monthly_budget_suggestion(
        uid,
        ym,
        gemini_api_key=user_gemini_key,
        persona=persona,
    )
    logger.info("Budget suggestion served user=%s month=%s", uid, ym)
    return jsonify(suggestion)


@bp.get("/weekly-digest")
@bp.get("/weekly-summary")
@jwt_required()
def weekly_digest_insight():
    uid = int(get_jwt_identity())
    week = request.args.get("week")
    currency = request.args.get("currency")
    user_gemini_key = (request.headers.get("X-Gemini-Api-Key") or "").strip() or None
    persona = (request.headers.get("X-Insight-Persona") or "").strip() or None
    try:
        payload = generate_weekly_digest(
            uid=uid,
            week=week,
            currency=currency,
            gemini_api_key=user_gemini_key,
            persona=persona,
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    logger.info("Weekly digest insight served user=%s week=%s", uid, payload.get("week"))
    return jsonify(payload), 200
