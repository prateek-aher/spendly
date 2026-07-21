# Spec: Edit Expense

## Overview
This feature lets a logged-in user edit an existing expense they own. It reuses the same form layout and validation rules established in Step 7 (Add Expense), but pre-fills the form with the expense's current values and updates the existing row instead of inserting a new one. The route currently stubbed at `GET /expenses/<int:id>/edit` (returning `"Edit expense — coming in Step 8"`) is replaced with a real `GET`/`POST` handler.

## Depends on
- Step 1 — Database Setup (`expenses` table)
- Step 3 — Login and Logout (session-based auth, `require_active_user`)
- Step 5 — Backend Routes for Profile Page (`profile` route, transaction list users navigate from)
- Step 7 — Add Expense (validation rules, `expenses_add.html` layout/category picker/date-quick-picks JS this template reuses, `CATEGORIES`)

## Routes
- `GET /expenses/<int:id>/edit` — show the edit form pre-filled with the expense's current values — logged-in, owner-only
- `POST /expenses/<int:id>/edit` — validate and apply the update, then redirect to profile — logged-in, owner-only

Both methods live on the same `edit_expense(id)` view (replacing the current stub), matching the `add_expense` pattern of branching on `request.method`.

## Database changes
No database changes. The existing `expenses` table (`database/db.py`) already has every column this feature needs (`amount`, `category`, `date`, `description`). This feature only needs a `SELECT ... WHERE id = ? AND user_id = ?` (ownership lookup) and an `UPDATE` statement — both belong in `database/queries.py` alongside the other pure DB helpers, not new schema.

## Templates
- **Create:** none
- **Modify:** `templates/expenses_add.html` — reuse as-is for edit and add a lightweight `mode` distinction (see Files to change), or clone its markup into a new `templates/expenses_edit.html`. Recommend reusing the existing template with a `mode="edit"` context variable rather than duplicating the form (see Rules for implementation).

## Files to change
- `app.py` — replace the `edit_expense(id)` stub with a real `GET`/`POST` handler: look up the expense scoped to the logged-in user, 404/redirect if not found or not owned, pre-fill form on `GET`, validate and `UPDATE` on `POST` (reusing the same amount/category/date/description checks as `add_expense`), flash a success message, redirect to `profile`.
- `database/queries.py` — add `get_expense_by_id(expense_id, user_id)` (returns the row only if it belongs to `user_id`, else `None`) and `update_expense(expense_id, user_id, amount, category, date, description)` (parameterised `UPDATE ... WHERE id = ? AND user_id = ?`).
- `templates/expenses_add.html` — adapt to double as the edit form: parameterise the page title/heading ("Add an expense" vs "Edit expense"), form `action` (`url_for('add_expense')` vs `url_for('edit_expense', id=expense.id)`), submit button label ("Add expense" vs "Save changes"), and drop the "Add another expense" checkbox in edit mode (it only makes sense for add).

## Files to create
None — no new templates or modules; add the query helpers to the existing `database/queries.py`.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- The `UPDATE`/ownership `SELECT` must always filter by both `id` and the session's `user_id` — a user must never be able to edit another user's expense by guessing an id in the URL. If the expense doesn't exist or isn't owned by the current user, redirect to `profile` (with a flash message) rather than raising a raw 404 or leaking whether the id exists for another user.
- Reuse the exact amount/category/date/description validation logic from `add_expense` (see the `# Amount/category/date/description validation ... extract a shared helper once that route exists` comment in `app.py` — this is the moment to extract that shared validation helper rather than copy-pasting it a second time).
- Keep the edit route's `GET` pre-fill and `POST` re-render-with-errors behavior consistent with `add_expense`'s `form_values` pattern so the template doesn't need separate branches for add vs. edit error states.

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by another user redirects to `/profile` (not a 500 or raw 404)
- [ ] Visiting `/expenses/<id>/edit` for your own expense shows the form pre-filled with its current amount, category, date, and description
- [ ] Submitting the edit form with a valid change updates the row in `expenses` (verify the amount/category/date/description actually changed in the DB) and redirects to `/profile` with a success flash message
- [ ] Submitting an invalid amount (e.g. `0`, `-5`, or non-numeric) re-renders the edit form with an inline error and preserves the other entered values
- [ ] Submitting an invalid category (not in `CATEGORIES`) re-renders the edit form with an inline error
- [ ] Submitting a future date re-renders the edit form with an inline error
- [ ] Submitting a description over 200 characters re-renders the edit form with an inline error
- [ ] The edit form has no "Add another expense" checkbox
