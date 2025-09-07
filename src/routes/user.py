# --- Flask / framework --------------------------------------------------------
from flask import (
    Blueprint, current_app, render_template,
    request, redirect, url_for, flash, session
)  # core web primitives: routing, templates, form data, redirects, messages, session

# --- Security / tokens --------------------------------------------------------
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
# time-limited signed tokens for password reset links

# --- Database / ORM -----------------------------------------------------------
from sqlalchemy.exc import IntegrityError  # catch unique/constraint errors
from models.user import User               # your User ORM model (table)

# --- Utilities ----------------------------------------------------------------
from textwrap import dedent                # Strips multistring to structured readable format
from utils.mailer import send_email        # thin email helper (SMTP or dev print)

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



def _serializer() -> URLSafeTimedSerializer:
    # Derive a dedicated salt for reset tokens
    salt = current_app.config.get("RESET_TOKEN_SALT") or "pw-reset"
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)



@bp.route("/reset", methods=["GET", "POST"])
def reset_request():
    """
    Ask user for email; if it exists, send a time-limited reset link.
    Always show success message (don’t leak which emails exist).
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = _serializer().dumps({"uid": user.id})
            # absolute URL if SERVER_NAME set; else relative
            reset_url = url_for("user.reset_token", token=token, _external=True)
            # Include a nonce in session to invalidate old links after login
            current_app.logger.info("Password reset for uid=%s url=%s", user.id, reset_url)
            # Calculate minutes until expiration
            minutes = current_app.config.get("RESET_TOKEN_MAX_AGE", 3600) // 60

            send_email(
                to=user.email,
                subject="Password reset",
                body=dedent(f"""\
                    Hewo Mr/Ms {user.username} :3,
                    
                    Oh nooo, a wild missing password appeared! 🙀
                    It's okay, happens to the best of us. I got your back 🐥

                    Tap this magical link to reset your password:
                    {reset_url}

                    The spell on this link fades in {minutes} minutes ⏳✨
                    If you didn't ask for this, just ignore me and carry on being awesome possum 🦝😎 

                    big hugs,
                    — {current_app.config.get('SERVER_NAME', 'Your Friendly Website')}
                """),
            )
        flash("If that email exists, a reset link was sent.", "ok")
        return redirect(url_for("user.login"))
    return render_template("user/reset_request.html")



@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_token(token):
    """
    Verify token; let user set a new password.
    Token lifetime = RESET_TOKEN_MAX_AGE (seconds).
    """
    max_age = int(current_app.config.get("RESET_TOKEN_MAX_AGE", 3600))
    try:
        data = _serializer().loads(token, max_age=max_age)
        uid = int(data.get("uid", 0))
    except SignatureExpired:
        flash("Reset link expired. Please request a new one.", "warn")
        return redirect(url_for("user.reset_request"))
    except (BadSignature, Exception):
        flash("Invalid reset link.", "warn")
        return redirect(url_for("user.reset_request"))

    user = User.query.get(uid)
    if not user:
        flash("Account not found.", "warn")
        return redirect(url_for("user.reset_request"))

    if request.method == "POST":
        pw1 = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""
        if len(pw1) < 8:
            return render_template("user/reset_form.html", error="Password must be at least 8 characters.")
        if pw1 != pw2:
            return render_template("user/reset_form.html", error="Passwords do not match.")
        user.set_password(pw1)
        db.session.commit()
        flash("Password updated. You can log in now.", "ok")
        return redirect(url_for("user.login"))

    return render_template("user/reset_form.html")



@bp.get("/delete")
def delete_confirm():
    """
    Show a confirmation page to delete the currently logged-in account.
    Requires login. We ask for exact username + current password.
    """
    uid = session.get("user_id")
    if not uid:
        flash("Please log in first.", "warn")
        return redirect(url_for("user.login"))

    user = db.session.get(User, uid)
    if not user:
        session.clear()
        flash("Session expired. Please log in again.", "warn")
        return redirect(url_for("user.login"))

    return render_template("user/delete.html", username=user.username)



@bp.post("/delete")
def delete_account():
    """
    Handle POST from the delete confirmation page.

    Validates:
      - user still logged in
      - typed username matches current account's username
      - password is correct

    On success:
      - delete the user
      - clear the session
      - redirect safely away from /user/delete
    """
    uid = session.get("user_id")
    if not uid:
        flash("Please log in first.", "warn")
        return redirect(url_for("user.login"))

    user = db.session.get(User, uid)
    if not user:
        session.clear()
        flash("Session expired. Please log in again.", "warn")
        return redirect(url_for("user.login"))

    typed_username = (request.form.get("confirm") or "").strip()
    password       = request.form.get("password") or ""

    # Username must match exactly
    if typed_username != user.username:
        return render_template(
            "user/delete.html",
            username=user.username,
            error="Confirmation text did not match your username."
        )

    # Password must be valid
    if not user.check_password(password):
        return render_template(
            "user/delete.html",
            username=user.username,
            error="Incorrect password."
        )

    # Delete + logout
    db.session.delete(user)
    db.session.commit()
    session.clear()
    flash("Your account has been deleted.", "ok")

    # Redirect away from /user/delete to avoid refresh posting again
    # (Use your actual home endpoint if you have it; fallback to "/")
    try:
        return redirect(url_for("user.index"))
    except Exception:
        return redirect("/")