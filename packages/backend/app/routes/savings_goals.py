from datetime import date, datetime
from decimal import Decimal
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from ..extensions import db
from ..models import (
    SavingsContribution,
    SavingsGoal,
    SavingsGoalStatus,
    SavingsMilestone,
    User,
)
from ..services.cache import cache_delete_patterns

bp = Blueprint("savings_goals", __name__)
logger = logging.getLogger("finmind.savings_goals")

DEFAULT_MILESTONE_PERCENTAGES = (25, 50, 75, 100)


def _serialize_milestone(m: SavingsMilestone) -> dict:
    return {
        "id": m.id,
        "goal_id": m.goal_id,
        "title": m.title,
        "target_amount": float(m.target_amount),
        "percentage": m.percentage,
        "reached": bool(m.reached),
        "reached_at": m.reached_at.isoformat() if m.reached_at else None,
    }


def _serialize_contribution(c: SavingsContribution) -> dict:
    return {
        "id": c.id,
        "goal_id": c.goal_id,
        "amount": float(c.amount),
        "notes": c.notes,
        "contributed_at": c.contributed_at.isoformat(),
    }


def _serialize_goal(goal: SavingsGoal, include_history: bool = False) -> dict:
    target = float(goal.target_amount)
    current = float(goal.current_amount)
    progress_pct = round(min(100.0, (current / target) * 100.0), 2) if target > 0 else 0.0
    remaining = round(max(0.0, target - current), 2)

    milestones = (
        db.session.query(SavingsMilestone)
        .filter_by(goal_id=goal.id, user_id=goal.user_id)
        .order_by(SavingsMilestone.target_amount.asc())
        .all()
    )

    payload = {
        "id": goal.id,
        "name": goal.name,
        "target_amount": target,
        "current_amount": current,
        "remaining_amount": remaining,
        "progress_percentage": progress_pct,
        "currency": goal.currency,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "category": goal.category,
        "notes": goal.notes,
        "status": goal.status,
        "milestones": [_serialize_milestone(m) for m in milestones],
        "created_at": goal.created_at.isoformat(),
    }

    if include_history:
        contributions = (
            db.session.query(SavingsContribution)
            .filter_by(goal_id=goal.id, user_id=goal.user_id)
            .order_by(SavingsContribution.contributed_at.desc(), SavingsContribution.id.desc())
            .all()
        )
        payload["contributions"] = [_serialize_contribution(c) for c in contributions]

    return payload


def _evaluate_milestones(goal: SavingsGoal) -> list[dict]:
    now = datetime.utcnow()
    current_dec = Decimal(str(goal.current_amount))
    target_dec = Decimal(str(goal.target_amount))

    milestones = (
        db.session.query(SavingsMilestone)
        .filter_by(goal_id=goal.id, user_id=goal.user_id)
        .order_by(SavingsMilestone.target_amount.asc())
        .all()
    )

    newly_unlocked = []
    for m in milestones:
        if not m.reached and current_dec >= Decimal(str(m.target_amount)):
            m.reached = True
            m.reached_at = now
            newly_unlocked.append(_serialize_milestone(m))

    if target_dec > 0 and current_dec >= target_dec:
        goal.status = SavingsGoalStatus.COMPLETED.value

    return newly_unlocked


@bp.get("")
@jwt_required()
def list_savings_goals():
    uid = int(get_jwt_identity())
    status_filter = request.args.get("status")
    query = db.session.query(SavingsGoal).filter_by(user_id=uid)
    if status_filter:
        query = query.filter_by(status=status_filter.upper())
    goals = query.order_by(SavingsGoal.created_at.desc(), SavingsGoal.id.desc()).all()
    return jsonify([_serialize_goal(g) for g in goals])


