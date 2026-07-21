"""
Tests for Step 9 — Delete Expense (.claude/specs/09-delete-expense.md).

Expected behaviour is derived strictly from the spec's "Routes", "Rules for
implementation", and "Definition of done" sections — not from reading the
`delete_expense` view body in app.py or the `delete_expense_by_id` query
helper's implementation in database/queries.py. Those files, plus
database/db.py, are only consulted for structural facts explicitly named by
the spec itself: the route/endpoint URL (`POST /expenses/<int:id>/delete`),
the `expenses` table columns, and the `get_summary_stats` helper already
exercised by tests/test_backend_connection.py for verifying summary-stat
side effects.

Fixtures `test_db_path`, `app`, and `client` come from tests/conftest.py
(fresh sqlite file per test, auto-seeded with a demo user and 8 demo expenses
via `seed_db()`). Login is established directly via
`client.session_transaction()` rather than through the `/login` route,
matching the house style already used in test_profile_page.py,
test_backend_connection.py, and test_08-edit-expense.py.

Out of scope: the spec's "shows a browser confirmation prompt before any
request is sent" / "cancelling sends no request" bullets describe
client-side `window.confirm()` behaviour wired up in static/js/main.js.
Flask's test client issues raw HTTP requests and never executes JavaScript,
so those two bullets are not (and cannot meaningfully be) covered here —
they belong to a browser-driven test suite instead.
"""

from datetime import date, timedelta

from database.db import get_db
from database.queries import get_summary_stats

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
    category="Food",
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


def _delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


# ---------------------------------------------------------------------- #
# Auth guard
# ---------------------------------------------------------------------- #


def test_post_delete_expense_redirects_to_login_when_logged_out(client):
    owner_id = _make_user()
    eid = _add_expense(owner_id)

    resp = client.post(_delete_url(eid))

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert (
        _get_expense_row(eid) is not None
    ), "An unauthenticated delete request must not remove the row"


# ---------------------------------------------------------------------- #
# GET is not allowed — route is POST-only
# ---------------------------------------------------------------------- #


