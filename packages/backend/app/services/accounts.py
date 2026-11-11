from datetime import date
from sqlalchemy import extract, func
from ..extensions import db
from ..models import AccountTransfer, AccountType, Category, Expense, FinancialAccount, User

VALID_ACCOUNT_TYPES = {t.value for t in AccountType}

# Deterministic FX rates relative to USD for multi-currency normalization
FX_TO_USD = {
    "USD": 1.0,
    "INR": 0.012,
    "EUR": 1.08,
    "GBP": 1.27,
    "AED": 0.2723,
    "SGD": 0.74,
    "AUD": 0.65,
    "CAD": 0.73,
    "JPY": 0.0067,
}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    src = (from_currency or "INR").upper()
    dst = (to_currency or "INR").upper()
    if src == dst:
        return round(float(amount), 2)
    usd_val = float(amount) * FX_TO_USD.get(src, 1.0)
    dst_rate = FX_TO_USD.get(dst, 1.0)
    return round(usd_val / dst_rate, 2)


def compute_account_metrics(account: FinancialAccount, ym: str | None = None) -> dict:
    uid = account.user_id
    all_tx = (
        db.session.query(Expense)
        .filter(Expense.user_id == uid, Expense.account_id == account.id)
        .all()
    )
    total_income = sum(float(e.amount) for e in all_tx if e.expense_type == "INCOME")
    total_expenses = sum(float(e.amount) for e in all_tx if e.expense_type != "INCOME")

    transfers_in = (
        db.session.query(func.coalesce(func.sum(AccountTransfer.amount), 0))
        .filter(
            AccountTransfer.user_id == uid,
            AccountTransfer.to_account_id == account.id,
        )
        .scalar()
    )
    transfers_out = (
        db.session.query(func.coalesce(func.sum(AccountTransfer.amount), 0))
        .filter(
            AccountTransfer.user_id == uid,
            AccountTransfer.from_account_id == account.id,
        )
        .scalar()
    )

    init_bal = float(account.initial_balance or 0)
    current_balance = round(
        init_bal + total_income - total_expenses + float(transfers_in or 0) - float(transfers_out or 0),
        2,
    )

    monthly_income = 0.0
    monthly_expenses = 0.0
    if ym and len(ym) == 7 and "-" in ym:
        year, month = map(int, ym.split("-"))
        for e in all_tx:
            if e.spent_at and e.spent_at.year == year and e.spent_at.month == month:
                if e.expense_type == "INCOME":
                    monthly_income += float(e.amount)
                else:
                    monthly_expenses += float(e.amount)

    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "institution": account.institution,
        "currency": account.currency,
        "initial_balance": round(init_bal, 2),
        "current_balance": current_balance,
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "transfers_in": round(float(transfers_in or 0), 2),
        "transfers_out": round(float(transfers_out or 0), 2),
        "monthly_income": round(monthly_income, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "monthly_net_flow": round(monthly_income - monthly_expenses, 2),
        "transaction_count": len(all_tx),
        "is_archived": account.is_archived,
    }


def build_multi_account_overview(
    uid: int,
    *,
    ym: str | None = None,
    account_id: int | None = None,
    include_archived: bool = False,
) -> dict:
    target_ym = (ym or date.today().strftime("%Y-%m")).strip()
    user = db.session.get(User, uid)
    base_currency = (user.preferred_currency if user and user.preferred_currency else "INR").upper()

    q = db.session.query(FinancialAccount).filter(FinancialAccount.user_id == uid)
    if not include_archived:
        q = q.filter(FinancialAccount.is_archived.is_(False))
    accounts = q.order_by(FinancialAccount.id.asc()).all()

    account_summaries = []
    total_assets_base = 0.0
    total_liabilities_base = 0.0
    consolidated_monthly_income = 0.0
    consolidated_monthly_expenses = 0.0

    for acc in accounts:
        if account_id is not None and acc.id != account_id:
            continue
        m = compute_account_metrics(acc, ym=target_ym)
        bal_in_base = convert_currency(m["current_balance"], acc.currency, base_currency)
        m["balance_in_base_currency"] = bal_in_base
        m["base_currency"] = base_currency

        if acc.account_type == AccountType.CREDIT_CARD.value and bal_in_base < 0:
            total_liabilities_base += abs(bal_in_base)
        elif bal_in_base < 0:
            total_liabilities_base += abs(bal_in_base)
        else:
            total_assets_base += bal_in_base

        consolidated_monthly_income += convert_currency(
            m["monthly_income"], acc.currency, base_currency
        )
        consolidated_monthly_expenses += convert_currency(
            m["monthly_expenses"], acc.currency, base_currency
        )
        account_summaries.append(m)

    # Also include unassigned transactions when no specific account filter is set
    unassigned_tx = (
        db.session.query(Expense)
        .filter(Expense.user_id == uid, Expense.account_id.is_(None))
        .all()
    )
    unassigned_net = sum(
        float(e.amount) if e.expense_type == "INCOME" else -float(e.amount)
        for e in unassigned_tx
    )

    net_worth_base = round(total_assets_base - total_liabilities_base, 2)
    positive_sum = sum(
        max(a["balance_in_base_currency"], 0.0) for a in account_summaries
    )
    for a in account_summaries:
        pos = max(a["balance_in_base_currency"], 0.0)
        a["share_pct"] = round((pos / positive_sum) * 100.0, 2) if positive_sum > 0 else 0.0

    # Recent transactions across selected accounts
    tx_query = db.session.query(Expense).filter(Expense.user_id == uid)
    if account_id is not None:
        tx_query = tx_query.filter(Expense.account_id == account_id)
    recent_rows = tx_query.order_by(Expense.spent_at.desc(), Expense.id.desc()).limit(15).all()

    account_map = {a.id: a.name for a in accounts}
    recent_transactions = [
        {
            "id": e.id,
            "account_id": e.account_id,
            "account_name": account_map.get(e.account_id, "Unassigned"),
            "description": e.notes or "Transaction",
            "amount": float(e.amount),
            "currency": e.currency,
            "type": e.expense_type,
            "category_id": e.category_id,
            "date": e.spent_at.isoformat(),
        }
        for e in recent_rows
    ]

    return {
        "period": {"month": target_ym},
        "base_currency": base_currency,
        "consolidated": {
            "account_count": len(account_summaries),
            "total_assets": round(total_assets_base, 2),
            "total_liabilities": round(total_liabilities_base, 2),
            "net_worth": net_worth_base,
            "monthly_income": round(consolidated_monthly_income, 2),
            "monthly_expenses": round(consolidated_monthly_expenses, 2),
            "monthly_net_flow": round(
                consolidated_monthly_income - consolidated_monthly_expenses, 2
            ),
            "unassigned_net_flow": round(unassigned_net, 2),
        },
        "accounts": account_summaries,
        "recent_transactions": recent_transactions,
    }
