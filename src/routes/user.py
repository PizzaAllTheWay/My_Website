# routes/user.py
# User section: status page, register, login, logout.
# Errors are rendered inline on the same page (no redirect on failure).

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, session
)
from sqlalchemy.exc import IntegrityError  # handle unique-constraint collisions

# Import the User model (ORM table)
from models.user import User

# IMPORTANT:
# Use a neutral module for shared extensions to avoid circular imports.
# Models import `db` from extensions; app.py imports the same and calls init_app().
# This prevents: app.py -> models -> app.py loops.
try:
    from extensions import db
except ModuleNotFoundError:
    from src.extensions import db

# All routes in this file will live under /user/*
bp = Blueprint("user", __name__, url_prefix="/user")


@bp.route("/")
def index():
    """
    User landing page.

    What it does:
    - Reads the current login state from the session (username).
    - If logged in, looks up the User row and fetches bongo_cat_score.
    - Renders templates/user/user.html with both values so the page
      can show “Signed in as …” and “Bongo cat score: …”.

    Notes:
    - If no user is logged in, username=None and bongo_cat_score=None,
      and the template will show login/register links instead.
    """
    # Pull username from the signed session cookie
    username = session.get("username")

    # Default when anonymous or user not found
    bongo_cat_score = None

    # If logged in, load the user and read the score
    if username:
        u = User.query.filter_by(username=username).first()
        if u:
            bongo_cat_score = u.get_bongo_cat_score()

    # Pass data to the template
    return render_template(
        "user/user.html",
        username=username,
        bongo_cat_score=bongo_cat_score,
    )



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
