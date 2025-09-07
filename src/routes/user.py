# routes/user.py
# User section: status page, register, login, logout.
# Errors are rendered inline on the same page (no redirect on failure).

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session
)
from sqlalchemy.exc import IntegrityError  # handle unique-constraint collisions

# Import the SQLAlchemy db handle from your app factory module.
# (Use 'from app import db' because your file is app.py, not run.py)
from app import db
from models.user import User

# All routes in this file will live under /user/*
bp = Blueprint("user", __name__, url_prefix="/user")


@bp.route("/")
def index():
    """
    User landing page.
    Shows simple status and links based on whether the user is logged in.
    We pass 'username' from the session into the template for convenience.
    """
    return render_template("user/user.html", username=session.get("username"))



@bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Create a new user account.

    GET:
      - Render blank form.

    POST:
      - Validate required fields.
      - Try to insert the user.
      - If a unique constraint hits (username/email exists), show inline error
        on the same page without redirect.
      - On success, redirect to login (PRG).
    """
    if request.method == "POST":
        # --- Read inputs and normalize ---
        username = (request.form.get("username") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        # --- Required fields check (fast-fail) ---
        if not username or not email or not password:
            return render_template(
                "user/register.html",
                error="All fields are required.",
                form={"username": username, "email": email},
            )

        # --- Create user model; hash password ---
        user = User(username=username, email=email)
        user.set_password(password)

        # --- Try to commit; DB enforces uniqueness ---
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Roll back the failed transaction before any further DB work
            db.session.rollback()

            # Determine which field collided (handles races / case variants)
            if User.query.filter_by(username=username).first():
                return render_template(
                    "user/register.html",
                    error="Username is already taken.",
                    form={"username": "", "email": email},
                )
            if User.query.filter_by(email=email).first():
                return render_template(
                    "user/register.html",
                    error="Email is already registered.",
                    form={"username": username, "email": ""},
                )

            # Fallback (should be rare)
            return render_template(
                "user/register.html",
                error="Account already exists.",
                form={"username": username, "email": email},
            )

        # --- Success path: go to login page with a flash message ---
        flash("Registration successful. Please log in.", "ok")
        return redirect(url_for("user.login"))

    # --- GET: render empty form ---
    return render_template("user/register.html")



@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Log the user in.

    GET:
      - Render blank login form.

    POST:
      - Validate required fields.
      - Look up user by username.
      - If bad creds: re-render same page with 'error' and preserve username.
      - If ok: set session and redirect to /user.
    """
    if request.method == "POST":
        # --- Read inputs ---
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        # --- Required fields check ---
        if not username or not password:
            return render_template(
                "user/login.html",
                error="Username and password are required.",
                form={"username": username},
            )

        # --- Fetch user and verify password ---
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            # Stay on login page; show inline error (no redirect)
            return render_template(
                "user/login.html",
                error="Incorrect username or password.",
                form={"username": username},
            )

        # --- Success: persist minimal session info ---
        session["user_id"] = user.id
        session["username"] = user.username

        flash("Logged in.", "ok")
        return redirect(url_for("user.index"))

    # --- GET: render empty form ---
    return render_template("user/login.html")



@bp.route("/logout")
def logout():
    """
    Log the user out by clearing the session,
    then go back to the user landing page.
    """
    session.clear()
    flash("Logged out.", "ok")
    return redirect(url_for("user.index"))
