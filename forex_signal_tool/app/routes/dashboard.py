from flask import Blueprint, render_template, jsonify
from app.config import Config

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    return render_template("dashboard.html", pairs=Config.CURRENCY_PAIRS)


@bp.route("/signals")
def signals():
    return render_template("signals.html", pairs=Config.CURRENCY_PAIRS)


@bp.route("/backtest")
def backtest():
    return render_template("backtest.html", pairs=Config.CURRENCY_PAIRS)


@bp.route("/reports")
def reports():
    from app.models.report import AiReport
    recent = AiReport.query.order_by(AiReport.created_at.desc()).limit(20).all()
    return render_template("reports.html", reports=recent)
