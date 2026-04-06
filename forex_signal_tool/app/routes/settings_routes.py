from flask import Blueprint, render_template

bp = Blueprint("settings_view", __name__)


@bp.route("/")
def settings_page():
    return render_template("settings.html")
