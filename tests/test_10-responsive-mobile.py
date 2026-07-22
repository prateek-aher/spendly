"""
Tests for Step 10 — Responsive Design for Mobile Devices
(.claude/specs/10-responsive-mobile.md).

This spec is CSS/JS/HTML-only: it adds a hamburger nav-toggle button and
`data-label` attributes to the profile transaction table so the same markup
can be restyled for mobile via CSS media queries. It introduces **no new
routes and no database changes** (see the spec's "Routes" / "Database
changes" sections).

Pure visual/layout behaviour — whether a media query breakpoint fires,
whether `.nav-links` visually slides open, or actual rendered pixel sizes of
touch targets — cannot be exercised via Flask's test client, since there is
no browser or CSS engine involved here. Those bullets in the spec's
"Definition of done" (375px viewport behaviour, dropdown open/close
animation, tap-target sizing, "no horizontal scrollbar") are out of scope for
this file and belong in a browser-driven (e.g. Playwright/Selenium) test
suite instead.

What *is* testable from rendered HTML, and what this file covers:
  - `templates/base.html`'s nav markup includes the new hamburger toggle
    button with the required id/aria attributes, and `.nav-links` now
    exposes `id="nav-links"` so the button's `aria-controls` reference is
    valid — checked on both an anonymous page (`/`) and an authenticated
    page (`/profile`).
  - `templates/profile.html`'s transaction table rows carry
    `data-label="Date"` / `"Description"` / `"Category"` / `"Amount"` /
    `"Actions"` attributes on their respective `<td>`s.
  - Nothing this step touches (route auth guards, status codes, actual
    transaction data, edit/delete affordances, nav auth-state content) is
    broken by these markup changes.

Fixtures `test_db_path`, `app`, and `client` come from tests/conftest.py
(fresh sqlite file per test). Login is established directly via
`client.session_transaction()`, matching the house style already used in
test_profile_page.py, test_08-edit-expense.py, and test_09-delete-expense.py.
"""

import re

from database.db import get_db

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
    amount=12.00,
    category="Food",
    expense_date="2026-07-01",
    description="Groceries run",
):
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


def _find_tags(body, tag_name):
    """Return every opening tag (e.g. '<button ...>') for the given tag name."""
    return re.findall(rf"<{tag_name}\b[^>]*>", body, flags=re.IGNORECASE)


def _find_tag_containing(body, tag_name, needle):
    """Return the first opening tag of `tag_name` whose attributes contain
    `needle`, or None if there isn't one."""
    for tag in _find_tags(body, tag_name):
        if needle in tag:
            return tag
    return None


# ---------------------------------------------------------------------- #
# Hamburger nav-toggle markup — present on an anonymous page
# ---------------------------------------------------------------------- #


