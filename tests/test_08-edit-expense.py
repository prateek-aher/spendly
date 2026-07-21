"""
Tests for Step 8 — Edit Expense (.claude/specs/08-edit-expense.md).

Expected behaviour is derived strictly from the spec's "Routes", "Rules for
implementation", and "Definition of done" sections — not from reading the
`edit_expense` view body in app.py or the `get_expense_by_id`/`update_expense`
implementations in database/queries.py. Those files, plus database/db.py, are
only consulted for structural facts explicitly named by the spec itself: the
route/endpoint name and its `<int:id>` URL, the `expenses` table columns, and
the fixed `CATEGORIES` list the spec says validation must check against
(reusing the same rules as Step 7 — Add Expense).

Fixtures `test_db_path`, `app`, and `client` come from tests/conftest.py
(fresh sqlite file per test, auto-seeded with a demo user and 8 demo expenses
via `seed_db()`). Login is established directly via
`client.session_transaction()` rather than through the `/login` route,
matching the house style already used in test_profile_page.py,
test_backend_connection.py, and test_07-add-expense.py.
"""

import re
from datetime import date, timedelta

from database.db import CATEGORIES, get_db

VALID_CATEGORY = "Food"
OTHER_VALID_CATEGORY = "Transport"
INVALID_CATEGORY = "NotARealCategory"

assert VALID_CATEGORY in CATEGORIES
assert OTHER_VALID_CATEGORY in CATEGORIES
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


