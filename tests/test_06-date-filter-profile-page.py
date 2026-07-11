"""
Tests for Step 6 — Date Filter for Profile Page
(.claude/specs/06-date-filter-profile-page.md).

The spec extends the existing `GET /profile` route (no new routes) with
optional query params:
    - `range`: one of `all` (default), `7d`, `30d`, `this_month`,
      `last_month`, `custom`
    - `start` / `end`: `YYYY-MM-DD`, only used when `range=custom`

Summary stats, the transaction list, and the category breakdown must all
be narrowed consistently to the resolved date window. Invalid, malformed,
or incomplete custom dates and unknown `range` values must silently fall
back to all-time data rather than erroring (Definition of done).

These tests are written against the spec's contract only:
    - happy paths for every preset range
    - custom range with valid, boundary-inclusive dates
    - auth guard on the (now filterable) route
    - fallback behaviour for malformed/incomplete custom dates and unknown
      range values
    - empty-result state (zero matching expenses -> zero-value UI, no error)
    - summary / transactions / category-breakdown narrowing consistently
      together for a single filter
    - bookmarkable direct navigation to a filtered URL
    - the GET-form contract and the active-option indicator called out in
      the Definition of done

Boundary formulas for `7d`/`30d` (e.g. whether "today" itself is inside
the window, or exactly how many days back the window starts) are *not*
specified by the spec, so tests intentionally avoid asserting on the exact
edge day for those two presets and instead use dates that are unambiguously
inside or unambiguously outside any reasonable interpretation of "last N
days". `this_month`/`last_month` are calendar-month bounded and therefore
testable at their exact edges (first/last day of the month).
"""

import re
from datetime import date, timedelta

import pytest

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


def _add_expense(user_id, amount, category, date_str, description="x"):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def _login(client, user_id, user_name=None):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        if user_name is not None:
            sess["user_name"] = user_name


def _iso(offset_days):
    """ISO date string `offset_days` days before today (0 = today)."""
    return (date.today() - timedelta(days=offset_days)).isoformat()


def _active_control(body, value):
    """Return the opening tag of whichever control carries `value="<value>"`,
    regardless of element type (button/input/anchor), or None if absent."""
    match = re.search(rf'<\w+\b[^>]*value="{re.escape(value)}"[^>]*>', body)
    return match.group(0) if match else None


# ---------------------------------------------------------------------- #
# Auth guard
# ---------------------------------------------------------------------- #


def test_profile_with_range_param_redirects_when_unauthenticated(client):
    resp = client.get("/profile?range=30d")
    assert resp.status_code == 302, "Filtered /profile must still require login"
    assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------- #
# Default behaviour == all-time (unchanged from before this step)
# ---------------------------------------------------------------------- #


def test_no_query_params_shows_all_time_data(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent lunch")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient bus fare")
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Recent lunch" in body
    assert "Ancient bus fare" in body
    assert f"{50.00:.2f}" in body
    assert "₹" in body and "$" not in body and "£" not in body


def test_explicit_range_all_matches_default_view(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent lunch")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient bus fare")
    _login(client, uid, "Test User")

    default_body = client.get("/profile").get_data(as_text=True)
    explicit_body = client.get("/profile?range=all").get_data(as_text=True)

    assert default_body == explicit_body, (
        "range=all must reproduce exactly the same view as no query params"
    )


def test_start_end_ignored_when_range_is_not_custom(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent lunch")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient bus fare")
    _login(client, uid, "Test User")

    all_time_body = client.get("/profile?range=all").get_data(as_text=True)
    with_stray_dates_body = client.get(
        "/profile?range=all&start=2026-01-01&end=2026-01-02"
    ).get_data(as_text=True)

    assert all_time_body == with_stray_dates_body, (
        "start/end must only apply when range=custom"
    )


# ---------------------------------------------------------------------- #
# Preset range: last 7 days
# ---------------------------------------------------------------------- #


def test_range_7d_includes_recent_excludes_far_past(client):
    uid = _make_user()
    _add_expense(uid, 15.00, "Food", _iso(0), "TodayMeal")
    _add_expense(uid, 5.00, "Food", _iso(2), "TwoDaysAgoSnack")
    _add_expense(uid, 999.00, "Rent", _iso(60), "OldRentPayment")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=7d")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "TodayMeal" in body
    assert "TwoDaysAgoSnack" in body
    assert "OldRentPayment" not in body
    assert f"{20.00:.2f}" in body


