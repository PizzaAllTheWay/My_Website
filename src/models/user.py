from app import db                      # SQLAlchemy instance created in app factory
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    """
    User accounts table.

    Notes:
    - Table name defaults to "user" (from class name). Override via __tablename__ if needed.
    - Unique constraints on username and email prevent duplicates at DB level.
    - We store only a password *hash* (never raw passwords).
    - created_at uses UTC; timestamps are naive (no tzinfo). Keep everything UTC.
    """

    # --- Primary Key ---
    id = db.Column(
        db.Integer,
        primary_key=True
    )  # Auto-increment integer primary key

    # --- Identity fields ---
    username = db.Column(
        db.String(32),
        unique=True,          # DB-level uniqueness; combined with app-side validation
        nullable=False,       # must be provided
        index=True            # speeds up lookups like User.query.filter_by(username=...)
    )
    # TIP: enforce a username policy app-side (allowed chars, length, etc.)

    email = db.Column(
        db.String(120),
        unique=True,          # one account per email
        nullable=False,
        index=True
    )
    # TIP: store emails lowercased app-side (normalize before insert).
    # SQLite unique is case-sensitive by default; normalization avoids surprises.

    # --- Auth ---
    password_hash = db.Column(
        db.String(255),
        nullable=False
    )
    # Why length 255?
    # - Enough for modern schemes (PBKDF2, scrypt, argon2) and their parameters/salt encodings.

    # --- Audit ---
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,  # set on INSERT by SQLAlchemy (server-side default not used here)
        nullable=False
    )

    # --- Helpers (optional but convenient) ---
    def set_password(self, password: str) -> None:
        """
        Hash and store the password.
        Call this when creating/updating the user, never assign password_hash directly.
        """
        # PBKDF2 by default in Werkzeug; fine for a simple app. For argon2, use passlib/argon2-cffi.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
