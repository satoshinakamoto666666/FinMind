from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import AccountTransfer, FinancialAccount
from ..services.accounts import (
    VALID_ACCOUNT_TYPES,
    build_multi_account_overview,
    compute_account_metrics,
)

bp = Blueprint("accounts", __name__)


@bp.post("")
@jwt_required()
def create_account():
    uid = int(get_jwt_identity())
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    acc_type = (data.get("account_type") or "CHECKING").upper().strip()
    if acc_type not in VALID_ACCOUNT_TYPES:
        return jsonify(error=f"invalid account_type, expected one of {sorted(VALID_ACCOUNT_TYPES)}"), 400
    try:
        initial_balance = float(data.get("initial_balance", 0.0))
    except (TypeError, ValueError):
        return jsonify(error="initial_balance must be numeric"), 400

    acc = FinancialAccount(
        user_id=uid,
        name=name,
        account_type=acc_type,
        institution=(data.get("institution") or "").strip() or None,
        currency=(data.get("currency") or "INR").upper().strip(),
        initial_balance=initial_balance,
    )
    db.session.add(acc)
    db.session.commit()
    return jsonify(compute_account_metrics(acc)), 201


@bp.get("")
@jwt_required()
def list_accounts():
    uid = int(get_jwt_identity())
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    ym = request.args.get("month")
    q = db.session.query(FinancialAccount).filter(FinancialAccount.user_id == uid)
    if not include_archived:
        q = q.filter(FinancialAccount.is_archived.is_(False))
    items = q.order_by(FinancialAccount.id.asc()).all()
    return jsonify([compute_account_metrics(a, ym=ym) for a in items])


@bp.get("/overview")
@jwt_required()
def accounts_overview():
    uid = int(get_jwt_identity())
    ym = request.args.get("month")
    acc_id_raw = request.args.get("account_id")
    account_id = int(acc_id_raw) if acc_id_raw and acc_id_raw.isdigit() else None
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    return jsonify(
        build_multi_account_overview(
            uid,
            ym=ym,
            account_id=account_id,
            include_archived=include_archived,
        )
    )


@bp.get("/<int:account_id>")
@jwt_required()
def get_account(account_id: int):
    uid = int(get_jwt_identity())
    acc = db.session.get(FinancialAccount, account_id)
    if not acc or acc.user_id != uid:
        return jsonify(error="not found"), 404
    return jsonify(compute_account_metrics(acc, ym=request.args.get("month")))


@bp.patch("/<int:account_id>")
@jwt_required()
def update_account(account_id: int):
    uid = int(get_jwt_identity())
    acc = db.session.get(FinancialAccount, account_id)
    if not acc or acc.user_id != uid:
        return jsonify(error="not found"), 404
    data = request.get_json() or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="name cannot be empty"), 400
        acc.name = name
    if "account_type" in data:
        acc_type = (data.get("account_type") or "").upper().strip()
        if acc_type not in VALID_ACCOUNT_TYPES:
            return jsonify(error="invalid account_type"), 400
        acc.account_type = acc_type
    if "institution" in data:
        acc.institution = (data.get("institution") or "").strip() or None
    if "initial_balance" in data:
        acc.initial_balance = float(data["initial_balance"])
    if "is_archived" in data:
        acc.is_archived = bool(data["is_archived"])
    db.session.commit()
    return jsonify(compute_account_metrics(acc))


@bp.delete("/<int:account_id>")
@jwt_required()
def delete_account(account_id: int):
    uid = int(get_jwt_identity())
    acc = db.session.get(FinancialAccount, account_id)
    if not acc or acc.user_id != uid:
        return jsonify(error="not found"), 404
    acc.is_archived = True
    db.session.commit()
    return jsonify(message="archived", id=acc.id), 200


@bp.post("/transfers")
@jwt_required()
def create_transfer():
    uid = int(get_jwt_identity())
    data = request.get_json() or {}
    from_id = data.get("from_account_id")
    to_id = data.get("to_account_id")
    if not from_id or not to_id or int(from_id) == int(to_id):
        return jsonify(error="distinct from_account_id and to_account_id are required"), 400
    from_acc = db.session.get(FinancialAccount, int(from_id))
    to_acc = db.session.get(FinancialAccount, int(to_id))
    if not from_acc or from_acc.user_id != uid or not to_acc or to_acc.user_id != uid:
        return jsonify(error="account not found"), 404
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify(error="amount must be numeric"), 400
    if amount <= 0:
        return jsonify(error="amount must be positive"), 400

    transferred_at = (
        date.fromisoformat(data["transferred_at"])
        if data.get("transferred_at")
        else date.today()
    )
    transfer = AccountTransfer(
        user_id=uid,
        from_account_id=from_acc.id,
        to_account_id=to_acc.id,
        amount=amount,
        currency=from_acc.currency,
        notes=data.get("notes"),
        transferred_at=transferred_at,
    )
    db.session.add(transfer)
    db.session.commit()
    return jsonify(
        id=transfer.id,
        from_account_id=from_acc.id,
        to_account_id=to_acc.id,
        amount=float(transfer.amount),
        transferred_at=transfer.transferred_at.isoformat(),
    ), 201