def _add_expense(
    user_id,
    amount=42.50,
    category=VALID_CATEGORY,
    expense_date=None,
    description="Original description",
):
    expense_date = expense_date or (date.today() - timedelta(days=1)).isoformat()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def _get_expense_row(expense_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row


def _expense_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    conn.close()
    return count


def _valid_form(**overrides):
    """A baseline valid /expenses/<id>/edit POST payload; override per-test."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "amount": "99.99",
        "category": OTHER_VALID_CATEGORY,
        "date": yesterday,
        "description": "Updated description",
    }
    payload.update(overrides)
    return payload


def _input_tag(name_attr, body):
    """Return the first <input ...> tag whose name= attribute matches, or None."""
    match = re.search(rf'<input[^>]*name="{name_attr}"[^>]*>', body)
    return match.group(0) if match else None


def _edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


# ---------------------------------------------------------------------- #
# Auth guard
# ---------------------------------------------------------------------- #


def test_get_edit_expense_redirects_to_login_when_logged_out(client):
    owner_id = _make_user()
    eid = _add_expense(owner_id)

    resp = client.get(_edit_url(eid))

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_edit_expense_redirects_to_login_when_logged_out(client):
    owner_id = _make_user()
    eid = _add_expense(owner_id)
    before = _get_expense_row(eid)

    resp = client.post(_edit_url(eid), data=_valid_form())

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    after = _get_expense_row(eid)
    assert (
        after["amount"] == before["amount"]
    ), "Row must not change for an unauthenticated POST"
    assert after["category"] == before["category"]
    assert after["date"] == before["date"]
    assert after["description"] == before["description"]


# ---------------------------------------------------------------------- #
# GET — happy path: form pre-filled with existing values
# ---------------------------------------------------------------------- #


def test_get_edit_expense_owned_by_current_user_returns_200_prefilled(client):
    uid = _make_user()
    eid = _add_expense(
        uid,
        amount=45.50,
        category="Food",
        expense_date="2026-06-01",
        description="Groceries",
    )
    _login(client, uid, "Test User")

    resp = client.get(_edit_url(eid))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200

    amount_tag = _input_tag("amount", body)
    assert amount_tag is not None
    assert 'value="45.5"' in amount_tag or 'value="45.50"' in amount_tag

    date_tag = _input_tag("date", body)
    assert date_tag is not None
    assert 'value="2026-06-01"' in date_tag

    description_tag = _input_tag("description", body)
    assert description_tag is not None
    assert 'value="Groceries"' in description_tag

    # Category should be pre-selected (checked) on the matching radio/pill input.
    category_match = re.search(
        r'<input[^>]*name="category"[^>]*value="Food"[^>]*>', body
    )
    assert category_match is not None
    assert "checked" in category_match.group(
        0
    ), "Expense's current category should be pre-selected"


def test_get_edit_expense_shows_all_category_options(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.get(_edit_url(eid))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for cat in CATEGORIES:
        assert f'value="{cat}"' in body, f"Expected a pill/radio for category {cat!r}"


# ---------------------------------------------------------------------- #
# No "add another expense" checkbox in edit mode
# ---------------------------------------------------------------------- #


def test_get_edit_expense_form_has_no_add_another_checkbox(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.get(_edit_url(eid))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert (
        _input_tag("add_another", body) is None
    ), "Spec: the edit form must not include an 'add another expense' checkbox"


def test_post_invalid_edit_rerender_has_no_add_another_checkbox(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(amount="-5"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _input_tag("add_another", body) is None, (
        "The 'add another expense' checkbox must stay absent even on the "
        "error re-render of the edit form"
    )


# ---------------------------------------------------------------------- #
# POST — happy path: valid update persists and redirects
# ---------------------------------------------------------------------- #


def test_post_valid_edit_updates_row_and_redirects_to_profile(client):
    uid = _make_user("Alex Rivera", "alex@example.com")
    eid = _add_expense(
        uid,
        amount=42.50,
        category="Food",
        expense_date="2026-06-01",
        description="Original description",
    )
    _login(client, uid, "Alex Rivera")

    payload = _valid_form(
        amount="150.25",
        category="Transport",
        date="2026-06-10",
        description="Weekly commute pass",
    )
    resp = client.post(_edit_url(eid), data=payload)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"

    row = _get_expense_row(eid)
    assert row["amount"] == 150.25
    assert row["category"] == "Transport"
    assert row["date"] == "2026-06-10"
    assert row["description"] == "Weekly commute pass"


def test_post_valid_edit_does_not_create_a_new_row(client):
    uid = _make_user()
    eid = _add_expense(uid)
    before_count = _expense_count()
    _login(client, uid, "Test User")

    client.post(_edit_url(eid), data=_valid_form())

    assert (
        _expense_count() == before_count
    ), "Editing must UPDATE the existing row, not INSERT a new one"


def test_post_valid_edit_shows_success_flash_on_profile(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(), follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # The redirected-to page is /profile; a flashed success message should render.
    assert "flash" in body.lower() or "success" in body.lower(), (
        "Expected a flash message container/class to render on the profile "
        "page after a successful edit"
    )


def test_post_valid_edit_change_reflected_in_profile_transactions(client):
    uid = _make_user("Jordan Lee", "jordan@example.com")
    eid = _add_expense(uid, description="Old description")
    _login(client, uid, "Jordan Lee")

    client.post(_edit_url(eid), data=_valid_form(description="Brand new unique text"))

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Brand new unique text" in body
    assert "Old description" not in body


# ---------------------------------------------------------------------- #
# Ownership guard
# ---------------------------------------------------------------------- #


def test_get_edit_expense_owned_by_another_user_redirects_to_profile(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id, description="Owner's private expense")
    _login(client, attacker_id, "Attacker User")

    resp = client.get(_edit_url(eid))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_get_edit_expense_owned_by_another_user_does_not_leak_data(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id, description="Owner's secret expense text")
    _login(client, attacker_id, "Attacker User")

    resp = client.get(_edit_url(eid), follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Owner's secret expense text" not in body, (
        "Another user's expense description must never be rendered to a "
        "non-owner, even via the redirect target"
    )


def test_post_edit_expense_owned_by_another_user_redirects_and_does_not_modify_row(
    client,
):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(
        owner_id,
        amount=10.00,
        category="Food",
        expense_date="2026-05-01",
        description="Owner's expense",
    )
    before = _get_expense_row(eid)
    _login(client, attacker_id, "Attacker User")

    resp = client.post(_edit_url(eid), data=_valid_form(amount="9999.99"))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"

    after = _get_expense_row(eid)
    assert (
        after["amount"] == before["amount"]
    ), "A non-owner's POST must not change the victim's row"
    assert after["category"] == before["category"]
    assert after["date"] == before["date"]
    assert after["description"] == before["description"]


def test_post_edit_expense_owned_by_another_user_does_not_return_404(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id)
    _login(client, attacker_id, "Attacker User")

    resp = client.post(_edit_url(eid), data=_valid_form())

    assert resp.status_code != 404, (
        "Spec: attempting to edit another user's expense must redirect to "
        "profile, not raise a raw 404 (which would leak existence of the id)"
    )
    assert resp.status_code != 500


# ---------------------------------------------------------------------- #
# Not found
# ---------------------------------------------------------------------- #


def test_get_edit_nonexistent_expense_redirects_to_profile(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    nonexistent_id = 999999

    resp = client.get(_edit_url(nonexistent_id))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_post_edit_nonexistent_expense_redirects_to_profile_and_inserts_nothing(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before_count = _expense_count()

    nonexistent_id = 999999
    resp = client.post(_edit_url(nonexistent_id), data=_valid_form())

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"
    assert (
        _expense_count() == before_count
    ), "No row should be inserted or modified for a missing id"


# ---------------------------------------------------------------------- #
# Validation errors — amount
# ---------------------------------------------------------------------- #


def test_post_negative_amount_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, amount=42.50, category="Food", description="Keep me")
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(amount="-5.00"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="amount"' in body
    after = _get_expense_row(eid)
    assert after["amount"] == before["amount"], "Invalid amount must not be persisted"


def test_post_zero_amount_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, amount=42.50)
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(amount="0"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="amount"' in body
    after = _get_expense_row(eid)
    assert after["amount"] == before["amount"]


def test_post_non_numeric_amount_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, amount=42.50)
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(amount="not-a-number"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="amount"' in body
    after = _get_expense_row(eid)
    assert after["amount"] == before["amount"]


def test_post_invalid_amount_preserves_other_submitted_field_values(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    payload = _valid_form(
        amount="-5.00",
        category="Entertainment",
        description="Preserved description text",
    )
    resp = client.post(_edit_url(eid), data=payload)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    description_tag = _input_tag("description", body)
    assert description_tag is not None
    assert 'value="Preserved description text"' in description_tag

    category_match = re.search(
        r'<input[^>]*name="category"[^>]*value="Entertainment"[^>]*>', body
    )
    assert category_match is not None
    assert "checked" in category_match.group(
        0
    ), "Submitted category should remain selected when the amount is invalid"

    date_tag = _input_tag("date", body)
    assert date_tag is not None
    assert f'value="{payload["date"]}"' in date_tag


# ---------------------------------------------------------------------- #
# Validation errors — category
# ---------------------------------------------------------------------- #


def test_post_invalid_category_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, category="Food")
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(category=INVALID_CATEGORY))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="category"' in body
    after = _get_expense_row(eid)
    assert after["category"] == before["category"]


# ---------------------------------------------------------------------- #
# Validation errors — date
# ---------------------------------------------------------------------- #


def test_post_future_date_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, expense_date="2026-01-01")
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    future = (date.today() + timedelta(days=7)).isoformat()
    resp = client.post(_edit_url(eid), data=_valid_form(date=future))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="date"' in body
    after = _get_expense_row(eid)
    assert after["date"] == before["date"]


def test_post_malformed_date_rerenders_form_with_error_and_does_not_update(client):
    uid = _make_user()
    eid = _add_expense(uid, expense_date="2026-01-01")
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    resp = client.post(_edit_url(eid), data=_valid_form(date="13/07/2026"))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="date"' in body
    after = _get_expense_row(eid)
    assert after["date"] == before["date"]


# ---------------------------------------------------------------------- #
# Validation errors — description
# ---------------------------------------------------------------------- #


def test_post_description_over_200_chars_rerenders_form_with_error_and_does_not_update(
    client,
):
    uid = _make_user()
    eid = _add_expense(uid, description="Short original")
    before = _get_expense_row(eid)
    _login(client, uid, "Test User")

    long_description = "x" * 201
    resp = client.post(_edit_url(eid), data=_valid_form(description=long_description))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-error-field="description"' in body
    after = _get_expense_row(eid)
    assert after["description"] == before["description"]


def test_post_description_exactly_200_chars_is_accepted(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    exactly_200 = "y" * 200
    resp = client.post(_edit_url(eid), data=_valid_form(description=exactly_200))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"
    after = _get_expense_row(eid)
    assert after["description"] == exactly_200
