import math
import os
import sqlite3
from datetime import date

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import (
    FILTER_PRESETS,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    normalize_range,
    paginate,
    parse_iso_date,
    resolve_date_range,
    update_expense,
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
            return render_template(
                "register.html", error="Please enter a valid email address."
            )

        if len(password) < 8:
            return render_template(
                "register.html", error="Password must be at least 8 characters."
            )

        conn = get_db()
        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing_user:
            conn.close()
            return render_template(
                "register.html", error="An account with this email already exists."
            )

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
    session.pop("keep_add_another", None)
    return redirect(url_for("landing"))


def require_active_user():
    """Return the current session's user record if it's still valid, else
    clear the stale session and return None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user_record = get_user_by_id(user_id)
    if user_record is None:
        session.pop("user_id", None)
        return None
    return user_record


def validate_expense_form(amount_raw, category, date_raw, description, today_date):
    """Validate the shared amount/category/date/description expense fields.
    Returns (amount, expense_date, error, error_field)."""
    error = None
    error_field = None
    amount = None
    try:
        amount = round(float(amount_raw), 2)
        if not math.isfinite(amount):
            error = "Please enter a valid amount."
            error_field = "amount"
        elif amount <= 0:
            error = "Amount must be greater than zero."
            error_field = "amount"
    except ValueError:
        error = "Please enter a valid amount."
        error_field = "amount"

    if not error and category not in CATEGORIES:
        error = "Please choose a valid category."
        error_field = "category"

    if not error and len(description) > 200:
        error = "Description must be 200 characters or fewer."
        error_field = "description"

    expense_date = None
    if not error:
        expense_date = parse_iso_date(date_raw)
        if expense_date is None:
            error = "Please enter a valid date."
            error_field = "date"
        elif expense_date > today_date:
            error = "Expense date cannot be in the future."
            error_field = "date"

    return amount, expense_date, error, error_field


def describe_expense_changes(
    old_expense, new_amount, new_category, new_date, new_description
):
    """Build a flash message summarising which fields changed between the
    stored expense and the just-submitted values."""
    old_description = old_expense["description"] or ""
    new_description = new_description or ""

    changes = []
    if round(old_expense["amount"], 2) != new_amount:
        changes.append(f"amount ₹{old_expense['amount']:.2f} → ₹{new_amount:.2f}")
    if old_expense["category"] != new_category:
        changes.append(f"category {old_expense['category']} → {new_category}")
    if old_expense["date"] != new_date.isoformat():
        changes.append(f"date {old_expense['date']} → {new_date.isoformat()}")
    if old_description != new_description:
        changes.append(
            f'description "{old_description or "—"}" → "{new_description or "—"}"'
        )

    if not changes:
        return "No changes made."
    return "Updated expense: " + "; ".join(changes) + "."


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/profile")
def profile():
    user_record = require_active_user()
    if user_record is None:
        return redirect(url_for("login"))
    user_id = user_record["id"]

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

    pagination = paginate(
        stats["transaction_count"], request.args.get("page"), TRANSACTIONS_PER_PAGE
    )

    transactions = get_recent_transactions(
        user_id,
        limit=TRANSACTIONS_PER_PAGE,
        start_date=start_date,
        end_date=end_date,
        offset=pagination["offset"],
    )
    categories = [
        {"name": cat["name"], "amount": cat["amount"], "percent": cat["pct"]}
        for cat in get_category_breakdown(
            user_id, start_date=start_date, end_date=end_date
        )
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
    if require_active_user() is None:
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_record = require_active_user()
    if user_record is None:
        return redirect(url_for("login"))
    user_id = user_record["id"]

    today_date = date.today()
    today = today_date.isoformat()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        category = request.form.get("category", "")
        date_raw = request.form.get("date", "")
        description = request.form.get("description", "").strip()
        add_another = bool(request.form.get("add_another"))

        form_values = {
            "amount": amount_raw,
            "category": category,
            "date": date_raw or today,
            "description": description,
            "add_another": add_another,
        }

        amount, expense_date, error, error_field = validate_expense_form(
            amount_raw, category, date_raw, description, today_date
        )

        if error:
            return render_template(
                "expenses_add.html",
                categories=CATEGORIES,
                error=error,
                error_field=error_field,
                form_values=form_values,
            )

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    amount,
                    category,
                    expense_date.isoformat(),
                    description or None,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.close()
            app.logger.exception("Failed to insert expense for user_id=%s", user_id)
            return render_template(
                "expenses_add.html",
                categories=CATEGORIES,
                error="Something went wrong saving your expense. Please try again.",
                error_field=None,
                form_values=form_values,
            )
        conn.close()

        flash(f"Added ₹{amount:.2f} to {category}.", "success")
        if add_another:
            session["keep_add_another"] = True
            return redirect(url_for("add_expense"))
        session.pop("keep_add_another", None)
        return redirect(url_for("profile"))

    keep_add_another = session.pop("keep_add_another", False)
    return render_template(
        "expenses_add.html",
        categories=CATEGORIES,
        form_values={
            "amount": "",
            "category": "",
            "date": today,
            "description": "",
            "add_another": keep_add_another,
        },
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_record = require_active_user()
    if user_record is None:
        return redirect(url_for("login"))
    user_id = user_record["id"]

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        flash("Expense not found.", "error")
        return redirect(url_for("profile"))

    today_date = date.today()

    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        category = request.form.get("category", "")
        date_raw = request.form.get("date", "")
        description = request.form.get("description", "").strip()

        form_values = {
            "amount": amount_raw,
            "category": category,
            "date": date_raw or today_date.isoformat(),
            "description": description,
        }

        amount, expense_date, error, error_field = validate_expense_form(
            amount_raw, category, date_raw, description, today_date
        )

        if error:
            return render_template(
                "expenses_add.html",
                categories=CATEGORIES,
                error=error,
                error_field=error_field,
                form_values=form_values,
                mode="edit",
                expense_id=id,
            )

        try:
            update_expense(
                id,
                user_id,
                amount,
                category,
                expense_date.isoformat(),
                description or None,
            )
        except sqlite3.Error:
            app.logger.exception(
                "Failed to update expense id=%s for user_id=%s", id, user_id
            )
            return render_template(
                "expenses_add.html",
                categories=CATEGORIES,
                error="Something went wrong saving your expense. Please try again.",
                error_field=None,
                form_values=form_values,
                mode="edit",
                expense_id=id,
            )

        flash(
            describe_expense_changes(
                expense, amount, category, expense_date, description
            ),
            "success",
        )
        return redirect(url_for("profile"))

    return render_template(
        "expenses_add.html",
        categories=CATEGORIES,
        form_values={
            "amount": expense["amount"],
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        },
        mode="edit",
        expense_id=id,
    )


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
