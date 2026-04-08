"""
管理者パネル ルート
/admin/ 以下のエンドポイント

ログイン: /admin/login
ダッシュボード: /admin/
バックテストツール: /admin/backtest-tool
"""

import threading
import logging
from functools import wraps
from datetime import datetime, timezone

from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, jsonify, flash)
from app.config import Config

bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)

# ジョブ実行ロック（プロセス内スレッド間共有）
_job_lock = threading.Lock()


# ---- 認証デコレーター ----

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            # AJAX / JSON リクエストには JSON 401 を返す
            is_ajax = (
                request.content_type == "application/json"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
            if is_ajax:
                return jsonify({"status": "error", "message": "セッションが切れました。ページを再読み込みしてログインしてください。"}), 401
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


# ---- 認証 ----

@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == Config.ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session.permanent = True
            return redirect(url_for("admin.dashboard"))
        error = "パスワードが違います"
    return render_template("admin/login.html", error=error)


@bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.login"))


# ---- ダッシュボード ----

@bp.route("/")
@login_required
def dashboard():
    from app.models.settings import Setting
    from app.models.price_data import PriceData
    from app.models.signal import TradingSignal
    from app.models.backtest import BacktestResult

    last_fetch   = Setting.get("last_data_fetch_at",   "未実行")
    last_bt      = Setting.get("last_backtest_at",     "未実行")
    last_signal  = Setting.get("last_signal_update_at","未実行")

    stats = {
        "price_rows":   PriceData.query.count(),
        "signal_count": TradingSignal.query.filter_by(is_active=True).count(),
        "bt_count":     BacktestResult.query.count(),
    }
    job_running = Setting.get("custom_bt_status", "idle") == "running"

    return render_template(
        "admin/dashboard.html",
        last_fetch=last_fetch,
        last_bt=last_bt,
        last_signal=last_signal,
        stats=stats,
        job_running=job_running,
    )


# ---- データ操作トリガー ----

@bp.route("/run-fetch", methods=["POST"])
@login_required
def run_fetch():
    from app.services.data_fetcher import fetch_and_store_all
    from app.models.settings import Setting

    try:
        results = fetch_and_store_all()
        total = sum(v for tf_r in results.values() for v in tf_r.values())
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_data_fetch_at", now_str)
        return jsonify({"status": "ok", "message": f"データ取得完了: {total}件保存"})
    except Exception as e:
        logger.exception("fetch error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/run-backtest", methods=["POST"])
@login_required
def run_backtest():
    from app.models.settings import Setting
    from app.services.backtester import run_all_backtests, save_backtest_results
    from app.services.data_fetcher import get_candles

    try:
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
                total_saved += save_backtest_results(results)

        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_backtest_at", now_str)
        return jsonify({"status": "ok", "message": f"バックテスト完了: {total_saved}件保存"})
    except Exception as e:
        logger.exception("backtest error")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/run-signals", methods=["POST"])
@login_required
def run_signals():
    from app.models.settings import Setting
    from app.services.signal_engine import run_signal_engine

    try:
        result = run_signal_engine()
        total = sum(v for tf_r in result.values() for v in tf_r.values())
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_signal_update_at", now_str)
        return jsonify({"status": "ok", "message": f"シグナル更新完了: {total}件"})
    except Exception as e:
        logger.exception("signal error")
        return jsonify({"status": "error", "message": str(e)}), 500


# ---- バックテストツール ----

@bp.route("/backtest-tool")
@login_required
def backtest_tool():
    from app.models.price_data import PriceData

    # ペア×TF の利用可能日時範囲をあらかじめ取得
    date_ranges = {}
    for pair in Config.CURRENCY_PAIRS:
        date_ranges[pair] = {}
        for tf in ["15min", "1hr", "4hr", "daily"]:
            row = (PriceData.query
                   .filter_by(currency_pair=pair, timeframe=tf)
                   .order_by(PriceData.timestamp.asc())
                   .first())
            row_last = (PriceData.query
                        .filter_by(currency_pair=pair, timeframe=tf)
                        .order_by(PriceData.timestamp.desc())
                        .first())
            if row and row_last:
                date_ranges[pair][tf] = {
                    "min": row.timestamp.strftime("%Y-%m-%d"),
                    "max": row_last.timestamp.strftime("%Y-%m-%d"),
                }
            else:
                date_ranges[pair][tf] = {"min": "", "max": ""}

    import json
    indicators = {
        "オシレーター": [
            ("RSI_14",         "RSI (14)"),
            ("MACD_12_26_9",   "MACD (12,26,9)"),
            ("Stochastic_14_3","Stochastic (14,3,3)"),
            ("CCI_20",         "CCI (20)"),
            ("Williams_R_14",  "Williams %R (14)"),
        ],
        "トレンド": [
            ("SMA_20",           "SMA (20)"),
            ("SMA_50",           "SMA (50)"),
            ("SMA_Cross_20_50",  "SMAクロス (20/50)"),
            ("EMA_Cross_9_21",   "EMAクロス (9/21)"),
            ("EMA_21",           "EMA (21)"),
            ("BollingerBands_20_2", "ボリンジャーバンド (20,2)"),
            ("BB_Squeeze",       "BBスクイーズ"),
        ],
        "ライン": [
            ("Pivot_Classic",          "ピボット (Classic)"),
            ("Fibonacci_Retracement",  "フィボナッチ"),
            ("Support_Resistance",     "サポート/レジスタンス"),
        ],
        "ボラティリティ": [
            ("ATR_14",          "ATR (14)"),
            ("Volatility_Index","ボラティリティ指数"),
        ],
        "パターン": [
            ("Hammer",              "ハンマー"),
            ("Inverted_Hammer",     "逆ハンマー"),
            ("Doji",                "十字線"),
            ("Bullish_Engulfing",   "陽の包み足"),
            ("Bearish_Engulfing",   "陰の包み足"),
            ("Three_White_Soldiers","三白兵"),
            ("Three_Black_Crows",   "三羽烏"),
            ("Pin_Bar",             "ピンバー"),
        ],
    }

    return render_template(
        "admin/backtest_tool.html",
        date_ranges_json=json.dumps(date_ranges),
        indicators=indicators,
        timeframes=[
            ("15min", "15分足"),
            ("1hr",   "1時間足"),
            ("4hr",   "4時間足"),
            ("daily", "日足"),
        ],
        pairs=[
            ("USDJPY", "ドル円"),
            ("GBPJPY", "ポンド円"),
            ("EURJPY", "ユーロ円"),
        ],
    )


@bp.route("/backtest-tool/run", methods=["POST"])
@login_required
def backtest_tool_run():
    """カスタムバックテスト実行（同期・排他制御）"""
    from app.models.settings import Setting
    from app import db

    # 排他制御: 既に実行中なら拒否
    if not _job_lock.acquire(blocking=False):
        return jsonify({"status": "busy", "message": "別のバックテストが実行中です。しばらく待ってから再試行してください。"}), 429

    try:
        Setting.set("custom_bt_status", "running")
        db.session.commit()

        data = request.get_json(force=True)
        pair       = data.get("pair", "USDJPY")
        timeframe  = data.get("timeframe", "1hr")
        start_date = data.get("start_date", "")
        end_date   = data.get("end_date", "")
        capital    = float(data.get("initial_capital", 1_000_000))
        sl_pips    = float(data.get("sl_pips", 20))
        rr_ratio   = float(data.get("rr_ratio", 1.5))
        tp_pips    = round(sl_pips * rr_ratio, 1)
        indicator_names = data.get("indicators", [])

        if pair not in Config.CURRENCY_PAIRS:
            return jsonify({"status": "error", "message": "無効な通貨ペア"}), 400
        if not indicator_names:
            return jsonify({"status": "error", "message": "指標を1つ以上選択してください"}), 400

        from app.services.data_fetcher import get_candles
        from app.services.backtester import run_backtest_for_indicator
        from app.services.indicators.oscillators import calculate_oscillators
        from app.services.indicators.trend import calculate_trend
        from app.services.indicators.lines import calculate_lines
        from app.services.indicators.volatility import calculate_volatility
        from app.services.indicators.patterns import calculate_patterns
        import pandas as pd

        INDICATOR_FUNC_MAP = {}
        for func in [calculate_oscillators, calculate_trend,
                     calculate_lines, calculate_volatility, calculate_patterns]:
            try:
                # ダミーdfでキーを取得
                dummy = pd.DataFrame({"open":[1]*50,"high":[1]*50,"low":[1]*50,
                                      "close":[1]*50,"volume":[0]*50})
                keys = func(dummy).keys()
                for k in keys:
                    INDICATOR_FUNC_MAP[k] = func
            except Exception:
                pass

        df = get_candles(pair, timeframe, limit=5000)
        if df.empty:
            return jsonify({"status": "error", "message": "データがありません"}), 400

        # 日付フィルタ
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=None)
            df = df[df["timestamp"] >= start_dt]
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, tzinfo=None)
            df = df[df["timestamp"] <= end_dt]
        df = df.reset_index(drop=True)

        if len(df) < 30:
            return jsonify({"status": "error", "message": "選択期間のデータが不足しています（30本以上必要）"}), 400

        results = []
        for ind_name in indicator_names:
            func = INDICATOR_FUNC_MAP.get(ind_name)
            if func is None:
                continue
            # 全データ期間でバックテスト（backtest_hours=99999で全期間使用）
            res = run_backtest_for_indicator(
                df=df,
                indicator_name=ind_name,
                indicator_func=func,
                pair=pair,
                timeframe=timeframe,
                initial_capital=capital,
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                backtest_hours=99999,
            )
            if res:
                res["indicator_name"] = ind_name
                # トレードログをJSONシリアライズ可能に変換
                trades_out = []
                for t in res.get("trades", []):
                    entry_ts = t.get("entry_ts")
                    exit_ts  = t.get("exit_ts")
                    trades_out.append({
                        "entry_ts": entry_ts.strftime("%Y/%m/%d %H:%M") if hasattr(entry_ts, "strftime") else str(entry_ts),
                        "exit_ts":  exit_ts.strftime("%Y/%m/%d %H:%M")  if hasattr(exit_ts,  "strftime") else str(exit_ts),
                        "signal":       t.get("signal"),
                        "entry_price":  round(t.get("entry_price", 0), 3),
                        "exit_price":   round(t.get("exit_price", 0), 3),
                        "outcome":      t.get("outcome"),
                        "capital_after": round(t.get("capital_after", 0)),
                    })
                res["trades"] = trades_out
                res["tp_pips"] = tp_pips
                res["rr_ratio"] = rr_ratio
                # datetimeをstrに変換
                for k in ["calculated_at"]:
                    if k in res and hasattr(res[k], "strftime"):
                        res[k] = res[k].strftime("%Y/%m/%d %H:%M")
                results.append(res)

        Setting.set("custom_bt_status", "idle")
        db.session.commit()

        return jsonify({"status": "ok", "results": results})

    except Exception as e:
        logger.exception("custom backtest error")
        try:
            from app.models.settings import Setting
            Setting.set("custom_bt_status", "idle")
        except Exception:
            pass
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        _job_lock.release()


@bp.route("/backtest-tool/status")
@login_required
def backtest_tool_status():
    from app.models.settings import Setting
    status = Setting.get("custom_bt_status", "idle")
    return jsonify({"status": status})
