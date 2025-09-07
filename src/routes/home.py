from flask import Blueprint, render_template

# group routes under a blueprint
bp = Blueprint("home", __name__)

@bp.route("/")
def index():
    return render_template("home.html")

