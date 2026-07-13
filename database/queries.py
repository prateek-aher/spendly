"""Pure DB query helpers for the profile page. No Flask imports."""

from datetime import date, datetime, timedelta
from math import ceil

from database.db import get_db

VALID_RANGES = {"all", "7d", "30d", "this_month", "last_month", "custom"}

FILTER_PRESETS = [
    ("all", "All time"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("this_month", "This month"),
    ("last_month", "Last month"),
    ("custom", "Custom"),
]


def normalize_range(range_value):
    """Return range_value if it's a recognized preset, else 'all'."""
    return range_value if range_value in VALID_RANGES else "all"


def _user_date_filter(user_id, start_date, end_date):
    """Return (where_clause, params) filtering by user_id and, if both dates
    are given, an inclusive date range."""
    where_clause = "WHERE user_id = ?"
    params = [user_id]
    if start_date is not None and end_date is not None:
        where_clause += " AND date BETWEEN ? AND ?"
        params += [start_date, end_date]
    return where_clause, params


def paginate(total_count, page_param, per_page):
    """Resolve a page query param into a pagination state dict, clamped to
    valid bounds. Never raises."""
    try:
        page = int(page_param)
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    total_pages = max(1, ceil(total_count / per_page))
    page = min(page, total_pages)

    return {
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "offset": (page - 1) * per_page,
    }


def parse_iso_date(value):
    """Return a date object if value is a real 'YYYY-MM-DD' date, else None."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def resolve_date_range(range_value, start_value=None, end_value=None, today=None):
    """Resolve filter query params into a concrete (start_date, end_date) pair
    of 'YYYY-MM-DD' strings, or (None, None) for all-time / any invalid input.
    Never raises."""
    today = today or date.today()
    range_value = normalize_range(range_value)

    if range_value == "all":
        return None, None

    if range_value == "7d":
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()

    if range_value == "30d":
        start = today - timedelta(days=29)
        return start.isoformat(), today.isoformat()

    if range_value == "this_month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()

    if range_value == "last_month":
        last_day_prev_month = today.replace(day=1) - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        return first_day_prev_month.isoformat(), last_day_prev_month.isoformat()

    start = parse_iso_date(start_value)
    end = parse_iso_date(end_value)
    if start is None or end is None or start > end:
        return None, None
    return start.isoformat(), end.isoformat()


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    created = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    return {
        "id": user_id,
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
    }


def get_summary_stats(user_id, start_date=None, end_date=None):
    conn = get_db()
    where_clause, params = _user_date_filter(user_id, start_date, end_date)

    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0) AS total_spent,
               COUNT(*) AS transaction_count
        FROM expenses
        {where_clause}
        """,
        params,
    ).fetchone()

    top_category_row = conn.execute(
        f"""
        SELECT category
        FROM expenses
        {where_clause}
        GROUP BY category
        ORDER BY SUM(amount) DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    conn.close()

    if row["transaction_count"] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": round(row["total_spent"], 2),
        "transaction_count": row["transaction_count"],
        "top_category": top_category_row["category"],
    }


def get_recent_transactions(user_id, limit=10, start_date=None, end_date=None, offset=0):
    conn = get_db()
    where_clause, params = _user_date_filter(user_id, start_date, end_date)
    params += [limit, offset]

    rows = conn.execute(
        f"""
        SELECT date, description, category, amount
        FROM expenses
        {where_clause}
        ORDER BY date DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    conn.close()

    transactions = []
    for row in rows:
        formatted_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %d, %Y")
        transactions.append(
            {
                "date": formatted_date,
                "description": row["description"],
                "category": row["category"],
                "amount": round(float(row["amount"]), 2),
            }
        )
    return transactions


def get_category_breakdown(user_id, start_date=None, end_date=None):
    conn = get_db()
    where_clause, params = _user_date_filter(user_id, start_date, end_date)

    rows = conn.execute(
        f"""
        SELECT category, SUM(amount) AS total
        FROM expenses
        {where_clause}
        GROUP BY category
        ORDER BY total DESC
        """,
        params,
    ).fetchall()

    if not rows:
        conn.close()
        return []

    grand_total = sum(row["total"] for row in rows)

    breakdown = []
    for row in rows:
        category_total = row["total"]
        pct = round(category_total / grand_total * 100) if grand_total else 0
        breakdown.append({
            "name": row["category"],
            "amount": round(category_total, 2),
            "pct": pct,
        })

    remainder = 100 - sum(item["pct"] for item in breakdown)
    breakdown[0]["pct"] += remainder

    conn.close()
    return breakdown
