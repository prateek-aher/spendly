# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page. Right now every
summary stat, the transaction list, and the category breakdown always
reflect the user's *entire* expense history. This step lets a user narrow
that view to a preset window (e.g. last 30 days, this month) or a custom
start/end date, so the profile page can answer "how am I doing this month"
rather than only "how am I doing overall." Filtering happens server-side via
query parameters on the existing route — no new page or JS framework is
introduced.

## Depends on
- Step 1: Database setup (`expenses.date` column exists, stored as `YYYY-MM-DD` text)
- Step 4: Profile page static UI (`profile.html` layout exists)
- Step 5: Backend connection (`database/queries.py` helpers and live `/profile` route exist)

## Routes
No new routes. The existing `GET /profile` route is extended to accept
optional query parameters:
- `range` — one of `all` (default), `7d`, `30d`, `this_month`, `last_month`, `custom`
- `start` — `YYYY-MM-DD`, required only when `range=custom`
- `end` — `YYYY-MM-DD`, required only when `range=custom`

Access level: logged-in only (same guard as today).

## Database changes
No database changes. `expenses.date` is already a `TEXT` column in
`YYYY-MM-DD` format, which sorts and compares correctly with SQL `BETWEEN`.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter control above the "Overview" section: preset options
    (All time / Last 7 days / Last 30 days / This month / Last month) plus a
    custom start/end date range input.
  - Filter must submit as a `GET` form so the resulting URL (e.g.
    `/profile?range=30d`) is bookmarkable and shareable.
  - The currently active preset/range must be visually indicated (e.g. an
    `is-active` class on the selected option).
  - No structural changes to the stats/transactions/category sections
    themselves — they keep rendering whatever the view passes in.

## Files to change
- `app.py` — in the `profile()` view, read `range`/`start`/`end` from
  `request.args`, resolve them into a concrete `(start_date, end_date)` pair
  (or `None, None` for "all"), and pass that pair into the existing calls to
  `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`. Also pass the active filter state to the
  template so the UI can highlight the current selection.
- `database/queries.py` — add optional `start_date=None, end_date=None`
  parameters to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`. When both are `None`, behavior is unchanged
  (all-time). When set, add a parameterised `AND date BETWEEN ? AND ?`
  clause to each query.
- `templates/profile.html` — add the filter UI described above.
- `static/css/style.css` — add styles for the filter control using existing
  CSS variables (no new hex values).

## Files to create
No new files. (If date-range resolution logic — e.g. turning `this_month`
into concrete start/end dates — grows beyond a few lines, it can live as a
small helper function inside `database/queries.py` rather than a new
module.)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format dates into SQL
- Passwords hashed with werkzeug (unchanged in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles (the existing category-bar `style="width: ...%"` is
  pre-existing and out of scope — don't introduce new inline styles)
- Currency must always display as ₹ — never £ or $
- Default behavior (no query params) must exactly match today's all-time view
- Invalid, malformed, or incomplete date query params (e.g. `range=custom`
  with a missing `start`) must fall back to "all time" rather than raising
  an error
- `start`/`end` must be validated as real `YYYY-MM-DD` dates before use;
  reject anything else by falling back to "all time"
- Query helpers must still call `get_db()` internally and close the
  connection before returning

## Definition of done
- [ ] Visiting `/profile` with no query params shows the same all-time data as before this change
- [ ] Selecting "Last 7 days" or "Last 30 days" filters transactions, summary stats, and category breakdown to that window
- [ ] Selecting "This month" shows only expenses dated in the current calendar month
- [ ] Selecting "Last month" shows only expenses dated in the previous calendar month
- [ ] Entering a custom start/end date range filters correctly, inclusive of both boundary dates
- [ ] Total spent, transaction count, top category, transaction list, and category breakdown all reflect the selected range consistently
- [ ] The active filter option is visually distinguishable in the UI
- [ ] Navigating directly to `/profile?range=30d` (e.g. from a bookmark) reproduces the same filtered view
- [ ] Selecting a range with zero matching expenses shows ₹0.00 total spent, 0 transactions, and an empty category breakdown — no errors
- [ ] Submitting `range=custom` without `start`/`end` (or with garbage dates) falls back to all-time data instead of erroring
