import os
import re
import sqlite3

import pytest
from werkzeug.security import check_password_hash

import database.db as db_module
from database.db import get_db, init_db, seed_db

# Fixed category list per spec section 10 ("Categories (Fixed List)").
SPEC_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# ---------- helpers ----------

def _table_columns(conn, table):
    """Return {column_name: (type, notnull, pk)} via PRAGMA table_info."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"]: (r["type"], r["notnull"], r["pk"]) for r in rows}


def _fk_list(conn, table):
    return conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()


# ================================================================
# get_db()
# ================================================================

def test_get_db_returns_dict_like_row_access(test_db_path):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Row Test", "rowtest@example.com", "hash"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("rowtest@example.com",)
    ).fetchone()
    conn.close()

    # Dictionary-like access by column name (sqlite3.Row behaviour).
    assert row["name"] == "Row Test"
    assert row["email"] == "rowtest@example.com"


def test_get_db_enables_foreign_key_enforcement(test_db_path):
    conn = get_db()
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    conn.close()
    # PRAGMA foreign_keys should report ON (1) for every connection returned.
    assert result[0] == 1


# ================================================================
# init_db()
# ================================================================

def test_init_db_creates_users_table_with_spec_columns(test_db_path):
    conn = get_db()
    columns = _table_columns(conn, "users")
    conn.close()

    assert set(columns.keys()) == {"id", "name", "email", "password_hash", "created_at"}
    assert columns["id"][2] == 1  # primary key
    assert columns["name"][1] == 1  # NOT NULL
    assert columns["email"][1] == 1  # NOT NULL
    assert columns["password_hash"][1] == 1  # NOT NULL


def test_init_db_creates_expenses_table_with_spec_columns(test_db_path):
    conn = get_db()
    columns = _table_columns(conn, "expenses")
    conn.close()

    assert set(columns.keys()) == {
        "id", "user_id", "amount", "category", "date", "description", "created_at",
    }
    assert columns["id"][2] == 1  # primary key
    assert columns["user_id"][1] == 1  # NOT NULL
    assert columns["amount"][1] == 1  # NOT NULL
    assert columns["amount"][0].upper() == "REAL"
    assert columns["category"][1] == 1  # NOT NULL
    assert columns["date"][1] == 1  # NOT NULL
    # description is nullable per spec.
    assert columns["description"][1] == 0


def test_init_db_expenses_user_id_is_foreign_key_to_users(test_db_path):
    conn = get_db()
    fks = _fk_list(conn, "expenses")
    conn.close()

    assert len(fks) >= 1
    fk = fks[0]
    assert fk["table"] == "users"
    assert fk["from"] == "user_id"
    assert fk["to"] == "id"


def test_init_db_is_idempotent_no_error_on_repeat_calls(test_db_path):
    # test_db_path fixture already ran init_db() once; calling again must not raise.
    init_db()
    init_db()

    conn = get_db()
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"users", "expenses"}.issubset(tables)


def test_database_file_exists_after_init_db(test_db_path):
    # Definition of done: "Database file is created on app startup".
    assert os.path.exists(test_db_path)
    assert os.path.getsize(test_db_path) > 0


# ================================================================
# seed_db()
# ================================================================

def test_seed_db_creates_exactly_one_demo_user(test_db_path):
    seed_db()

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["name"] == "Prateek"


def test_seed_db_demo_password_is_hashed_not_plaintext(test_db_path):
    seed_db()

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    conn.close()

    assert row["password_hash"] != "prateek123"
    assert check_password_hash(row["password_hash"], "prateek123")


def test_seed_db_creates_eight_sample_expenses(test_db_path):
    seed_db()

    conn = get_db()
    demo_user = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (demo_user["id"],)
    ).fetchall()
    conn.close()

    assert len(expenses) == 8


def test_seed_db_expenses_all_linked_to_demo_user(test_db_path):
    seed_db()

    conn = get_db()
    demo_user = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    total_expenses = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    linked_expenses = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (demo_user["id"],)
    ).fetchone()["c"]
    conn.close()

    # Every seeded expense belongs to the demo user (no orphans/other users).
    assert total_expenses == linked_expenses == 8


def test_seed_db_covers_at_least_one_expense_per_category(test_db_path):
    seed_db()

    conn = get_db()
    demo_user = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    categories_used = {
        r["category"]
        for r in conn.execute(
            "SELECT DISTINCT category FROM expenses WHERE user_id = ?",
            (demo_user["id"],),
        ).fetchall()
    }
    conn.close()

    # Spec: "At least one expense per category" across the fixed category list.
    for category in SPEC_CATEGORIES:
        assert category in categories_used


def test_seed_db_expense_dates_use_yyyy_mm_dd_format(test_db_path):
    seed_db()

    conn = get_db()
    dates = [r["date"] for r in conn.execute("SELECT date FROM expenses").fetchall()]
    conn.close()

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    assert len(dates) == 8
    for d in dates:
        assert date_pattern.match(d), f"date {d!r} is not in YYYY-MM-DD format"


def test_seed_db_does_not_duplicate_on_repeated_calls(test_db_path):
    seed_db()
    seed_db()
    seed_db()

    conn = get_db()
    user_count = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()["c"]
    expense_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    conn.close()

    assert user_count == 1
    assert expense_count == 8


def test_seed_db_returns_early_if_users_table_already_has_data(test_db_path):
    # Spec: "Checks if users table already contains data - If yes -> return early".
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Pre-existing", "preexisting@example.com", "hash"),
    )
    conn.commit()
    conn.close()

    seed_db()

    conn = get_db()
    demo_user = conn.execute(
        "SELECT * FROM users WHERE email = ?", ("prateek@spendly.com",)
    ).fetchone()
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    conn.close()

    assert demo_user is None
    assert total_users == 1


# ================================================================
# Constraints: unique email
# ================================================================

def test_duplicate_user_email_raises_integrity_error(test_db_path):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("First", "dupe@example.com", "hash1"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Second", "dupe@example.com", "hash2"),
        )
    conn.close()


# ================================================================
# Constraints: foreign key on expenses.user_id
# ================================================================

def test_insert_expense_with_nonexistent_user_id_raises_integrity_error(test_db_path):
    conn = get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (999999, 10.00, "Food", "2026-07-01", "orphan expense"),
        )
    conn.close()


# ================================================================
# amount stored/handled as float (REAL)
# ================================================================

def test_expense_amount_is_stored_and_returned_as_float(test_db_path):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Amount Tester", "amounttest@example.com", "hash"),
    )
    uid = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("amounttest@example.com",)
    ).fetchone()["id"]
    # Insert as a plain int to confirm the REAL column still yields a float back.
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, 10, "Food", "2026-07-01", "int amount in"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT amount FROM expenses WHERE user_id = ?", (uid,)
    ).fetchone()
    conn.close()

    assert isinstance(row["amount"], float)
    assert row["amount"] == 10.0


def test_seed_db_expense_amounts_are_floats(test_db_path):
    seed_db()

    conn = get_db()
    amounts = [r["amount"] for r in conn.execute("SELECT amount FROM expenses").fetchall()]
    conn.close()

    assert len(amounts) == 8
    for amount in amounts:
        assert isinstance(amount, float)
