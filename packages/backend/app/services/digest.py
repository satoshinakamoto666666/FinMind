from datetime import date, datetime, timedelta
import json
import re
from urllib import request as url_request

from ..config import Settings
from ..extensions import db
from ..models import Bill, Category, Expense, Reminder, User
from .cache import cache_get, cache_set, weekly_digest_key

_settings = Settings()
WEEK_PATTERN = re.compile(r"^(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])$")
DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DIGEST_CACHE_TTL_SECONDS = 600


def parse_iso_week(week_str: str | None = None) -> tuple[str, date, date]:
    """Parse YYYY-WNN string (or default to today's ISO week) into (week_label, monday, sunday)."""
    if not week_str or not week_str.strip():
        today = date.today()
        iso_year, iso_week, _ = today.isocalendar()
        week_label = f"{iso_year:04d}-W{iso_week:02d}"
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        sunday = monday + timedelta(days=6)
        return week_label, monday, sunday

    cleaned = week_str.strip().upper()
    m = WEEK_PATTERN.match(cleaned)
    if not m:
        raise ValueError("Invalid week format. Expected YYYY-WNN (e.g. 2026-W10).")
    year = int(m.group(1))
    week_num = int(m.group(2))
    try:
        monday = date.fromisocalendar(year, week_num, 1)
    except ValueError as exc:
        raise ValueError("Invalid ISO week number for the given year.") from exc
    sunday = monday + timedelta(days=6)
    return f"{year:04d}-W{week_num:02d}", monday, sunday


def _resolve_currency(uid: int, explicit_currency: str | None = None) -> str:
    if explicit_currency and explicit_currency.strip():
        return explicit_currency.strip().upper()
    user = db.session.get(User, uid)
    if user and user.preferred_currency:
        return user.preferred_currency.upper()
    return "INR"


def _query_week_transactions(
    uid: int, start_date: date, end_date: date, currency: str
) -> list[Expense]:
    return (
        db.session.query(Expense)
        .filter(
            Expense.user_id == uid,
            Expense.spent_at >= start_date,
            Expense.spent_at <= end_date,
            Expense.currency == currency,
        )
        .order_by(Expense.spent_at.asc(), Expense.id.asc())
        .all()
    )


def _category_map(uid: int) -> dict[int, str]:
    rows = db.session.query(Category).filter(Category.user_id == uid).all()
    return {c.id: c.name for c in rows}


def _compute_trend(curr: float, prev: float) -> tuple[str, float | None]:
    if prev == 0.0 and curr > 0.0:
        return "NEW", None
    if prev > 0.0 and curr == 0.0:
        return "GONE", -100.0
    if prev == 0.0 and curr == 0.0:
        return "FLAT", 0.0
    pct = round(((curr - prev) / prev) * 100.0, 2)
    if abs(pct) < 1.0:
        return "FLAT", pct
    return ("UP" if pct > 0 else "DOWN"), pct


def _build_heuristic_insights(
    total_spent: float,
    total_income: float,
    wow_change_pct: float | None,
    category_breakdown: list[dict],
    upcoming_bills: list[dict],
    currency: str,
) -> list[str]:
    insights: list[str] = []
    if total_spent == 0.0 and total_income == 0.0:
        insights.append(
            "No transactions recorded for this week yet. Log expenses to unlock weekly trend insights."
        )
    else:
        if wow_change_pct is not None:
            if wow_change_pct > 15.0:
                insights.append(
                    f"Weekly spending increased by {wow_change_pct:.1f}% compared to last week."
                )
            elif wow_change_pct < -10.0:
                insights.append(
                    f"Great job! Weekly spending dropped by {abs(wow_change_pct):.1f}% compared to last week."
                )
            else:
                insights.append(
                    f"Weekly spending remained steady ({wow_change_pct:+.1f}% vs. previous week)."
                )

        active_cats = [c for c in category_breakdown if c["amount"] > 0]
        if active_cats:
            top = active_cats[0]
            insights.append(
                f"{top['category_name']} was your top spending category at {top['amount']:.2f} {currency} ({top['percentage']:.1f}% of weekly spend)."
            )

        spikes = [
            c
            for c in active_cats
            if c["trend"] == "UP" and (c["change_pct"] or 0) >= 25.0
        ]
        if spikes:
            biggest = max(spikes, key=lambda x: x["change_amount"])
            insights.append(
                f"Watch out: {biggest['category_name']} rose by {biggest['change_pct']:.1f}% (+{biggest['change_amount']:.2f} {currency}) week-over-week."
            )

        if total_income > 0:
            savings_rate = round(
                ((total_income - total_spent) / total_income) * 100.0, 1
            )
            insights.append(
                f"Weekly net cash flow is {(total_income - total_spent):+.2f} {currency} ({savings_rate:.1f}% net margin)."
            )

    if upcoming_bills:
        bills_total = round(sum(b["amount"] for b in upcoming_bills), 2)
        insights.append(
            f"You have {len(upcoming_bills)} upcoming bill(s) totaling {bills_total:.2f} {currency} due in the next 7 days."
        )

    return insights[:5]


