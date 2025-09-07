from flask import Blueprint, render_template

# group routes under a blueprint
# Also makes sure you can acces the blueprint with prefixing on url with /<url_prefix>
bp = Blueprint("about", __name__, url_prefix="/about")

@bp.route("/")
def index():
    return render_template("about.html")