# ---------------------------------------------------------------------- #
# Preset range: last 30 days
# ---------------------------------------------------------------------- #


def test_range_30d_includes_within_window_excludes_far_past(client):
    uid = _make_user()
    _add_expense(uid, 40.00, "Food", _iso(5), "InsideWindowMeal")
    _add_expense(uid, 10.00, "Transport", _iso(20), "InsideWindowBus")
    _add_expense(uid, 500.00, "Rent", _iso(90), "FarPastRent")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=30d")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "InsideWindowMeal" in body
    assert "InsideWindowBus" in body
    assert "FarPastRent" not in body
    assert f"{50.00:.2f}" in body


# ---------------------------------------------------------------------- #
# Preset range: this month
# ---------------------------------------------------------------------- #


def test_range_this_month_includes_current_month_excludes_last_month(client):
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_day_of_last_month = first_of_this_month - timedelta(days=1)

    uid = _make_user()
    _add_expense(uid, 12.00, "Food", first_of_this_month.isoformat(), "FirstOfThisMonth")
    _add_expense(uid, 8.00, "Food", today.isoformat(), "TodayExpense")
    _add_expense(uid, 99.00, "Bills", last_day_of_last_month.isoformat(), "LastDayLastMonth")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=this_month")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "FirstOfThisMonth" in body
    assert "TodayExpense" in body
    assert "LastDayLastMonth" not in body


# ---------------------------------------------------------------------- #
# Preset range: last month
# ---------------------------------------------------------------------- #


def test_range_last_month_includes_previous_month_excludes_this_month(client):
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_day_of_last_month = first_of_this_month - timedelta(days=1)
    first_of_last_month = last_day_of_last_month.replace(day=1)

    uid = _make_user()
    _add_expense(uid, 33.00, "Food", first_of_last_month.isoformat(), "FirstOfLastMonth")
    _add_expense(uid, 17.00, "Bills", last_day_of_last_month.isoformat(), "LastDayOfLastMonth")
    _add_expense(uid, 44.00, "Transport", first_of_this_month.isoformat(), "FirstOfThisMonthExcluded")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=last_month")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "FirstOfLastMonth" in body
    assert "LastDayOfLastMonth" in body
    assert "FirstOfThisMonthExcluded" not in body
    assert f"{50.00:.2f}" in body


# ---------------------------------------------------------------------- #
# Custom range: valid dates, inclusive of both boundaries
# ---------------------------------------------------------------------- #