@bp.post("")
@jwt_required()
def create_savings_goal():
    uid = int(get_jwt_identity())
    user = db.session.get(User, uid)
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400

    try:
        target_amount = Decimal(str(data["target_amount"]))
    except (KeyError, ValueError, Exception):
        return jsonify(error="valid positive target_amount is required"), 400

    if target_amount <= 0:
        return jsonify(error="target_amount must be greater than 0"), 400

    initial_amount = Decimal(str(data.get("current_amount", 0) or 0))
    if initial_amount < 0:
        return jsonify(error="current_amount cannot be negative"), 400

    target_date_val = (
        date.fromisoformat(data["target_date"]) if data.get("target_date") else None
    )

    goal = SavingsGoal(
        user_id=uid,
        name=name,
        target_amount=target_amount,
        current_amount=initial_amount,
        currency=data.get("currency") or (user.preferred_currency if user else "INR"),
        target_date=target_date_val,
        category=data.get("category"),
        notes=data.get("notes"),
        status=(
            SavingsGoalStatus.COMPLETED.value
            if initial_amount >= target_amount
            else SavingsGoalStatus.ACTIVE.value
        ),
    )
    db.session.add(goal)
    db.session.flush()

    custom_milestones = data.get("milestones")
    if isinstance(custom_milestones, list) and len(custom_milestones) > 0:
        for item in custom_milestones:
            m_target = Decimal(str(item["target_amount"]))
            pct = int(round((float(m_target) / float(target_amount)) * 100))
            db.session.add(
                SavingsMilestone(
                    goal_id=goal.id,
                    user_id=uid,
                    title=item.get("title") or f"{pct}% Milestone",
                    target_amount=m_target,
                    percentage=item.get("percentage", pct),
                )
            )
    elif data.get("auto_milestones", True):
        for pct in DEFAULT_MILESTONE_PERCENTAGES:
            m_target = (target_amount * Decimal(pct) / Decimal(100)).quantize(
                Decimal("0.01")
            )
            db.session.add(
                SavingsMilestone(
                    goal_id=goal.id,
                    user_id=uid,
                    title=f"{pct}% of {name}",
                    target_amount=m_target,
                    percentage=pct,
                )
            )

    db.session.flush()
    _evaluate_milestones(goal)
    db.session.commit()
    cache_delete_patterns([f"user:{uid}:dashboard_summary:*"])
    logger.info("Created savings goal id=%s user=%s name=%s", goal.id, uid, goal.name)
    return jsonify(_serialize_goal(goal, include_history=True)), 201


@bp.get("/<int:goal_id>")
@jwt_required()
def get_savings_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404
    return jsonify(_serialize_goal(goal, include_history=True))


@bp.patch("/<int:goal_id>")
@jwt_required()
def update_savings_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404

    data = request.get_json() or {}
    if "name" in data and str(data["name"]).strip():
        goal.name = str(data["name"]).strip()
    if "target_amount" in data:
        new_target = Decimal(str(data["target_amount"]))
        if new_target <= 0:
            return jsonify(error="target_amount must be greater than 0"), 400
        goal.target_amount = new_target
    if "target_date" in data:
        goal.target_date = (
            date.fromisoformat(data["target_date"]) if data["target_date"] else None
        )
    if "category" in data:
        goal.category = data["category"]
    if "notes" in data:
        goal.notes = data["notes"]
    if "status" in data and data["status"]:
        goal.status = str(data["status"]).upper()

    _evaluate_milestones(goal)
    db.session.commit()
    return jsonify(_serialize_goal(goal, include_history=True))


@bp.delete("/<int:goal_id>")
@jwt_required()
def delete_savings_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404

    db.session.query(SavingsMilestone).filter_by(
        goal_id=goal.id, user_id=uid
    ).delete()
    db.session.query(SavingsContribution).filter_by(
        goal_id=goal.id, user_id=uid
    ).delete()
    db.session.delete(goal)
    db.session.commit()
    return jsonify(message="deleted")


@bp.post("/<int:goal_id>/contribute")
@jwt_required()
def contribute_to_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404

    data = request.get_json() or {}
    try:
        amount = Decimal(str(data["amount"]))
    except (KeyError, ValueError, Exception):
        return jsonify(error="valid positive amount is required"), 400

    if amount <= 0:
        return jsonify(error="contribution amount must be greater than 0"), 400

    contributed_at = (
        date.fromisoformat(data["contributed_at"])
        if data.get("contributed_at")
        else date.today()
    )
    contribution = SavingsContribution(
        goal_id=goal.id,
        user_id=uid,
        amount=amount,
        notes=data.get("notes"),
        contributed_at=contributed_at,
    )
    db.session.add(contribution)

    goal.current_amount = Decimal(str(goal.current_amount)) + amount
    newly_unlocked = _evaluate_milestones(goal)
    db.session.commit()

    response = _serialize_goal(goal, include_history=True)
    response["newly_unlocked_milestones"] = newly_unlocked
    return jsonify(response), 200


@bp.post("/<int:goal_id>/milestones")
@jwt_required()
def add_milestone(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="title is required"), 400

    try:
        target_amount = Decimal(str(data["target_amount"]))
    except (KeyError, ValueError, Exception):
        return jsonify(error="valid target_amount is required"), 400

    if target_amount <= 0:
        return jsonify(error="target_amount must be greater than 0"), 400

    pct = int(round((float(target_amount) / float(goal.target_amount)) * 100))
    now = datetime.utcnow()
    reached = Decimal(str(goal.current_amount)) >= target_amount
    milestone = SavingsMilestone(
        goal_id=goal.id,
        user_id=uid,
        title=title,
        target_amount=target_amount,
        percentage=data.get("percentage", pct),
        reached=reached,
        reached_at=now if reached else None,
    )
    db.session.add(milestone)
    db.session.commit()
    return jsonify(_serialize_milestone(milestone)), 201
