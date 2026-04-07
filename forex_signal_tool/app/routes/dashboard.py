from flask import Blueprint, render_template, request
from app.config import Config

bp = Blueprint("dashboard", __name__)


def _get_pair_data(pair: str) -> dict:
    """指定通貨ペアのデータをサーバーサイドで取得"""
    from app.services.data_fetcher import get_latest_price, get_candles
    from app.models.signal import TradingSignal
    from app.models.backtest import BacktestResult

    price = get_latest_price(pair)

    # アクティブシグナル（信頼度順）
    signals = (
        TradingSignal.query
        .filter_by(currency_pair=pair, is_active=True)
        .order_by(TradingSignal.confidence_score.desc())
        .limit(10)
        .all()
    )

    # バックテスト上位5件
    top_bt = (
        BacktestResult.query
        .filter_by(currency_pair=pair)
        .filter(BacktestResult.win_rate >= 55)
        .order_by(BacktestResult.win_rate.desc())
        .limit(5)
        .all()
    )

    buy_signals = [s for s in signals if s.signal_type == "BUY"]
    sell_signals = [s for s in signals if s.signal_type == "SELL"]

    if buy_signals and len(buy_signals) > len(sell_signals):
        overall = "BUY"
    elif sell_signals and len(sell_signals) > len(buy_signals):
        overall = "SELL"
    else:
        overall = "NEUTRAL"

    return {
        "pair": pair,
        "display": f"{pair[:3]}/{pair[3:]}",
        "price": price,
        "signals": [s.to_dict() for s in signals],
        "buy_count": len(buy_signals),
        "sell_count": len(sell_signals),
        "overall": overall,
        "top_backtest": [r.to_dict() for r in top_bt],
    }


@bp.route("/")
def index():
    pair = request.args.get("pair", "USDJPY")
    if pair not in Config.CURRENCY_PAIRS:
        pair = "USDJPY"
    data = _get_pair_data(pair)
    return render_template(
        "dashboard.html",
        pairs=Config.CURRENCY_PAIRS,
        current_pair=pair,
        data=data,
    )


@bp.route("/signals")
def signals():
    pair = request.args.get("pair", "USDJPY")
    if pair not in Config.CURRENCY_PAIRS:
        pair = "USDJPY"

    from app.models.signal import TradingSignal
    all_signals = (
        TradingSignal.query
        .filter_by(currency_pair=pair, is_active=True)
        .order_by(TradingSignal.confidence_score.desc())
        .all()
    )
    return render_template(
        "signals.html",
        pairs=Config.CURRENCY_PAIRS,
        current_pair=pair,
        signals=[s.to_dict() for s in all_signals],
    )


@bp.route("/backtest")
def backtest():
    pair = request.args.get("pair", "USDJPY")
    if pair not in Config.CURRENCY_PAIRS:
        pair = "USDJPY"

    from app.models.backtest import BacktestResult
    results = (
        BacktestResult.query
        .filter_by(currency_pair=pair)
        .order_by(BacktestResult.win_rate.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "backtest.html",
        pairs=Config.CURRENCY_PAIRS,
        current_pair=pair,
        results=[r.to_dict() for r in results],
    )


@bp.route("/reports")
def reports():
    from app.models.report import AiReport
    recent = AiReport.query.order_by(AiReport.created_at.desc()).limit(20).all()
    return render_template("reports.html", reports=recent)