def test_landing_page_has_nav_toggle_button_with_required_attrs(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200

    toggle_tag = _find_tag_containing(body, "button", 'id="nav-toggle"')
    assert toggle_tag is not None, (
        'Expected a <button id="nav-toggle"> inside base.html\'s nav, '
        "reachable on every page including the anonymous landing page"
    )
    assert 'aria-controls="nav-links"' in toggle_tag, (
        "The hamburger toggle must reference the nav links panel via "
        'aria-controls="nav-links"'
    )
    assert 'aria-expanded="false"' in toggle_tag, (
        'The hamburger toggle must start with aria-expanded="false" '
        "(closed) on initial page load"
    )
    assert re.search(r'aria-label="[^"]+"', toggle_tag), (
        "The hamburger toggle must carry a non-empty aria-label for " "accessibility"
    )


def test_landing_page_nav_links_container_has_id_for_aria_controls(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)

    assert 'id="nav-links"' in body, (
        'The .nav-links container must expose id="nav-links" so the '
        "hamburger's aria-controls reference resolves to a real element"
    )


# ---------------------------------------------------------------------- #
# Hamburger nav-toggle markup — present on an authenticated page too
# ---------------------------------------------------------------------- #


def test_profile_page_has_nav_toggle_button_with_required_attrs(client):
    uid = _make_user("Jamie Rivera", "jamie.rivera@example.com")
    _login(client, uid, "Jamie Rivera")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200

    toggle_tag = _find_tag_containing(body, "button", 'id="nav-toggle"')
    assert toggle_tag is not None, (
        "Expected the same nav-toggle button from base.html to render on "
        "an authenticated page (profile) as well"
    )
    assert 'aria-controls="nav-links"' in toggle_tag
    assert 'aria-expanded="false"' in toggle_tag
    assert re.search(r'aria-label="[^"]+"', toggle_tag)


def test_profile_page_nav_links_container_has_id_for_aria_controls(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert 'id="nav-links"' in body


def test_profile_page_nav_still_shows_authenticated_links_alongside_toggle(client):
    # Regression: adding the hamburger toggle must not remove/replace the
    # existing session-aware nav content (greeting/Profile/Analytics/Sign out)
    # from the rendered HTML — it's just newly reachable via the toggle on
    # narrow screens per CSS, not deleted from the markup.
    uid = _make_user("Jordan Lee", "jordan@example.com")
    _login(client, uid, "Jordan Lee")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert 'href="/profile"' in body
    assert "Sign out" in body
    assert "/logout" in body


def test_landing_page_nav_still_shows_logged_out_links_alongside_toggle(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)

    assert "Sign in" in body
    assert "Get started" in body
    assert "Sign out" not in body


# ---------------------------------------------------------------------- #
# Profile transaction table — data-label attributes on <td>s
# ---------------------------------------------------------------------- #


def test_profile_transaction_row_tds_have_data_label_attributes(client):
    uid = _make_user()
    _add_expense(
        uid,
        amount=12.00,
        category="Food",
        expense_date="2026-07-01",
        description="Groceries run",
    )
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for label in ("Date", "Description", "Category", "Amount", "Actions"):
        assert f'data-label="{label}"' in body, (
            f'Expected a <td data-label="{label}"> in the transaction row '
            "so CSS can restyle it into a stacked mobile card via "
            "::before { content: attr(data-label) }"
        )


def test_profile_transaction_table_data_label_count_matches_row_count(client):
    uid = _make_user()
    _add_expense(uid, amount=12.00, category="Food", description="First expense")
    _add_expense(
        uid,
        amount=8.50,
        category="Transport",
        expense_date="2026-07-02",
        description="Second expense",
    )
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    # Each of the two rows should contribute one data-label="Date" (and so on
    # for the other four labels) — i.e. the attribute isn't just present once
    # for the first row but wired into the actual per-row loop.
    for label in ("Date", "Description", "Category", "Amount", "Actions"):
        occurrences = body.count(f'data-label="{label}"')
        assert occurrences >= 2, (
            f'Expected data-label="{label}" to appear on every transaction '
            f"row (>= 2 for 2 seeded expenses), found {occurrences}"
        )


def test_profile_transaction_table_underlying_markup_is_still_a_table(client):
    # Rule for implementation: "Keep the transaction table's underlying
    # <table> markup (don't switch to <div>-based cards)".
    uid = _make_user()
    _add_expense(uid)
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert "<table" in body
    assert "<td" in body
    assert "<tr" in body


# ---------------------------------------------------------------------- #
# Regression — existing functional behaviour untouched by this feature
# ---------------------------------------------------------------------- #


def test_profile_still_redirects_to_login_when_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_still_returns_200_when_authenticated(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    assert resp.status_code == 200


def test_landing_page_still_returns_200_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_login_page_still_renders_form_and_has_nav_toggle(client):
    # Sanity check that base.html's nav-toggle addition is inherited on a
    # page other than landing/profile too, and that it hasn't broken the
    # page's own core content.
    resp = client.get("/login")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'name="email"' in body
    assert 'name="password"' in body
    assert 'id="nav-toggle"' in body
    assert 'id="nav-links"' in body


def test_profile_transaction_table_still_shows_correct_data_values(client):
    uid = _make_user("Alex Rivera", "alex@example.com")
    _add_expense(
        uid,
        amount=42.50,
        category="Food",
        expense_date="2026-06-01",
        description="Unique data-check description",
    )
    _login(client, uid, "Alex Rivera")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Unique data-check description" in body
    assert "Food" in body
    assert "42.50" in body


def test_profile_transaction_row_still_has_edit_and_delete_actions(client):
    uid = _make_user()
    eid = _add_expense(uid, description="Row with actions")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"/expenses/{eid}/edit" in body, (
        "Expected the row's Edit action to still link to "
        "/expenses/<id>/edit after the data-label markup change"
    )
    assert f"/expenses/{eid}/delete" in body, (
        "Expected the row's Delete action to still target "
        "/expenses/<id>/delete after the data-label markup change"
    )


def test_add_expense_still_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_add_expense_form_page_still_renders_when_authenticated(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'name="amount"' in body
    assert 'name="category"' in body
