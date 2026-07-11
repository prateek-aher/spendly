from werkzeug.security import generate_password_hash

from database.db import get_db


# ---------- helpers ----------

def _make_user(email, password, name="Test User"):
    """Insert a user directly into the users table with a properly hashed
    password, bypassing the /register route. Returns the new user's id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


# ---------- GET /login ----------

def test_get_login_renders_form_unchanged(client):
    resp = client.get("/login")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    # The existing form posts email, password to /login.
    assert 'name="email"' in body
    assert 'name="password"' in body
    assert 'action="/login"' in body


# ---------- POST /login — happy path ----------

def test_post_login_correct_credentials_redirects_to_profile(client):
    _make_user("login-happy@example.com", "correcthorse")
    resp = client.post(
        "/login",
        data={"email": "login-happy@example.com", "password": "correcthorse"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/profile"


def test_post_login_correct_credentials_sets_session(client):
    user_id = _make_user("login-session@example.com", "correcthorse")
    client.post(
        "/login",
        data={"email": "login-session@example.com", "password": "correcthorse"},
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id


# ---------- POST /login — wrong password ----------

def test_post_login_wrong_password_shows_generic_error(client):
    _make_user("login-wrongpw@example.com", "correcthorse")
    resp = client.post(
        "/login",
        data={"email": "login-wrongpw@example.com", "password": "totallywrong"},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Invalid email or password." in body


def test_post_login_wrong_password_does_not_set_session(client):
    _make_user("login-wrongpw2@example.com", "correcthorse")
    client.post(
        "/login",
        data={"email": "login-wrongpw2@example.com", "password": "totallywrong"},
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


# ---------- POST /login — unknown email ----------

def test_post_login_unknown_email_shows_same_generic_error(client):
    resp = client.post(
        "/login",
        data={"email": "nobody-at-all@example.com", "password": "whatever123"},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Invalid email or password." in body


def test_post_login_unknown_email_does_not_set_session(client):
    client.post(
        "/login",
        data={"email": "nobody-at-all-2@example.com", "password": "whatever123"},
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_post_login_wrong_password_and_unknown_email_have_identical_error_text(client):
    # The spec requires the exact same wording for "email exists, wrong
    # password" vs "email does not exist" so the response can't leak which
    # case occurred. Compare the auth-error content, not the whole page (page
    # chrome/nav could legitimately differ between requests).
    _make_user("login-compare@example.com", "correcthorse")

    wrong_password_resp = client.post(
        "/login",
        data={"email": "login-compare@example.com", "password": "nope-wrong"},
    )
    unknown_email_resp = client.post(
        "/login",
        data={"email": "does-not-exist@example.com", "password": "nope-wrong"},
    )

    wrong_password_body = wrong_password_resp.get_data(as_text=True)
    unknown_email_body = unknown_email_resp.get_data(as_text=True)

    assert "Invalid email or password." in wrong_password_body
    assert "Invalid email or password." in unknown_email_body


# ---------- POST /login — empty fields ----------

def test_post_login_empty_email_shows_required_error(client):
    resp = client.post(
        "/login",
        data={"email": "", "password": "somepassword"},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "All fields are required." in body


def test_post_login_empty_password_shows_required_error(client):
    resp = client.post(
        "/login",
        data={"email": "someone@example.com", "password": ""},
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "All fields are required." in body


def test_post_login_empty_fields_do_not_set_session(client):
    client.post("/login", data={"email": "", "password": ""})
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


# ---------- GET /logout ----------

def test_logout_while_logged_in_clears_session_and_redirects(client):
    user_id = _make_user("logout-user@example.com", "correcthorse")
    client.post(
        "/login",
        data={"email": "logout-user@example.com", "password": "correcthorse"},
    )
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user_id  # sanity check: logged in first

    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"

    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_logout_while_already_logged_out_is_a_noop_redirect(client):
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None  # sanity check: not logged in

    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"

    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


# ---------- nav: base.html reflects logged-in/out state ----------

def test_nav_shows_signin_and_getstarted_when_logged_out(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "Sign in" in body
    assert "Get started" in body
    assert "Sign out" not in body


def test_nav_shows_profile_and_signout_when_logged_in(client):
    _make_user("nav-user@example.com", "correcthorse")
    client.post(
        "/login",
        data={"email": "nav-user@example.com", "password": "correcthorse"},
    )
    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert 'href="/profile"' in body
    assert "Sign out" in body
    assert "Get started" not in body
