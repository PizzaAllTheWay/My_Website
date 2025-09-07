from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify

# Support both import contexts: run from src/ or import as src.app
try:
    from extensions import db
except ModuleNotFoundError:
    from src.extensions import db
try:
    from models.user import User
except ModuleNotFoundError:
    from src.models.user import User

bp = Blueprint("bongo_cat", __name__, url_prefix="/bongo_cat")



@bp.get("/")
def index():
    """Game landing: show current score if logged in."""
    uid = session.get("user_id")
    score = None
    if uid:
        u = db.session.get(User, uid)  # SQLAlchemy 2.x
        if u:
            score = u.get_bongo_cat_score()
    return render_template("bongo_cat/game.html", score=score)



@bp.post("/sync")
def sync():
    """Batch increment by client-reported delta (periodic / on-leave / pre-nav)."""
    uid = session.get("user_id")
    if not uid:
        return jsonify(error="not_logged_in"), 401

    data = request.get_json(silent=True) or {}
    try:
        delta = int(data.get("delta", 0))
    except (TypeError, ValueError):
        return jsonify(error="bad_delta"), 400

    # Guard rails
    if delta == 0:
        return jsonify(total=None), 200
    if delta < 0:
        return jsonify(error="negative_delta_forbidden"), 400
    if delta > 1000:
        return jsonify(error="delta_too_large"), 400

    u = db.session.get(User, uid)
    if not u:
        session.clear()
        return jsonify(error="no_user"), 401

    u.add_bongo_cat_score(delta)
    db.session.commit()
    return jsonify(total=u.get_bongo_cat_score()), 200



@bp.get("/leaderboard")
def leaderboard():
    """Top 10 by score; stable ties by username ASC."""
    top = (
        User.query
        .order_by(User.bongo_cat_score.desc(), User.username.asc())
        .limit(10)
        .all()
    )
    rows = [{"username": u.username, "score": u.get_bongo_cat_score()} for u in top]
    return render_template("bongo_cat/leaderboard.html", rows=rows)