def test_get_delete_expense_returns_405_and_does_not_delete(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.get(_delete_url(eid))

    assert resp.status_code == 405, (
        "Spec: the delete route must only accept POST; a plain GET/typed "
        "link must fail safely (405), never perform the deletion"
    )
    assert _get_expense_row(eid) is not None, "GET must never delete the row"


# ---------------------------------------------------------------------- #
# Happy path — deleting your own expense
# ---------------------------------------------------------------------- #


def test_post_delete_own_expense_removes_row_and_redirects_to_profile(client):
    uid = _make_user("Alex Rivera", "alex@example.com")
    eid = _add_expense(
        uid,
        amount=42.50,
        category="Food",
        expense_date="2026-06-01",
        description="Original description",
    )
    _login(client, uid, "Alex Rivera")

    resp = client.post(_delete_url(eid))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"
    assert _get_expense_row(eid) is None, "The row must be gone from the DB"


def test_post_delete_own_expense_shows_success_flash(client):
    uid = _make_user()
    eid = _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.post(_delete_url(eid), follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "flash" in body.lower() or "success" in body.lower(), (
        "Expected a flash message container/class to render on the profile "
        "page after a successful delete"
    )


def test_post_delete_own_expense_does_not_affect_other_rows(client):
    uid = _make_user()
    kept_eid = _add_expense(
        uid, amount=10.00, category="Transport", description="Keep me"
    )
    deleted_eid = _add_expense(
        uid, amount=20.00, category="Food", description="Delete me"
    )
    before_count = _expense_count()
    _login(client, uid, "Test User")

    resp = client.post(_delete_url(deleted_eid))

    assert resp.status_code == 302
    assert _get_expense_row(deleted_eid) is None
    assert (
        _get_expense_row(kept_eid) is not None
    ), "Deleting one expense must not remove any other row"
    assert _expense_count() == before_count - 1


# ---------------------------------------------------------------------- #
# Ownership guard
# ---------------------------------------------------------------------- #


def test_post_delete_expense_owned_by_another_user_redirects_to_profile(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id, description="Owner's private expense")
    _login(client, attacker_id, "Attacker User")

    resp = client.post(_delete_url(eid))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_post_delete_expense_owned_by_another_user_does_not_delete_row(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(
        owner_id,
        amount=99.00,
        category="Bills",
        expense_date="2026-05-01",
        description="Owner's expense",
    )
    before = _get_expense_row(eid)
    before_count = _expense_count()
    _login(client, attacker_id, "Attacker User")

    client.post(_delete_url(eid))

    after = _get_expense_row(eid)
    assert (
        after is not None
    ), "A non-owner's delete request must not remove the victim's row"
    assert after["amount"] == before["amount"]
    assert after["category"] == before["category"]
    assert after["date"] == before["date"]
    assert after["description"] == before["description"]
    assert _expense_count() == before_count


def test_post_delete_expense_owned_by_another_user_does_not_return_404(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id)
    _login(client, attacker_id, "Attacker User")

    resp = client.post(_delete_url(eid))

    assert resp.status_code != 404, (
        "Spec: attempting to delete another user's expense must redirect to "
        "profile, not raise a raw 404 (which would leak existence of the id)"
    )
    assert resp.status_code != 500


def test_post_delete_expense_owned_by_another_user_shows_flash(client):
    owner_id = _make_user("Owner User", "owner@example.com")
    attacker_id = _make_user("Attacker User", "attacker@example.com")
    eid = _add_expense(owner_id, description="Owner's private expense")
    _login(client, attacker_id, "Attacker User")

    resp = client.post(_delete_url(eid), follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "flash" in body.lower() or "not found" in body.lower(), (
        "Expected a flash message indicating the expense could not be " "deleted/found"
    )


# ---------------------------------------------------------------------- #
# Not found — nonexistent id behaves like the not-owned case
# ---------------------------------------------------------------------- #


def test_post_delete_nonexistent_expense_redirects_to_profile_without_crash(client):
    uid = _make_user()
    _login(client, uid, "Test User")
    before_count = _expense_count()

    nonexistent_id = 999999
    resp = client.post(_delete_url(nonexistent_id))

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"
    assert (
        _expense_count() == before_count
    ), "Deleting a nonexistent id must not change the row count"


def test_post_delete_nonexistent_expense_shows_flash_and_no_500(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.post(_delete_url(999999), follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert resp.status_code != 500
    assert "flash" in body.lower() or "not found" in body.lower()


# ---------------------------------------------------------------------- #
# Post-deletion effects on the profile page
# ---------------------------------------------------------------------- #


def test_deleted_expense_no_longer_appears_in_profile_transaction_list(client):
    uid = _make_user("Jordan Lee", "jordan@example.com")
    eid = _add_expense(uid, description="Unique text to disappear")
    _login(client, uid, "Jordan Lee")

    client.post(_delete_url(eid))

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Unique text to disappear" not in body


def test_deleted_expense_summary_stats_reflect_removal(client):
    uid = _make_user("Sam Taylor", "sam@example.com")
    kept_eid = _add_expense(uid, amount=15.00, category="Transport")
    deleted_eid = _add_expense(uid, amount=35.00, category="Food")
    _login(client, uid, "Sam Taylor")

    stats_before = get_summary_stats(uid)
    assert stats_before["total_spent"] == 50.00
    assert stats_before["transaction_count"] == 2

    client.post(_delete_url(deleted_eid))

    stats_after = get_summary_stats(uid)
    assert stats_after["total_spent"] == 15.00
    assert stats_after["transaction_count"] == 1
    assert stats_after["top_category"] == "Transport"

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "15.00" in body
    assert _get_expense_row(kept_eid) is not None
