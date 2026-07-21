# Spendly

A personal expense tracker built with Flask — a step-by-step learning project covering database setup, auth, and expense CRUD.

**Live demo:** _[add your Render URL here once deployed]_

## Tech stack

- Flask (Python)
- SQLite
- Jinja2 templates, vanilla CSS/JS (no frontend framework)

## Running locally

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

App runs at `http://localhost:5001`.

## Deployment notes

This app is deployed on [Render's free tier](https://render.com), which is well suited for a low-traffic demo like this one but comes with a couple of trade-offs worth knowing before you click the live demo link above:

- **Cold starts.** Free Render services spin down after ~15 minutes of no traffic and spin back up on the next request. If nobody's visited recently, the first load can take **30–60 seconds** while the container boots. Refreshing or waiting it out is normal — it's not broken.
- **Data doesn't persist across sleep cycles.** Render's free tier has no persistent disk, and a wake-from-sleep counts as a fresh container start. That means any expenses added during a visit are reset once the app goes back to sleep — every visitor effectively gets a clean slate. This is expected behavior for this demo, not a bug.

These trade-offs are acceptable here because the goal is a free, always-available link rather than a production deployment with durable data. If you want to explore persistent data locally, clone the repo and run it yourself instead.