def _gemini_weekly_insights(
    summary_context: dict, api_key: str, model: str, persona: str
) -> list[str]:
    prompt = (
        f"{persona}\n"
        "Analyze this user's weekly financial summary and return strict JSON with key "
        '"insights" containing a list of 3 concise, actionable bullet strings.\n'
        f"summary={json.dumps(summary_context)}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
    ).encode("utf-8")
    req = url_request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with url_request.urlopen(req, timeout=10) as resp:  # nosec B310
        payload = json.loads(resp.read().decode("utf-8"))
    text = (
        payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    ).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini did not return a JSON object")
    parsed = json.loads(text[start : end + 1])
    items = parsed.get("insights")
    if not isinstance(items, list) or not items:
        raise ValueError("Invalid insights list from Gemini")
    return [str(i) for i in items[:5]]


def generate_weekly_digest(
    uid: int,
    week: str | None = None,
    currency: str | None = None,
    gemini_api_key: str | None = None,
    persona: str | None = None,
    use_cache: bool = True,
) -> dict:
    week_label, week_start, week_end = parse_iso_week(week)
    resolved_currency = _resolve_currency(uid, currency)
    cache_key = weekly_digest_key(uid, week_label, resolved_currency)

    if use_cache and not gemini_api_key:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_end - timedelta(days=7)
    prev_iso_year, prev_iso_week, _ = prev_week_start.isocalendar()
    prev_week_label = f"{prev_iso_year:04d}-W{prev_iso_week:02d}"

    curr_txs = _query_week_transactions(uid, week_start, week_end, resolved_currency)
    prev_txs = _query_week_transactions(
        uid, prev_week_start, prev_week_end, resolved_currency
    )
    cat_names = _category_map(uid)

    curr_expenses = [t for t in curr_txs if (t.expense_type or "EXPENSE").upper() != "INCOME"]
    curr_incomes = [t for t in curr_txs if (t.expense_type or "EXPENSE").upper() == "INCOME"]
    prev_expenses = [t for t in prev_txs if (t.expense_type or "EXPENSE").upper() != "INCOME"]

    total_spent = round(sum(float(t.amount) for t in curr_expenses), 2)
    total_income = round(sum(float(t.amount) for t in curr_incomes), 2)
    net_flow = round(total_income - total_spent, 2)
    previous_week_spent = round(sum(float(t.amount) for t in prev_expenses), 2)
    wow_change = round(total_spent - previous_week_spent, 2)
    overall_trend, wow_change_pct = _compute_trend(total_spent, previous_week_spent)

    # Category aggregation across both weeks
    curr_by_cat: dict[int | None, float] = {}
    for t in curr_expenses:
        curr_by_cat[t.category_id] = curr_by_cat.get(t.category_id, 0.0) + float(t.amount)

    prev_by_cat: dict[int | None, float] = {}
    for t in prev_expenses:
        prev_by_cat[t.category_id] = prev_by_cat.get(t.category_id, 0.0) + float(t.amount)

    all_cat_ids = set(curr_by_cat.keys()) | set(prev_by_cat.keys())
    category_breakdown: list[dict] = []
    for cid in all_cat_ids:
        c_amt = round(curr_by_cat.get(cid, 0.0), 2)
        p_amt = round(prev_by_cat.get(cid, 0.0), 2)
        delta = round(c_amt - p_amt, 2)
        trend_dir, change_pct = _compute_trend(c_amt, p_amt)
        pct_share = round((c_amt / total_spent) * 100.0, 2) if total_spent > 0 else 0.0
        category_breakdown.append(
            {
                "category_id": cid,
                "category_name": cat_names.get(cid, "Uncategorized") if cid else "Uncategorized",
                "amount": c_amt,
                "previous_amount": p_amt,
                "change_amount": delta,
                "change_pct": change_pct,
                "percentage": pct_share,
                "trend": trend_dir,
            }
        )
    category_breakdown.sort(key=lambda x: (-x["amount"], -x["previous_amount"], str(x["category_name"])))

    # 7-day daily breakdown (Monday..Sunday)
    daily_breakdown: list[dict] = []
    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        day_exp = sum(
            float(t.amount) for t in curr_expenses if t.spent_at == day_date
        )
        day_inc = sum(
            float(t.amount) for t in curr_incomes if t.spent_at == day_date
        )
        day_cnt = sum(1 for t in curr_txs if t.spent_at == day_date)
        daily_breakdown.append(
            {
                "date": day_date.isoformat(),
                "day_name": DAY_NAMES[offset],
                "spent": round(day_exp, 2),
                "income": round(day_inc, 2),
                "transaction_count": day_cnt,
            }
        )

    # Upcoming bills in the next 7 days from week_end (or today if current week)
    anchor_date = min(date.today(), week_end)
    upcoming_window_end = week_end + timedelta(days=7)
    bills_rows = (
        db.session.query(Bill)
        .filter(
            Bill.user_id == uid,
            Bill.active.is_(True),
            Bill.currency == resolved_currency,
            Bill.next_due_date >= anchor_date,
            Bill.next_due_date <= upcoming_window_end,
        )
        .order_by(Bill.next_due_date.asc())
        .all()
    )
    upcoming_bills = [
        {
            "id": b.id,
            "name": b.name,
            "amount": round(float(b.amount), 2),
            "currency": b.currency,
            "next_due_date": b.next_due_date.isoformat(),
            "autopay_enabled": b.autopay_enabled,
        }
        for b in bills_rows
    ]

    # Structured trends summary
    active_cats = [c for c in category_breakdown if c["amount"] > 0]
    top_category = active_cats[0] if active_cats else None
    increases = [c for c in category_breakdown if c["change_amount"] > 0]
    decreases = [c for c in category_breakdown if c["change_amount"] < 0]
    biggest_increase = max(increases, key=lambda x: x["change_amount"]) if increases else None
    biggest_decrease = min(decreases, key=lambda x: x["change_amount"]) if decreases else None
    peak_day = max(daily_breakdown, key=lambda x: x["spent"]) if total_spent > 0 else None

    trends = {
        "overall_direction": overall_trend,
        "top_category": (
            {
                "category_name": top_category["category_name"],
                "amount": top_category["amount"],
                "percentage": top_category["percentage"],
            }
            if top_category
            else None
        ),
        "biggest_increase": (
            {
                "category_name": biggest_increase["category_name"],
                "change_amount": biggest_increase["change_amount"],
                "change_pct": biggest_increase["change_pct"],
            }
            if biggest_increase
            else None
        ),
        "biggest_decrease": (
            {
                "category_name": biggest_decrease["category_name"],
                "change_amount": biggest_decrease["change_amount"],
                "change_pct": biggest_decrease["change_pct"],
            }
            if biggest_decrease
            else None
        ),
        "highest_spend_day": (
            {
                "date": peak_day["date"],
                "day_name": peak_day["day_name"],
                "spent": peak_day["spent"],
            }
            if peak_day and peak_day["spent"] > 0
            else None
        ),
    }

    insights = _build_heuristic_insights(
        total_spent=total_spent,
        total_income=total_income,
        wow_change_pct=wow_change_pct,
        category_breakdown=category_breakdown,
        upcoming_bills=upcoming_bills,
        currency=resolved_currency,
    )
    method = "heuristic"
    warnings: list[str] = []

    key = (gemini_api_key or "").strip() or (_settings.gemini_api_key or "")
    if key:
        try:
            insights = _gemini_weekly_insights(
                summary_context={
                    "week": week_label,
                    "currency": resolved_currency,
                    "total_spent": total_spent,
                    "previous_week_spent": previous_week_spent,
                    "wow_change_pct": wow_change_pct,
                    "top_categories": category_breakdown[:3],
                },
                api_key=key,
                model=_settings.gemini_model,
                persona=(persona or "You are FinMind's financial coach.").strip(),
            )
            method = "gemini"
        except Exception:
            warnings.append("gemini_unavailable")

    payload = {
        "week": week_label,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "previous_week": prev_week_label,
        "currency": resolved_currency,
        "total_spent": total_spent,
        "total_income": total_income,
        "net_flow": net_flow,
        "daily_average": round(total_spent / 7.0, 2),
        "transaction_count": len(curr_txs),
        "expense_count": len(curr_expenses),
        "previous_week_spent": previous_week_spent,
        "week_over_week_change": wow_change,
        "week_over_week_change_pct": wow_change_pct,
        "category_breakdown": category_breakdown,
        "daily_breakdown": daily_breakdown,
        "upcoming_bills": upcoming_bills,
        "trends": trends,
        "insights": insights,
        "method": method,
    }
    if warnings:
        payload["warnings"] = warnings

    if use_cache and method == "heuristic":
        cache_set(cache_key, payload, ttl_seconds=DIGEST_CACHE_TTL_SECONDS)
    return payload


def send_weekly_digest_notification(
    uid: int, week: str | None = None, channel: str = "email", currency: str | None = None
) -> dict:
    digest = generate_weekly_digest(uid=uid, week=week, currency=currency, use_cache=False)
    channel_norm = (channel or "email").strip().lower()
    if channel_norm not in {"email", "whatsapp"}:
        raise ValueError("Invalid notification channel. Expected 'email' or 'whatsapp'.")

    top_cat = (
        digest["trends"]["top_category"]["category_name"]
        if digest["trends"]["top_category"]
        else "None"
    )
    msg = (
        f"[FinMind Weekly Digest {digest['week']}] Total Spent: "
        f"{digest['total_spent']:.2f} {digest['currency']} "
        f"(Top category: {top_cat}). "
        f"{digest['insights'][0] if digest['insights'] else ''}"
    )[:500]

    reminder = Reminder(
        user_id=uid,
        bill_id=None,
        message=msg,
        send_at=datetime.utcnow(),
        sent=True,
        channel=channel_norm,
    )
    db.session.add(reminder)
    db.session.commit()
    return {
        "reminder_id": reminder.id,
        "channel": channel_norm,
        "week": digest["week"],
        "message": msg,
        "status": "sent",
    }
