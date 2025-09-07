from flask import Blueprint, render_template

# group routes under a blueprint
# Also makes sure you can acces the blueprint with prefixing on url with /<url_prefix>
bp = Blueprint("user", __name__, url_prefix="/user")

@bp.route("/")
def index():
    return render_template("user.html")
