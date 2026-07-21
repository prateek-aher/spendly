# Spec: Delete Expense

## Overview
This feature lets a logged-in user permanently delete an expense they own from their transaction history. It replaces the stubbed `GET /expenses/<int:id>/delete` route (currently returning `"Delete expense — coming in Step 9"`) with a real handler, and adds a "Delete" action next to the existing "Edit" action in the profile page's transaction table. Because deleting data is destructive and irreversible, the route must not be a bare `GET` link (a crawler or prefetch could trigger it) — deletion happens via a `POST` form, gated behind a client-side confirmation prompt.

## Depends on
- Step 1 — Database Setup (`expenses` table)
- Step 3 — Login and Logout (session-based auth, `require_active_user`)
- Step 5 — Backend Routes for Profile Page (`profile` route, transaction list users navigate from)
- Step 8 — Edit Expense (`get_expense_by_id` ownership-lookup helper this feature reuses; the `actions-cell` markup in `templates/profile.html` this feature extends)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense if it exists and is owned by the current user, flash a confirmation, redirect to `profile` — logged-in, owner-only

The existing stub is a bare `GET` route; it must be changed to `methods=["POST"]` only. No `GET` handler is needed — there is no standalone "delete" page, only the action itself.

## Database changes
No database changes. The existing `expenses` table (`database/db.py`) is unchanged. This feature only needs a `DELETE FROM expenses WHERE id = ? AND user_id = ?`, added as a new helper in `database/queries.py` alongside `get_expense_by_id` and `update_expense`.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — add a `POST` form with a "Delete" submit button inside the existing `actions-cell` `<td>`, next to the "Edit" link. Wire up a JS confirmation (see `static/js/main.js`) so the delete only proceeds after the user confirms.

## Files to change
- `app.py` — replace the `delete_expense(id)` stub with a real `POST`-only handler: require an active user (redirect to `login` if none), look up the expense scoped to `user_id` via `get_expense_by_id`, flash "Expense not found." and redirect to `profile` if it's missing/not owned, otherwise call the new `delete_expense_by_id` query helper, flash a success message (e.g. `"Deleted ₹{amount:.2f} from {category}."`), and redirect to `profile`.
- `database/queries.py` — add `delete_expense_by_id(expense_id, user_id)`: a parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`, following the same connect/execute/commit/close-in-finally shape as `update_expense`.
- `templates/profile.html` — in the `actions-cell` `<td>` (around the existing `edit_expense` link), add a small `<form method="POST" action="{{ url_for('delete_expense', id=tx.id) }}">` containing a submit button styled as a destructive action (e.g. `btn-ghost btn-danger`), with a `data-confirm` attribute holding the confirmation copy (e.g. `Delete this ₹{{ "%.2f"|format(tx.amount) }} {{ tx.category }} expense?`).
- `static/js/main.js` — add a `DOMContentLoaded` listener that attaches a `submit` handler to every form with a `data-confirm` attribute, calling `window.confirm(form.dataset.confirm)` and calling `event.preventDefault()` if the user cancels. Keep it generic (not delete-specific) so any future destructive form can reuse the same `data-confirm` convention.
- `static/css/style.css` — add a `.btn-danger` variant (using the existing `--danger` CSS variable for text/border, matching the visual weight of `.btn-ghost`) so the delete button reads as destructive without hardcoding hex values.

## Files to create
None — no new templates or modules; add the query helper to the existing `database/queries.py` and the confirm behavior to the existing `static/js/main.js`.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- The `DELETE`/ownership lookup must always filter by both `id` and the session's `user_id` — a user must never be able to delete another user's expense by guessing an id in the URL. If the expense doesn't exist or isn't owned by the current user, redirect to `profile` (with a flash message) rather than raising a raw 404 or leaking whether the id exists for another user.
- The route must only accept `POST` (no `GET` handler) — deleting data must never be reachable via a plain link/prefetch.
- The confirmation prompt is client-side only (`window.confirm` via the `data-confirm` JS hook) — it is a UX safeguard, not a security control. The server-side ownership check is what actually protects the data.
- Keep the delete form visually and structurally consistent with the existing "Edit" link in the same `actions-cell` (same cell, same row, small footprint) — don't introduce a separate modal/dialog component for this step.

## Definition of done
- [ ] Visiting `POST /expenses/<id>/delete` while logged out redirects to `/login`
- [ ] Submitting the delete form for an expense owned by another user redirects to `/profile` with a "not found" flash, and the other user's row is untouched in the DB
- [ ] Clicking "Delete" on your own expense shows a browser confirmation prompt before any request is sent
- [ ] Cancelling the confirmation prompt sends no request and leaves the expense in place
- [ ] Confirming the prompt removes the row from the `expenses` table (verify via DB query) and redirects to `/profile` with a success flash message
- [ ] The deleted expense no longer appears in the profile page's transaction list, and summary stats (total spent, expense count, category breakdown) reflect its removal
- [ ] `GET /expenses/<id>/delete` (e.g. typed directly in the browser) does not delete anything — returns a 405 or otherwise fails safely
