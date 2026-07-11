"""
Tests for Step 4 — Profile Page (.claude/specs/04-profile-page.md).

Step 4's spec describes a *static* profile page: hardcoded user info,
summary stats, transaction history, and category breakdown, wired behind
a login-required `/profile` route. Step 5 (see
.claude/specs/05-backend-routes-for-profile-page.md) later swaps the
hardcoded context for real DB queries, and that step's own test file
(tests/test_backend_connection.py) already covers exact-value correctness
of those queries.

This file therefore focuses on what Step 4's "Definition of done" actually
promises structurally, regardless of whether the data behind it is
hardcoded (Step 4) or DB-backed (Step 5):
  - auth guard behaviour (redirect / 200)
  - presence of the four required sections (user info, summary stats,
    transaction history, category breakdown)
  - navbar reflecting logged-in state
  - no hardcoded hex colours in the template source

We deliberately do NOT assert on exact hardcoded strings/numbers, since the
app may already be past Step 4 and those values may be dynamic.
"""

import re

from database.db import get_db


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


def _login(client, user_id, user_name=None):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        if user_name is not None:
            sess["user_name"] = user_name


# ---------------------------------------------------------------------- #
# Auth guard
# ---------------------------------------------------------------------- #


def test_profile_redirects_to_login_when_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_returns_200_when_authenticated(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    assert resp.status_code == 200


# ---------------------------------------------------------------------- #
# User info card
# ---------------------------------------------------------------------- #


def test_profile_shows_user_info_card_with_name_and_email(client):
    uid = _make_user("Jamie Rivera", "jamie.rivera@example.com")
    _login(client, uid, "Jamie Rivera")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert "Jamie Rivera" in body
    assert "jamie.rivera@example.com" in body


# ---------------------------------------------------------------------- #
# Summary stats row (spec names: total spent, transaction count, top category)
# ---------------------------------------------------------------------- #


def test_profile_shows_at_least_three_summary_stats(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", "2026-07-01")
    _add_expense(uid, 30.00, "Transport", "2026-07-02")
    _add_expense(uid, 10.00, "Bills", "2026-07-03")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True).lower()

    # Assumption: the spec explicitly names these three stat concepts
    # ("total spent", "number of transactions", "top category"); we check
    # for their presence in the rendered text rather than exact wording,
    # since the spec doesn't mandate literal label text.
    assert "total" in body and "spent" in body
    assert "transaction" in body
    assert "top" in body and "categor" in body


# ---------------------------------------------------------------------- #
# Transaction history table
# ---------------------------------------------------------------------- #


def test_profile_transaction_table_has_at_least_three_rows(client):
    uid = _make_user()
    _add_expense(uid, 12.00, "Food", "2026-07-01", "Groceries run")
    _add_expense(uid, 8.50, "Transport", "2026-07-02", "Bus fare")
    _add_expense(uid, 45.00, "Bills", "2026-07-03", "Electricity bill")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert "Groceries run" in body
    assert "Bus fare" in body
    assert "Electricity bill" in body

    # Structural check: at least one header row + 3 data rows.
    row_count = len(re.findall(r"<tr\b", body))
    assert row_count >= 4


def test_profile_transaction_table_has_expected_columns(client):
    uid = _make_user()
    _add_expense(uid, 12.00, "Food", "2026-07-01", "Groceries run")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    # Column headers called for by the spec: date, description, category, amount.
    for column in ("Date", "Description", "Category", "Amount"):
        assert column in body


# ---------------------------------------------------------------------- #
# Category breakdown
# ---------------------------------------------------------------------- #


def test_profile_category_breakdown_shows_at_least_three_categories(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", "2026-07-01")
    _add_expense(uid, 30.00, "Transport", "2026-07-02")
    _add_expense(uid, 10.00, "Bills", "2026-07-03")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert "Food" in body
    assert "Transport" in body
    assert "Bills" in body


# ---------------------------------------------------------------------- #
# Navbar reflects logged-in state
# ---------------------------------------------------------------------- #


def test_navbar_shows_logout_link_when_logged_in(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert "/logout" in body
    # Some sign-out affordance should be present alongside the logout link.
    assert re.search(r"sign\s*out|log\s*out", body, re.IGNORECASE)


# ---------------------------------------------------------------------- #
# No hardcoded hex colours in the template source
# ---------------------------------------------------------------------- #


def test_profile_template_has_no_hardcoded_hex_colors():
    with open("templates/profile.html", encoding="utf-8") as f:
        source = f.read()

    hex_color_matches = re.findall(r"#[0-9a-fA-F]{3,8}\b", source)
    assert hex_color_matches == []
