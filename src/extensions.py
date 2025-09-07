from flask_sqlalchemy import SQLAlchemy

# Single shared SQLAlchemy instance for the whole app.
# Imported by app.py (to init_app) and by models (to define tables).
db = SQLAlchemy()
