from database.db import get_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)


def _make_user(name="Test User", email="test@example.com"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, "hash"),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def _add_expense(user_id, amount, category, date, description="x"):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    conn.close()


# ---------- get_user_by_id ----------


def test_get_user_by_id_valid(test_db_path):
    uid = _make_user("Jane Doe", "jane@example.com")
    result = get_user_by_id(uid)
    assert result["name"] == "Jane Doe"
    assert result["email"] == "jane@example.com"
    assert "member_since" in result


def test_get_user_by_id_missing(test_db_path):
    assert get_user_by_id(999999) is None


# ---------- get_summary_stats ----------


def test_get_summary_stats_with_expenses(test_db_path):
    uid = _make_user()
    _add_expense(uid, 50.00, "Food", "2026-07-01")
    _add_expense(uid, 10.00, "Transport", "2026-07-02")
    stats = get_summary_stats(uid)
    assert stats["total_spent"] == 60.00
    assert stats["transaction_count"] == 2
    assert stats["top_category"] == "Food"


def test_get_summary_stats_no_expenses(test_db_path):
    uid = _make_user()
    stats = get_summary_stats(uid)
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


# ---------- get_recent_transactions ----------


def test_get_recent_transactions_ordering(test_db_path):
    uid = _make_user()
    _add_expense(uid, 5.00, "Food", "2026-07-01", "old")
    _add_expense(uid, 6.00, "Food", "2026-07-03", "newest")
    _add_expense(uid, 7.00, "Food", "2026-07-02", "middle")
    txs = get_recent_transactions(uid)
    assert [t["description"] for t in txs] == ["newest", "middle", "old"]
    assert set(txs[0].keys()) == {"id", "date", "description", "category", "amount"}


def test_get_recent_transactions_empty(test_db_path):
    uid = _make_user()
    assert get_recent_transactions(uid) == []


# ---------- get_category_breakdown ----------


def test_get_category_breakdown_with_expenses(test_db_path):
    uid = _make_user()
    _add_expense(uid, 75.00, "Food", "2026-07-01")
    _add_expense(uid, 25.00, "Transport", "2026-07-02")
    breakdown = get_category_breakdown(uid)
    assert [c["name"] for c in breakdown] == ["Food", "Transport"]
    assert sum(c["pct"] for c in breakdown) == 100
    assert all(isinstance(c["pct"], int) for c in breakdown)


def test_get_category_breakdown_empty(test_db_path):
    uid = _make_user()
    assert get_category_breakdown(uid) == []


# ---------- route tests ----------


def test_profile_redirects_when_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated_seed_user(client):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    expected_total_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt FROM expenses WHERE user_id = ?",
        (row["id"],),
    ).fetchone()
    conn.close()

    with client.session_transaction() as sess:
        sess["user_id"] = row["id"]

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Prateek" in body
    assert "prateek@spendly.com" in body
    assert "₹" in body
    assert "$" not in body
    assert f"{expected_total_row['total']:.2f}" in body
    assert str(expected_total_row["cnt"]) in body


def test_profile_shows_own_data_for_new_user(client):
    uid = _make_user("New Guy", "newguy@example.com")
    _add_expense(uid, 12.34, "Food", "2026-07-05", "Solo lunch")

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "New Guy" in body
    assert "Prateek" not in body
    assert "12.34" in body


def test_profile_zero_expenses_no_error(client):
    uid = _make_user("Empty Wallet", "empty@example.com")

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "0.00" in body
