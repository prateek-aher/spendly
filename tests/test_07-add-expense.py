"""
Tests for Step 7 — Add Expense (.claude/specs/07-add-expense.md).

Expected behaviour is derived strictly from the spec's "Routes", "Rules for
implementation", and "Definition of done" sections — not from reading the
`add_expense` view body in app.py. `app.py` and `database/db.py` are only
consulted for structural facts explicitly named by the spec itself: the
route/endpoint names, the `expenses` table columns, and the fixed
`CATEGORIES` list the spec says validation must check against.

Fixtures `test_db_path`, `app`, and `client` come from tests/conftest.py
(fresh in-memory-backed sqlite file per test, auto-seeded with a demo user
and 8 demo expenses via `seed_db()`). Login is established directly via
`client.session_transaction()` rather than through the `/login` route,
matching the house style already used in test_profile_page.py and
test_backend_connection.py.
"""

import re
from datetime import date, timedelta

from database.db import CATEGORIES, get_db

VALID_CATEGORY = "Food"
INVALID_CATEGORY = "NotARealCategory"

assert VALID_CATEGORY in CATEGORIES
assert INVALID_CATEGORY not in CATEGORIES


# ---------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------- #


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


def _login(client, user_id, user_name=None):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        if user_name is not None:
            sess["user_name"] = user_name


def _expense_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    conn.close()
    return count