def test_range_custom_valid_dates_are_inclusive_of_both_boundaries(client):
    start = date.today() - timedelta(days=10)
    end = date.today() - timedelta(days=5)
    just_before_start = start - timedelta(days=1)
    just_after_end = end + timedelta(days=1)

    uid = _make_user()
    _add_expense(uid, 10.00, "Food", start.isoformat(), "OnStartBoundary")
    _add_expense(uid, 20.00, "Food", end.isoformat(), "OnEndBoundary")
    _add_expense(uid, 1000.00, "Rent", just_before_start.isoformat(), "JustBeforeStart")
    _add_expense(uid, 2000.00, "Rent", just_after_end.isoformat(), "JustAfterEnd")
    _login(client, uid, "Test User")

    resp = client.get(f"/profile?range=custom&start={start.isoformat()}&end={end.isoformat()}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "OnStartBoundary" in body
    assert "OnEndBoundary" in body
    assert "JustBeforeStart" not in body
    assert "JustAfterEnd" not in body
    assert f"{30.00:.2f}" in body


# ---------------------------------------------------------------------- #
# Custom range fallback: missing / incomplete / malformed dates
# ---------------------------------------------------------------------- #


def test_range_custom_without_start_or_end_falls_back_to_all_time(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=custom")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Recent" in body
    assert "Ancient" in body


def test_range_custom_missing_end_falls_back_to_all_time(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient")
    _login(client, uid, "Test User")

    start = (date.today() - timedelta(days=5)).isoformat()
    resp = client.get(f"/profile?range=custom&start={start}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Recent" in body
    assert "Ancient" in body, "missing `end` must fall back to all-time, not error or drop rows"


def test_range_custom_missing_start_falls_back_to_all_time(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient")
    _login(client, uid, "Test User")

    end = date.today().isoformat()
    resp = client.get(f"/profile?range=custom&end={end}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Recent" in body
    assert "Ancient" in body, "missing `start` must fall back to all-time, not error or drop rows"


@pytest.mark.parametrize(
    "start,end",
    [
        ("not-a-date", "2026-07-10"),
        ("2026-07-01", "not-a-date"),
        ("2026-13-40", "2026-07-10"),
        ("07/01/2026", "07/10/2026"),
        ("", ""),
    ],
)
def test_range_custom_malformed_dates_fall_back_to_all_time(client, start, end):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient")
    _login(client, uid, "Test User")

    resp = client.get(f"/profile?range=custom&start={start}&end={end}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200, f"malformed dates ({start!r}, {end!r}) must not error"
    assert "Recent" in body
    assert "Ancient" in body


# ---------------------------------------------------------------------- #
# Unknown `range` value fallback
# ---------------------------------------------------------------------- #


def test_unknown_range_value_falls_back_to_all_time(client):
    uid = _make_user()
    _add_expense(uid, 20.00, "Food", _iso(2), "Recent")
    _add_expense(uid, 30.00, "Transport", _iso(400), "Ancient")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=not_a_real_range")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Recent" in body
    assert "Ancient" in body


# ---------------------------------------------------------------------- #
# Empty-result state
# ---------------------------------------------------------------------- #


def test_range_with_zero_matching_expenses_shows_zero_state_without_error(client):
    uid = _make_user()
    _add_expense(uid, 42.00, "Groceries", date.today().isoformat(), "OutsideFilterWindow")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=custom&start=2000-01-01&end=2000-01-02")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"{0.00:.2f}" in body, "zero-match filter should show ₹0.00 total spent"
    assert "OutsideFilterWindow" not in body
    assert "Groceries" not in body, "category breakdown must be empty for zero-match filter"


# ---------------------------------------------------------------------- #
# Consistency: summary + transactions + category breakdown narrow together
# ---------------------------------------------------------------------- #


def test_filter_narrows_summary_transactions_and_categories_consistently(client):
    uid = _make_user()
    _add_expense(uid, 40.00, "Food", _iso(3), "InsideMeal")
    _add_expense(uid, 25.50, "Transport", _iso(15), "InsideBus")
    _add_expense(uid, 999.99, "Rent", _iso(90), "OutsideRent")
    _login(client, uid, "Test User")

    resp = client.get("/profile?range=30d")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # Summary reflects only the two in-window expenses.
    assert f"{65.50:.2f}" in body
    # Transaction list reflects only the two in-window expenses.
    assert "InsideMeal" in body
    assert "InsideBus" in body
    assert "OutsideRent" not in body
    # Category breakdown reflects only in-window categories.
    assert "Food" in body
    assert "Transport" in body
    assert "Rent" not in body


# ---------------------------------------------------------------------- #
# Bookmarkable direct navigation
# ---------------------------------------------------------------------- #


def test_direct_navigation_to_filtered_url_reproduces_same_filtered_view(client):
    uid = _make_user()
    _add_expense(uid, 40.00, "Food", _iso(3), "InsideMeal")
    _add_expense(uid, 999.99, "Rent", _iso(90), "OutsideRent")
    _login(client, uid, "Test User")

    first_visit = client.get("/profile?range=30d").get_data(as_text=True)
    second_visit = client.get("/profile?range=30d").get_data(as_text=True)

    assert first_visit == second_visit, (
        "revisiting a bookmarked filtered URL must reproduce an identical view"
    )


# ---------------------------------------------------------------------- #
# GET-form contract + active-option indicator (Definition of done)
# ---------------------------------------------------------------------- #


def test_filter_form_submits_via_get(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert re.search(r'<form[^>]*method=["\']GET["\']', body, re.IGNORECASE), (
        "filter must submit as a GET form so the URL is bookmarkable"
    )


@pytest.mark.parametrize("range_value", ["all", "7d", "30d", "this_month", "last_month", "custom"])
def test_selected_preset_option_is_marked_active(client, range_value):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get(f"/profile?range={range_value}")
    body = resp.get_data(as_text=True)

    control = _active_control(body, range_value)
    assert control is not None, f"expected a filter control for range={range_value}"
    assert "is-active" in control or "active" in control, (
        f"the selected range option ({range_value}) must be visually distinguishable"
    )


def test_default_view_marks_all_time_option_active(client):
    uid = _make_user()
    _login(client, uid, "Test User")

    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    control = _active_control(body, "all")
    assert control is not None, "expected a control representing the 'all time' option"
    assert "is-active" in control or "active" in control, (
        "default (no query params) view must mark 'all time' as the active option"
    )
