# Import Flask Server
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # real migrations (Alembic under the hood)
from sqlalchemy import inspect, text   # tiny dev helper for SQLite
import os

# IMPORTANT:
# Use a neutral module for shared extensions to avoid circular imports.
# Models import `db` from extensions; app.py imports the same and calls init_app().
# This prevents: app.py -> models -> app.py loops.
try:
    from extensions import db
except ModuleNotFoundError:
    # If imported as 'src.app', allow absolute path too.
    from src.extensions import db

BASE_DIR = os.path.dirname(__file__)  # .../src

# Migration manager (binds to app+db inside create_app)
migrate = Migrate()


def create_app():
    # Create Flask app; declare where templates/static/instance(databases) live
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        # hard-pin instance under src/
        instance_path=os.path.join(BASE_DIR, "instance"),
    )

    # Session signing key (move to env in real apps)
    app.config["SECRET_KEY"] = "change-me"

    # Ensure the instance directory exists (Flask stores writable files here)
    os.makedirs(app.instance_path, exist_ok=True)

    # SQLite DB under instance/: instance/site.db
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "site.db")

    # Disable SQLAlchemy event system overhead
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Attach SQLAlchemy to this app (db defined in extensions.py)
    db.init_app(app)

    # Bind Alembic/Flask-Migrate to this app+db so `flask db ...` works
    # Why: db.create_all() does NOT modify existing tables; migrations do.
    migrate.init_app(app, db)

    # Import models so SQLAlchemy (and Alembic’s autogenerate) sees tables.
    # Keep imports AFTER init_app to avoid cycles and half-initialized states.
    try:
        from models.user import User  # noqa: F401
    except ModuleNotFoundError:
        from src.models.user import User  # noqa: F401

    # Register blueprints (routes)
    try:
        from routes.home import bp as home_bp
        from routes.bongo_cat import bp as bongo_cat_bp
        from routes.about import bp as about_bp
        from routes.user import bp as user_bp
    except ModuleNotFoundError:
        from src.routes.home import bp as home_bp
        from src.routes.bongo_cat import bp as bongo_cat_bp
        from src.routes.about import bp as about_bp
        from src.routes.user import bp as user_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(bongo_cat_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(user_bp)

    # --- Lightweight "migration" helper (dev only) ---------------------------
    # Goal: on restart, auto-add specific missing columns in SQLite.
    # Why: db.create_all() won't alter existing tables; this fills a tiny gap
    #      for quick local changes WITHOUT running Alembic.
    # Limits: adds columns only (with DEFAULT if NOT NULL). No drops/renames/type changes.
    # Prod/teams: use Flask-Migrate and run `flask db migrate` + `flask db upgrade`.
    def sqlite_auto_add_columns():
        # Only run on SQLite (simple check)
        if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
            return

        insp = inspect(db.engine)

        # If the 'user' table doesn't exist yet, nothing to alter; create_all() will handle it.
        if not insp.has_table("user"):
            return

        # Current columns present in the 'user' table
        existing_cols = {c["name"] for c in insp.get_columns("user")}

        # Define columns we want to ensure exist (name -> DDL to add)
        planned_alters = []
        if "bongo_cat_score" not in existing_cols:
            # NOT NULL requires a DEFAULT for existing rows
            planned_alters.append(
                "ALTER TABLE user ADD COLUMN bongo_cat_score INTEGER NOT NULL DEFAULT 0"
            )

        # Apply each missing column once; commit after changes
        for ddl in planned_alters:
            db.session.execute(text(ddl))

        if planned_alters:
            db.session.commit()
    # -------------------------------------------------------------------------

    # Create tables if they don't exist (first boot),
    # then optionally run the dev-only SQLite auto-ADD helper.
    # NOTE:
    # - Real schema changes: generate a migration (flask db migrate) and apply (flask db upgrade).
    # - Your start/restart scripts already call `flask db upgrade` before starting gunicorn.
    with app.app_context():
        db.create_all()            # creates missing tables only; safe to keep
        sqlite_auto_add_columns()  # optional convenience for local dev on SQLite

    # Return the configured app instance
    return app


# Expose the WSGI app object for gunicorn: `app:app`
app = create_app()

# Development server entrypoint
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
