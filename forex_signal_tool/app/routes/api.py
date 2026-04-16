"""
REST API エンドポイント
"""

from flask import Blueprint, jsonify, request
from app.config import Config

bp = Blueprint("api", __name__)


# ---- USD/JPY トレンドスコア ----

@bp.route("/usdjpy/trend-score")
def usdjpy_trend_score():
    """GET /api/usdjpy/trend-score — マルチタイムフレーム買い強度スコア"""
    try:
        from app.services.usdjpy_analysis import get_usdjpy_trend_score
        result = get_usdjpy_trend_score()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---- 価格データ ----

@bp.route("/prices/latest")
def latest_prices():
    from app.services.data_fetcher import get_latest_price
    prices = {}
    for pair in Config.CURRENCY_PAIRS:
        prices[pair] = get_latest_price(pair)
    return jsonify(prices)


@bp.route("/prices/<pair>/<timeframe>")
def price_candles(pair: str, timeframe: str):
    if pair not in Config.CURRENCY_PAIRS:
        return jsonify({"error": "Invalid pair"}), 400
    if timeframe not in Config.TIMEFRAMES:
        return jsonify({"error": "Invalid timeframe"}), 400

    limit = request.args.get("limit", 200, type=int)
    from app.services.data_fetcher import get_candles
    df = get_candles(pair, timeframe, limit=limit)
    if df.empty:
        return jsonify([])
    return jsonify(df.to_dict(orient="records"))


# ---- シグナル ----

@bp.route("/signals")
def active_signals():
    from app.models.signal import TradingSignal
    pair = request.args.get("pair")
    timeframe = request.args.get("timeframe")

    query = TradingSignal.query.filter_by(is_active=True)
    if pair:
        query = query.filter_by(currency_pair=pair)
    if timeframe:
        query = query.filter_by(timeframe=timeframe)

    signals = query.order_by(TradingSignal.confidence_score.desc()).all()
    return jsonify([s.to_dict() for s in signals])


@bp.route("/signals/summary")
def signals_summary():
    from app.services.signal_engine import get_summary_signals
    return jsonify(get_summary_signals())


@bp.route("/signals/run", methods=["POST"])
def run_signals():
    from app.services.signal_engine import run_signal_engine
    result = run_signal_engine()
    return jsonify({"status": "ok", "results": result})


# ---- バックテスト ----

@bp.route("/backtest")
def backtest_results():
    from app.models.backtest import BacktestResult
    pair = request.args.get("pair")
    timeframe = request.args.get("timeframe")
    min_wr = request.args.get("min_win_rate", 0, type=float)

    query = BacktestResult.query
    if pair:
        query = query.filter_by(currency_pair=pair)
    if timeframe:
        query = query.filter_by(timeframe=timeframe)
    if min_wr:
        query = query.filter(BacktestResult.win_rate >= min_wr)

    results = query.order_by(BacktestResult.win_rate.desc()).limit(200).all()
    return jsonify([r.to_dict() for r in results])


@bp.route("/backtest/run", methods=["POST"])
def run_backtest():
    """全通貨ペア・タイムフレームのバックテストを実行"""
    from app.models.settings import Setting
    from app.services.backtester import run_all_backtests, save_backtest_results
    from app.services.data_fetcher import get_candles

    initial_capital = Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL)
    sl_pips = Setting.get_float("sl_pips", Config.DEFAULT_SL_PIPS)
    tp_pips = Setting.get_float("tp_pips", Config.DEFAULT_TP_PIPS)
    backtest_hours = Setting.get_int("backtest_hours", Config.DEFAULT_BACKTEST_HOURS)

    total_saved = 0
    for pair in Config.CURRENCY_PAIRS:
        for tf in Config.TIMEFRAMES:
            df = get_candles(pair, tf, limit=500)
            if df.empty:
                continue
            results = run_all_backtests(
                pair=pair, timeframe=tf, df=df,
                initial_capital=initial_capital,
                sl_pips=sl_pips, tp_pips=tp_pips,
                backtest_hours=backtest_hours,
            )
            saved = save_backtest_results(results)
            total_saved += saved

    return jsonify({"status": "ok", "saved": total_saved})


# ---- レポート ----

@bp.route("/reports")
def get_reports():
    from app.models.report import AiReport
    limit = request.args.get("limit", 10, type=int)
    reports = AiReport.query.order_by(AiReport.created_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in reports])


@bp.route("/reports/<int:report_id>")
def get_report(report_id: int):
    from app.models.report import AiReport
    report = AiReport.query.get_or_404(report_id)
    return jsonify(report.to_dict())


@bp.route("/reports/generate", methods=["POST"])
def generate_report():
    from app.services.report_generator import create_and_save_report
    from app.services.email_sender import send_report_email
    from app.models.settings import Setting

    report_id = create_and_save_report()
    if report_id is None:
        return jsonify({"error": "Failed to generate report"}), 500

    # メール送信
    send_email = request.json.get("send_email", True) if request.is_json else True
    email_sent = False
    if send_email:
        email_sent = send_report_email(report_id)

    return jsonify({"status": "ok", "report_id": report_id, "email_sent": email_sent})


# ---- データ取得 ----

@bp.route("/fetch/data", methods=["POST"])
def fetch_data():
    from app.services.data_fetcher import fetch_and_store_all
    result = fetch_and_store_all()
    return jsonify({"status": "ok", "result": result})


# ---- 設定 ----

@bp.route("/settings", methods=["GET"])
def get_settings():
    from app.models.settings import Setting
    keys = [
        "initial_capital", "sl_pips", "tp_pips", "backtest_hours",
        "min_win_rate", "min_trades", "report_times", "gemini_model",
    ]
    return jsonify({k: Setting.get(k) for k in keys})


@bp.route("/settings", methods=["POST"])
def update_settings():
    from app.models.settings import Setting
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    allowed = {
        "initial_capital", "sl_pips", "tp_pips", "backtest_hours",
        "min_win_rate", "min_trades", "report_times", "gemini_model",
    }
    for key, value in data.items():
        if key in allowed:
            Setting.set(key, value)

    return jsonify({"status": "ok"})
