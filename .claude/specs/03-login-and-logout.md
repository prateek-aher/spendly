# Spec: Login and Logout

## Overview

Implement session-based login and logout so a registered user can sign in
through the existing `login.html` form and sign out again. This is the second
piece of the auth flow: Step 2 (Registration) already establishes the
`session["user_id"]` convention on account creation; this step adds the
matching path for returning users (`POST /login` verifying credentials
against the `users` table) and the teardown path (`GET /logout` clearing the
session). It also updates the shared nav in `base.html` so signed-in users see
their identity and a sign-out link instead of "Sign in" / "Get started".

## Depends on

- Step 1 — Database Setup (complete). Requires `get_db()` and the `users`
  table from `database/db.py`.
- Step 2 — Registration (complete). Requires `app.secret_key`, the
  `session["user_id"]` convention, and `generate_password_hash`-hashed
  passwords already in the `users` table.

## Routes

- `GET /login` — render the login form (already exists, unchanged) — public
- `POST /login` — validate credentials, start a session, redirect to
  `/profile` — public
- `GET /logout` — clear the session, redirect to `/` — logged-in (safe to hit
  while logged out too; it should just no-op and redirect)

No changes to `/profile` or any expense routes — those remain stubs for later
steps.

## Database changes

No database changes. The `users` table (id, name, email, password_hash,
created_at) already supports login as-is; `password_hash` (via
`werkzeug.security.check_password_hash`) is all that's needed to verify
credentials.

## Templates

- **Create:** none
- **Modify:**
  - `templates/login.html` — no structural changes required; the existing
    `{% if error %}` block already supports server-side validation errors, and
    the form already posts `email`, `password` to `/login`. Only touch this
    file if a validation message needs a specific display tweak.
  - `templates/base.html` — update the `nav-links` block so that when
    `session.user_id` is set, it shows a link to `/profile` (using the
    logged-in user's name) and a "Sign out" link to `/logout`, instead of the
    current always-shown "Sign in" / "Get started" links.

## Files to change

- `app.py`:
  - Change `login()` to accept `methods=["GET", "POST"]`.
    - On `GET`: render `login.html` as today.
    - On `POST`:
      - Read `email`, `password` from `request.form`.
      - Validate both fields are non-empty; on failure re-render `login.html`
        with `error="All fields are required."`.
      - Look up the user by email via a parameterized `SELECT`.
      - If no user is found, or `check_password_hash` fails against the
        stored `password_hash`, re-render `login.html` with a generic
        `error="Invalid email or password."` (do not reveal which field was
        wrong).
      - On success: set `session["user_id"] = <user id>` and redirect to
        `/profile`.
      - Always close the DB connection.
  - Change `logout()`:
    - Remove `user_id` from the session (e.g. `session.pop("user_id", None)`
      so it's safe even if already logged out).
    - Redirect to `/` (landing page).
  - Import `check_password_hash` from `werkzeug.security` alongside the
    existing `generate_password_hash` import.

- `templates/base.html`:
  - Wrap the existing `nav-links` anchors in an `{% if session.user_id %}` /
    `{% else %}` block.
  - Logged-out branch: keep the current "Sign in" / "Get started" links
    unchanged.
  - Logged-in branch: link to `{{ url_for('profile') }}` and a
    `{{ url_for('logout') }}` link labelled "Sign out". Fetching the display
    name requires either a small DB lookup or passing the user's name into
    every render — for this step, it's acceptable to show a static
    "Profile" / "Sign out" pair without the user's name if wiring the name
    into every template is out of scope; do not add a context processor or
    other new abstraction beyond what's needed to read `session.user_id` in
    the template (session is already available in Jinja by default via
    Flask).

## Files to create

- None

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs.
- Parameterised queries only — never use string formatting/f-strings to build
  SQL.
- Passwords verified with `werkzeug.security.check_password_hash`; never
  store, log, or compare plaintext passwords.
- Use CSS variables — never hardcode hex values (only relevant if
  `login.html`, `base.html`, or their styles are touched).
- All templates extend `base.html`.
- Always close DB connections — no leaked connections across requests.
- Do not implement `/profile` or any expense routes beyond what already
  exists — those are separate steps.
- Login errors must be generic ("Invalid email or password.") and must not
  reveal whether the email exists in the system.

## Definition of done

- [ ] Visiting `/login` still renders the existing form unchanged.
- [ ] Submitting `/login` with a registered email and correct password sets a
      session cookie and redirects to `/profile`.
- [ ] Submitting `/login` with a registered email and wrong password
      re-renders `login.html` with a generic invalid-credentials error and
      does not set a session.
- [ ] Submitting `/login` with an email not in `users` re-renders `login.html`
      with the same generic invalid-credentials error (no difference in
      wording from a wrong-password case).
- [ ] Submitting `/login` with an empty email or password re-renders
      `login.html` with an appropriate error.
- [ ] Visiting `/logout` while logged in clears the session and redirects to
      `/`; the nav reverts to "Sign in" / "Get started".
- [ ] Visiting `/logout` while already logged out does not error and
      redirects to `/`.
- [ ] While logged in, the nav in `base.html` shows a link to `/profile` and
      a "Sign out" link instead of "Sign in" / "Get started".
- [ ] No SQL is built via string concatenation/formatting anywhere in the new
      code.
