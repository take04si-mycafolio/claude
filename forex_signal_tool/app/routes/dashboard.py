from flask import Blueprint, render_template, jsonify
from app.config import Config

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    """ダッシュボード（初期データをサーバーサイドで埋め込み）"""
    from app.services.data_fetcher import get_latest_price

    # 初期価格データをサーバー側で取得してテンプレートに渡す
    initial_prices = {}
    for pair in Config.CURRENCY_PAIRS:
        price = get_latest_price(pair)
        if price:
            initial_prices[pair] = price

    return render_template(
        "dashboard.html",
        pairs=Config.CURRENCY_PAIRS,
        initial_prices=initial_prices,
    )


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
