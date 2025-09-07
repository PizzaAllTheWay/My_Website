# Import Flask Server
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

# Create a global SQLAlchemy handle for models/routes to use
db = SQLAlchemy()

def create_app():
    # Create Flask app; declare where templates/static live
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Set a secret key (move to env var in real use)
    app.config["SECRET_KEY"] = "change-me"

    # Ensure the instance directory exists (Flask uses this for writable files)
    os.makedirs(app.instance_path, exist_ok=True)

    # Point SQLAlchemy to a SQLite file under instance/: instance/site.db
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "site.db")

    # Disable event system overhead
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Attach SQLAlchemy to this app
    db.init_app(app)

    # Import models so SQLAlchemy knows tables before create_all()
    from models.user import User  # noqa: F401

    # Register blueprints (routes)
    from routes.home import bp as home_bp
    from routes.about import bp as about_bp
    from routes.user import bp as user_bp
    app.register_blueprint(home_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(user_bp)

    # Create DB tables if they don't exist yet
    with app.app_context():
        db.create_all()

    # Return the configured app instance
    return app

# Expose the WSGI app object for gunicorn: `app:app`
app = create_app()

# Development server entrypoint
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
