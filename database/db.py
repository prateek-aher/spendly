import sqlite3
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

DB_PATH = "spendly.db"  # matches .gitignore entry

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    if existing["c"] > 0:
        conn.close()
        return

    password_hash = generate_password_hash("prateek123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Prateek", "prateek@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = datetime.now()
    sample_expenses = [
        (45.50, "Food", (today - timedelta(days=1)).strftime("%Y-%m-%d"), "Groceries"),
        (
            12.00,
            "Transport",
            (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            "Bus pass",
        ),
        (
            89.99,
            "Bills",
            (today - timedelta(days=3)).strftime("%Y-%m-%d"),
            "Electricity bill",
        ),
        (25.00, "Health", (today - timedelta(days=4)).strftime("%Y-%m-%d"), "Pharmacy"),
        (
            15.00,
            "Entertainment",
            (today - timedelta(days=5)).strftime("%Y-%m-%d"),
            "Movie ticket",
        ),
        (
            60.00,
            "Shopping",
            (today - timedelta(days=6)).strftime("%Y-%m-%d"),
            "New shoes",
        ),
        (8.75, "Other", (today - timedelta(days=7)).strftime("%Y-%m-%d"), "Misc"),
        (30.00, "Food", (today - timedelta(days=8)).strftime("%Y-%m-%d"), "Restaurant"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, *e) for e in sample_expenses],
    )
    conn.commit()
    conn.close()
