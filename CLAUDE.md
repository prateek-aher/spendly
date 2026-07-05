# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Spendly" is a Flask expense-tracker app built as a **step-by-step learning project**. Marketing/static pages (landing, terms, privacy, login/register forms) are already built out, but the core application logic — database layer, auth, and expense CRUD — is intentionally left as stubs for the student to implement incrementally. Comments like `# Students will write this file in Step 1 — Database Setup` and route bodies like `return "Add expense — coming in Step 7"` in `app.py` mark unimplemented steps; don't treat these as bugs to silently fix unless the user is actively working on that step.

## Commands

```bash
# Setup (venv already exists at ./venv)
source venv/bin/activate
pip install -r requirements.txt

# Run the dev server (http://localhost:5001)
python app.py

# Run tests
pytest
pytest path/to/test_file.py::test_name   # single test
```

There is no build/lint tooling configured (no linter, no frontend bundler) — this is plain Flask + Jinja + vanilla CSS/JS.

## Architecture

- `app.py` — single Flask application entrypoint. All routes are defined directly here (no blueprints). Runs on port 5001 with debug mode on.
- `database/db.py` — intended to hold `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (idempotent `CREATE TABLE IF NOT EXISTS` schema setup), and `seed_db()` (sample data for development). Currently a stub.
- `templates/` — Jinja2 templates, all extending `templates/base.html`, which defines the shared `<nav>`/`<footer>` chrome and the `title` / `head` / `content` / `scripts` blocks pages override.
- `static/css/style.css` — single global stylesheet for all pages (no preprocessor, no per-page CSS files).
- `static/js/main.js` — currently a placeholder; JS is added here as features are built rather than per-page script files.

Since there are no blueprints, models, or ORM yet, expect the eventual data layer (SQLite via `database/db.py`) and any auth/session logic to be wired directly into `app.py`'s route handlers as the tutorial steps progress.
