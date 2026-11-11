import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from ..services.digest import generate_weekly_digest, send_weekly_digest_notification

bp = Blueprint("digest", __name__)
logger = logging.getLogger("finmind.digest")


@bp.get("/weekly")
@jwt_required()
def get_weekly_digest():
    uid = int(get_jwt_identity())
    week = request.args.get("week")
    currency = request.args.get("currency")
    gemini_key = (request.headers.get("X-Gemini-Api-Key") or "").strip() or None
    persona = (request.headers.get("X-Insight-Persona") or "").strip() or None
    try:
        payload = generate_weekly_digest(
            uid=uid,
            week=week,
            currency=currency,
            gemini_api_key=gemini_key,
            persona=persona,
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    logger.info("Weekly digest served user=%s week=%s", uid, payload.get("week"))
    return jsonify(payload), 200


@bp.post("/weekly/send")
@jwt_required()
def trigger_weekly_digest():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    week = data.get("week") or request.args.get("week")
    channel = data.get("channel") or "email"
    currency = data.get("currency") or request.args.get("currency")
    try:
        result = send_weekly_digest_notification(
            uid=uid, week=week, channel=channel, currency=currency
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    logger.info("Weekly digest notification sent user=%s week=%s", uid, result.get("week"))
    return jsonify(result), 201
