import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    FILTER_PRESETS,
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    normalize_range,
    paginate,
    resolve_date_range,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

TRANSACTIONS_PER_PAGE = 10

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        if "@" not in email:
            return render_template("register.html", error="Please enter a valid email address.")

        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.")

        conn = get_db()
        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user:
            conn.close()
            return render_template("register.html", error="An account with this email already exists.")

        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        flash("Account created! Redirecting...", "success")
        session["user_id"] = user_id
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="All fields are required.")

        conn = get_db()
        user = conn.execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            conn.close()
            return render_template("login.html", error="Invalid email or password.")

        conn.close()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    user_record = get_user_by_id(user_id)
    if user_record is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    name_parts = user_record["name"].split()
    initials = "".join(part[0].upper() for part in name_parts[:2])

    user = {
        "name": user_record["name"],
        "email": user_record["email"],
        "member_since": user_record["member_since"],
        "initials": initials,
    }

    range_value = normalize_range(request.args.get("range", "all"))
    start_param = request.args.get("start")
    end_param = request.args.get("end")
    start_date, end_date = resolve_date_range(range_value, start_param, end_param)

    stats = get_summary_stats(user_id, start_date, end_date)
    summary = {
        "total_spent": stats["total_spent"],
        "expense_count": stats["transaction_count"],
        "top_category": stats["top_category"],
    }

    pagination = paginate(stats["transaction_count"], request.args.get("page"), TRANSACTIONS_PER_PAGE)

    transactions = get_recent_transactions(
        user_id,
        limit=TRANSACTIONS_PER_PAGE,
        start_date=start_date,
        end_date=end_date,
        offset=pagination["offset"],
    )
    categories = [
        {"name": cat["name"], "amount": cat["amount"], "percent": cat["pct"]}
        for cat in get_category_breakdown(user_id, start_date=start_date, end_date=end_date)
    ]

    filter_state = {
        "range": range_value,
        "start": (start_param or "") if range_value == "custom" else "",
        "end": (end_param or "") if range_value == "custom" else "",
    }

    filter_query_args = {"range": range_value}
    if range_value == "custom":
        filter_query_args["start"] = filter_state["start"]
        filter_query_args["end"] = filter_state["end"]

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        categories=categories,
        filter_state=filter_state,
        filter_query_args=filter_query_args,
        filter_presets=FILTER_PRESETS,
        pagination=pagination,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
