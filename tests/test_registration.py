from werkzeug.security import check_password_hash

from database.db import get_db


# ---------- helpers ----------

def _get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row


def _count_users_with_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row["c"]


# ---------- GET /register ----------

def test_get_register_renders_form(client):
    resp = client.get("/register")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    # The existing form posts name, email, password.
    assert 'name="name"' in body
    assert 'name="email"' in body
    assert 'name="password"' in body


# ---------- POST /register — happy path ----------

def test_post_register_creates_user_row(client):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "password123"},
    )
    row = _get_user_by_email("alice@example.com")
    assert row is not None
    assert row["name"] == "Alice"


def test_post_register_stores_hashed_password_not_plaintext(client):
    client.post(
        "/register",
        data={"name": "Bob", "email": "bob@example.com", "password": "password123"},
    )
    row = _get_user_by_email("bob@example.com")
    assert row is not None
    # Password must be hashed with werkzeug, never stored/kept as plaintext.
    assert row["password_hash"] != "password123"
    assert check_password_hash(row["password_hash"], "password123")


def test_post_register_redirects_to_profile(client):
    resp = client.post(
        "/register",
        data={"name": "Carol", "email": "carol@example.com", "password": "password123"},
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_post_register_sets_session(client):
    client.post(
        "/register",
        data={"name": "Dave", "email": "dave@example.com", "password": "password123"},
    )
    row = _get_user_by_email("dave@example.com")
    with client.session_transaction() as sess:
        assert sess.get("user_id") == row["id"]


# ---------- POST /register — duplicate email ----------

def test_post_register_duplicate_email_shows_error(client):
    # The demo user (demo@spendly.com) is created by seed_db().
    resp = client.post(
        "/register",
        data={"name": "Someone", "email": "demo@spendly.com", "password": "password123"},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "An account with this email already exists." in body


def test_post_register_duplicate_email_no_duplicate_row(client):
    client.post(
        "/register",
        data={"name": "Someone", "email": "demo@spendly.com", "password": "password123"},
    )
    assert _count_users_with_email("demo@spendly.com") == 1


# ---------- POST /register — validation failures ----------

def test_post_register_empty_name_rejected(client):
    resp = client.post(
        "/register",
        data={"name": "", "email": "noname@example.com", "password": "password123"},
    )
    body = resp.get_data(as_text=True)
    # Re-renders the form (200) rather than redirecting; shows an error.
    assert resp.status_code == 200
    assert "auth-error" in body
    assert _count_users_with_email("noname@example.com") == 0


def test_post_register_invalid_email_rejected(client):
    resp = client.post(
        "/register",
        data={"name": "NoAt", "email": "invalid-email", "password": "password123"},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "auth-error" in body
    assert _count_users_with_email("invalid-email") == 0


def test_post_register_short_password_rejected(client):
    resp = client.post(
        "/register",
        data={"name": "Shorty", "email": "shorty@example.com", "password": "short"},
    )
    body = resp.get_data(as_text=True)
    # Password under 8 characters must be rejected.
    assert resp.status_code == 200
    assert "auth-error" in body
    assert _count_users_with_email("shorty@example.com") == 0


def test_post_register_boundary_password_length_accepted(client):
    # Spec: password length >= 8, so exactly 8 chars is valid.
    resp = client.post(
        "/register",
        data={"name": "Edge", "email": "edge@example.com", "password": "12345678"},
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    assert _count_users_with_email("edge@example.com") == 1


def test_post_register_failure_creates_no_session(client):
    client.post(
        "/register",
        data={"name": "", "email": "nosess@example.com", "password": "password123"},
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None