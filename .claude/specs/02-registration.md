# Spec: Registration

## Overview

Implement user registration so a visitor can create a Spendly account through the
existing `register.html` form. This is the first piece of real authentication logic
in the app: it turns the static `/register` page into a working `GET`/`POST` route
that validates input, hashes the password, inserts a new row into `users`, and On success, the user is shown a success message and then signs the new user in immediately via a Flask session. All later steps (login, logout,
profile, expense CRUD) depend on the session convention established here.

## Depends on

- Step 1 — Database Setup (complete). Requires `get_db()`, `init_db()`, and the
  `users` table from `database/db.py`.

## Routes

- `GET /register` — render the registration form (already exists, unchanged) — public
- `POST /register` — validate input, create the user, start a session, redirect to
  `/profile` — public

No changes to `/login`, `/logout`, or any expense routes — those remain stubs for
later steps.

## Database changes

No database changes. `users` table (id, name, email, password_hash, created_at)
already supports registration as-is. The `email` column's `UNIQUE NOT NULL`
constraint is what backs the duplicate-email check.

## Templates

- **Create:** none
- **Modify:** `templates/register.html` — no structural changes required; the
  existing `{% if error %}` block already supports server-side validation errors, and
  the form already posts `name`, `email`, `password` to `/register`. Only touch this
  file if a validation message needs a specific display tweak.

## Files to change

- `app.py`:
  - Add `app.secret_key` (read from an environment variable, e.g. `SECRET_KEY`, with
    a hardcoded fallback for local dev) so `flask.session` can be used.
  - Import `session` and `redirect`/`url_for` from `flask`, and `get_db` (already
    imported) plus `generate_password_hash` from `werkzeug.security`.
  - Change `register()` to accept `methods=["GET", "POST"]`.
    - On `GET`: render `register.html` as today.
    - On `POST`:
      - Read `name`, `email`, `password` from `request.form`.
      - Validate: all fields non-empty, email contains `@`, password length >= 8.
      - On validation failure: re-render `register.html` with `error` set, form
        values preserved via template vars if desired.
      - Check for existing email via a parameterized `SELECT`. If found, re-render
        with `error="An account with this email already exists."`.
      - Hash the password with `generate_password_hash`.
      - Insert the new user with a parameterized `INSERT`.
      - Set `session["user_id"] = <new user id>`.
      - Redirect to `/profile` (Step 4's stub page — reachable now, but its real
        implementation comes later).

## Files to create

- None

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs.
- Parameterised queries only — never use string formatting/f-strings to build SQL.
- Passwords hashed with `werkzeug.security.generate_password_hash`; never store or
  log plaintext passwords.
- Use CSS variables — never hardcode hex values (only relevant if `register.html` or
  its styles are touched).
- All templates extend `base.html`.
- Always close DB connections (or use a pattern consistent with `database/db.py`'s
  existing `get_db()` usage) — no leaked connections across requests.
- Do not implement `/login`, `/logout`, or `/profile` beyond what already exists —
  those are separate steps.

## Definition of done

- [ ] Visiting `/register` still renders the existing form unchanged.
- [ ] Submitting the form with a new name/email/password creates a row in `users`
      with a hashed (non-plaintext) password.
- [ ] After successful registration, the browser is redirected to `/profile` and a
      session cookie is set.
- [ ] Submitting with an email that already exists in `users` re-renders
      `register.html` with an error message and does not create a duplicate row.
- [ ] Submitting with an empty name, invalid email, or password under 8 characters
      re-renders `register.html` with an appropriate error and does not create a row.
- [ ] Restarting the app (`python app.py`) does not error and does not re-seed or
      duplicate the demo user.
- [ ] No SQL is built via string concatenation/formatting anywhere in the new code.