def _expenses_for_user(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def _valid_form(**overrides):
    """A baseline valid /expenses/add POST payload; override fields per-test."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "amount": "42.50",
        "category": VALID_CATEGORY,
        "date": yesterday,
        "description": "Grocery run",
    }
    payload.update(overrides)
    return payload


def _input_tag(name_attr, body):
    """Return the first <input ...> tag whose name= attribute matches, or None."""
    match = re.search(rf'<input[^>]*name="{name_attr}"[^>]*>', body)
    return match.group(0) if match else None


# ---------------------------------------------------------------------- #
# Auth guard
# ---------------------------------------------------------------------- #


def test_get_add_expense_redirects_to_login_when_logged_out(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_add_expense_redirects_to_login_when_logged_out(client):
    before = _expense_count()
    resp = client.post("/expenses/add", data=_valid_form())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _expense_count() == before, "No row should be inserted for an unauthenticated POST"


# ---------------------------------------------------------------------- #
# GET /expenses/add — form rendering
# ---------------------------------------------------------------------- #


def test_get_add_expense_authenticated_returns_200_with_all_fields(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body
    assert 'name="description"' in body
    for cat in CATEGORIES:
        assert f'value="{cat}"' in body, f"Expected a pill/radio for category {cat!r}"


def test_get_add_expense_date_defaults_to_today(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)
    today = date.today().isoformat()

    date_tag = _input_tag("date", body)
    assert date_tag is not None, "Expected a date input on the add-expense form"
    assert f'value="{today}"' in date_tag, "Date field should default to today's date"


# ---------------------------------------------------------------------- #
# POST /expenses/add — happy path
# ---------------------------------------------------------------------- #


def test_post_valid_expense_inserts_row_scoped_to_current_user(client):
    uid = _make_user("Alex Rivera", "alex@example.com")
    _login(client, uid, "Alex Rivera")

    payload = _valid_form(description="Weekly groceries")
    resp = client.post("/expenses/add", data=payload)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"

    rows = _expenses_for_user(uid)
    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == uid
    assert row["amount"] == 42.50
    assert row["category"] == VALID_CATEGORY
    assert row["date"] == payload["date"]
    assert row["description"] == "Weekly groceries"


def test_post_valid_expense_appears_in_profile_recent_transactions(client):
    uid = _make_user("Jordan Lee", "jordan@example.com")
    _login(client, uid, "Jordan Lee")

    client.post("/expenses/add", data=_valid_form(description="Unique lunch entry"))

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Unique lunch entry" in body
    assert VALID_CATEGORY in body


def test_post_valid_expense_reflected_in_summary_stats(client):
    uid = _make_user("Sam Park", "sam@example.com")
    _login(client, uid, "Sam Park")

    client.post("/expenses/add", data=_valid_form(amount="100.00", description="Stats check"))

    after_resp = client.get("/profile")
    after_body = after_resp.get_data(as_text=True)
    assert after_resp.status_code == 200
    # The newly added ₹100.00 expense (this user's only expense) should be
    # reflected in the total-spent stat.
    assert "100.00" in after_body


def test_post_valid_expense_reflected_in_category_breakdown(client):
    uid = _make_user("Riley Fox", "riley@example.com")
    _login(client, uid, "Riley Fox")

    client.post("/expenses/add", data=_valid_form(category="Entertainment", description="Breakdown check"))

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Entertainment" in body


def test_profile_has_working_add_expense_link(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'href="/expenses/add"' in body
    assert "Add expense" in body


# ---------------------------------------------------------------------- #
# Validation errors — amount
# ---------------------------------------------------------------------- #


def test_post_negative_amount_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    resp = client.post("/expenses/add", data=_valid_form(amount="-5.00"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="amount"' in body


def test_post_zero_amount_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    resp = client.post("/expenses/add", data=_valid_form(amount="0"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="amount"' in body


def test_post_non_numeric_amount_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    resp = client.post("/expenses/add", data=_valid_form(amount="not-a-number"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="amount"' in body


# ---------------------------------------------------------------------- #
# Validation errors — category
# ---------------------------------------------------------------------- #


def test_post_category_outside_fixed_list_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    resp = client.post("/expenses/add", data=_valid_form(category=INVALID_CATEGORY))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="category"' in body


# ---------------------------------------------------------------------- #
# Validation errors — date
# ---------------------------------------------------------------------- #


def test_post_malformed_date_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    resp = client.post("/expenses/add", data=_valid_form(date="13/07/2026"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="date"' in body


def test_post_future_date_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    future = (date.today() + timedelta(days=7)).isoformat()
    resp = client.post("/expenses/add", data=_valid_form(date=future))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    assert 'data-error-field="date"' in body


# ---------------------------------------------------------------------- #
# Validation errors — description
# ---------------------------------------------------------------------- #


def test_post_description_over_200_chars_shows_error_and_does_not_insert(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before = _expense_count()

    long_description = "x" * 201
    resp = client.post("/expenses/add", data=_valid_form(description=long_description))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _expense_count() == before
    # Proxy for "focus lands on the description field": the spec requires
    # the route to pass an error_field the template uses to drive focus;
    # actual browser focus can't be observed via the test client.
    assert 'data-error-field="description"' in body


# ---------------------------------------------------------------------- #
# Amount rounding
# ---------------------------------------------------------------------- #


def test_post_amount_with_float_artifacts_is_rounded_to_two_decimals(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.post("/expenses/add", data=_valid_form(amount="19.999999999998"))
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"

    rows = _expenses_for_user(uid)
    assert len(rows) == 1
    # Spec: "normalized to 2 decimal places (round(amount, 2))".
    assert rows[0]["amount"] == round(19.999999999998, 2)


# ---------------------------------------------------------------------- #
# Description optional
# ---------------------------------------------------------------------- #


def test_post_blank_description_succeeds(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.post("/expenses/add", data=_valid_form(description=""))
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"

    rows = _expenses_for_user(uid)
    assert len(rows) == 1
    assert rows[0]["description"] in (None, ""), "Blank description should be stored as NULL/empty"


def test_post_blank_description_does_not_render_literal_none_string(client):
    uid = _make_user("No Desc User", "nodesc@example.com")
    _login(client, uid, "No Desc User")

    client.post("/expenses/add", data=_valid_form(description="", amount="17.00"))

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "17.00" in body
    assert "None" not in body, "Blank description must not render as the literal string 'None'"


# ---------------------------------------------------------------------- #
# "Add another expense" flow
# ---------------------------------------------------------------------- #


def test_post_with_add_another_checked_redirects_back_to_form(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.post("/expenses/add", data=_valid_form(add_another="on"))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/expenses/add"
    # The expense should still have been saved before the multi-entry redirect.
    assert len(_expenses_for_user(uid)) == 1
    with client.session_transaction() as sess:
        assert sess.get("keep_add_another") is True


def test_post_without_add_another_redirects_to_profile(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.post("/expenses/add", data=_valid_form())

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_get_add_expense_with_keep_add_another_shows_checkbox_checked(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    with client.session_transaction() as sess:
        sess["keep_add_another"] = True

    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    checkbox_tag = _input_tag("add_another", body)
    assert checkbox_tag is not None, "Expected an 'add_another' checkbox on the form"
    assert "checked" in checkbox_tag, "Checkbox should start pre-checked when keep_add_another session flag is set"
    with client.session_transaction() as sess:
        assert "keep_add_another" not in sess, "The session flag should be popped after being read once"


def test_get_add_expense_without_keep_add_another_checkbox_not_checked(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    checkbox_tag = _input_tag("add_another", body)
    assert checkbox_tag is not None
    assert "checked" not in checkbox_tag, "Checkbox should not be pre-checked by default"


# ---------------------------------------------------------------------- #
# Insert always uses session user_id, never a form-supplied value
# ---------------------------------------------------------------------- #


def test_post_ignores_form_supplied_user_id_and_uses_session_user(client):
    victim_id = _make_user("Victim User", "victim@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    _login(client, attacker_id, "Attacker User")

    payload = _valid_form(description="Session-scoped insert check")
    payload["user_id"] = str(victim_id)  # spoofed field; must be ignored

    resp = client.post("/expenses/add", data=payload)
    assert resp.status_code == 302

    attacker_rows = _expenses_for_user(attacker_id)
    victim_rows = _expenses_for_user(victim_id)

    assert len(attacker_rows) == 1, "The expense must be attributed to the logged-in session user"
    assert attacker_rows[0]["description"] == "Session-scoped insert check"
    assert len(victim_rows) == 0, "The spoofed form user_id must never be used for the insert"
