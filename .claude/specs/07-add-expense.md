# Spec: Add Expense

## Overview
Step 7 turns the `/expenses/add` stub into a real form so a logged-in user
can record a new expense. This is the first write path into the `expenses`
table since seeding — until now the app has been read-only (profile stats,
transaction list, category breakdown). The user fills in amount, category,
date, and an optional description; on success the expense is saved. They
can either return to their profile with the new transaction visible, or
opt into a fast multi-entry flow ("Add another expense") that keeps them
on the form for consecutive entries.

## Depends on
- Step 1: Database setup (`expenses` table exists with `user_id`, `amount`,
  `category`, `date`, `description` columns)
- Step 3: Login and logout (`session["user_id"]` is the auth guard pattern)
- Step 4: Profile page static UI (`profile.html` layout exists)
- Step 5: Backend routes for profile page (`database/queries.py` exists
  alongside `database/db.py`; live `/profile` route exists)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in
  - If `session["keep_add_another"]` is set (popped on read), the "Add
    another expense" checkbox on the rendered form starts checked.
- `POST /expenses/add` — validate and insert the new expense — logged-in
  - Redirects to `/profile` on success, unless the submitted form included
    a checked `add_another` checkbox, in which case it sets
    `session["keep_add_another"] = True` and redirects back to
    `GET /expenses/add` instead (fast multi-entry loop). The "sticky
    checkbox" state is carried via the session rather than a URL query
    param, so there's a single source of truth for it.

Both replace the current `@app.route("/expenses/add")` stub in `app.py`,
which must gain `methods=["GET", "POST"]` and the same
`if not session.get("user_id"): return redirect(url_for("login"))` guard
used by `profile()` and `analytics()`, plus the same
`get_user_by_id(...)`-backed stale-session check `profile()` uses (in case
the session's user was deleted after login).

## Database changes
No database changes. The existing `expenses` table
(`database/db.py`) already has every column this form needs:
`user_id`, `amount`, `category`, `date`, `description`. `category` is a free
`TEXT` column with no `CHECK` constraint, so validation happens in the route
against the existing `CATEGORIES` list in `database/db.py`.

## Templates
- **Create:** `templates/expenses_add.html` — form with fields:
  - Amount (`number`, `step="0.01"`, `min="0.01"`, required), rendered
    with a fixed `₹` prefix inside the input itself (not just the label)
  - Category — a grid of colored pill buttons (one radio input + styled
    label per category, radio visually hidden via the standard sr-only
    clip technique, not a native `<select>`), reusing the existing
    `.category-badge-*` colors from the transactions table so each pill
    matches its color elsewhere in the app. A native `<select>` was
    considered but dropped: `<option>` background colors aren't reliably
    stylable across browsers.
  - Date (`date`, required, defaults to today), with "Today" / "Yesterday"
    quick-pick buttons above it (styled with the existing `.filter-pill`
    class) that fill in the date without a page reload
  - Description (`text`, optional, `maxlength="200"`)
  - An "Add another expense after this one" checkbox — when checked at
    submit time, a successful save redirects back to this same form
    (pre-checked) instead of `/profile`
  - Submit button ("Add expense") and a "Cancel" link back to `/profile`
  - On validation error, re-render this template with an `error` message,
    the submitted values preserved (same pattern as `register.html` /
    `login.html`), and focus moved to the first invalid field
- **Modify:** `templates/profile.html` — add an "Add expense" link/button
  (e.g. in `.profile-header`) pointing to `{{ url_for('add_expense') }}`,
  styled with the existing `.btn-primary` class

## Files to change
- `app.py` — replace the `add_expense` stub with a real `GET`/`POST`
  handler:
  - Guard with the login-required redirect
  - On `GET`, render `expenses_add.html` with `categories=CATEGORIES`,
    today's date as the default, and the "Add another" checkbox state
    seeded from the `keep_add_another` query param
  - On `POST`, read `amount`, `category`, `date`, `description`,
    `add_another` from `request.form`, validate them (see rules below),
    insert via a parameterised `INSERT INTO expenses (...)` through
    `get_db()`, commit, close the connection, flash a success message, and
    redirect to `url_for("profile")` — or back to
    `url_for("add_expense", keep_add_another=1)` if `add_another` was
    checked
  - On a validation error, also pass an `error_field` value identifying
    which field failed, so the template can focus it
- `templates/profile.html` — add the "Add expense" entry point described
  above
- `static/css/style.css` — styles for the category pill grid, the ₹
  input prefix, the quick date-pick buttons, and the "Add another"
  checkbox
- `static/js/main.js` — the quick date-pick button handlers and focus
  management on validation errors

## Files to create
- `templates/expenses_add.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format form values into SQL
- Passwords hashed with werkzeug (unchanged in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $
- `amount` must be validated server-side as a positive, finite number
  (reject `0`, negative, non-numeric, `NaN`, and `Infinity` input) before
  insert, and normalized to 2 decimal places (`round(amount, 2)`) before
  the positivity/finiteness check and the insert, to avoid float artifacts
  like `19.999999999998`
- `category` must be validated against the `CATEGORIES` list in
  `database/db.py` — reject anything else
- `date` must be validated as a real `YYYY-MM-DD` date before insert
  (reuse `parse_iso_date` from `database/queries.py`, shared with the
  profile date filter); do not allow future-dated expenses. The
  future-date check compares against the server's local clock — this
  assumes the server and client share a timezone, which holds for this
  app's local single-machine dev deployment but would need revisiting for
  a multi-timezone production deployment
- `description` is optional — store `NULL`/empty, never crash if omitted;
  capped at 200 characters, enforced both via `maxlength` on the input and
  a server-side length check (client-side `maxlength` alone is not
  trustworthy since it can be bypassed by posting directly)
- Validation failures must re-render the form with a clear `error`
  message, not raise a 500 — this includes unexpected DB errors on
  insert (e.g. a constraint violation or locked database), which must be
  caught and shown as a generic error rather than crashing
- The insert must always use the logged-in user's `session["user_id"]` —
  never a value taken from the form
- The category picker is a grid of colored pill buttons (radio + label),
  a different interaction pattern from the plain submit-button pills used
  by the profile page's date filter (`.filter-pill`). This divergence is
  a known, accepted inconsistency for now — a future design-system pass
  should reconcile the two "pill selector" idioms into one, but doing so
  now would mean redesigning a working feature for a cosmetic concern

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount,
      category, date (defaulted to today), and description fields
- [ ] Submitting a valid expense inserts a row into `expenses` for the
      current user and redirects to `/profile`
- [ ] The newly added expense appears in the profile page's recent
      transactions and is reflected in the summary stats and category
      breakdown
- [ ] Submitting a negative, zero, or non-numeric amount shows an error and
      does not insert a row
- [ ] Submitting a category outside the fixed `CATEGORIES` list shows an
      error and does not insert a row
- [ ] Submitting a malformed or future date shows an error and does not
      insert a row
- [ ] Submitting with description left blank still succeeds
- [ ] Submitting a description longer than 200 characters shows an error,
      does not insert a row, and focus lands on the description field
- [ ] Submitting an amount like `19.999999999998` inserts a row with the
      amount rounded to 2 decimal places
- [ ] The profile page has a working "Add expense" link that opens the form
- [ ] Checking "Add another expense" before submitting a valid expense
      redirects back to `/expenses/add` with the checkbox still checked,
      instead of `/profile`
- [ ] On a validation error, keyboard focus lands on the field that failed
      validation (amount, category, date, or description)
