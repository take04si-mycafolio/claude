"""
管理者パネル ルート
/admin/ 以下のエンドポイント

ログイン: /admin/login
ダッシュボード: /admin/
バックテストツール: /admin/backtest-tool

NOTE: Xserver 共有サーバーは CGI の 4xx/5xx を HTML エラーページに差し替えるため、
      API エンドポイントはすべて HTTP 200 で返し、JSON の status フィールドでエラーを伝える。
"""

import threading
import logging
from functools import wraps
from datetime import datetime, timezone

from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, jsonify)
from app.config import Config

bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)

_job_lock = threading.Lock()


# ---- 認証デコレーター ----

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            is_ajax = (
                request.content_type == "application/json"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
            if is_ajax:
                # HTTP 200 で返す (Xserver が 401 HTML を差し替えないように)
                return jsonify({"status": "auth_required",
                                "message": "セッションが切れました。再ログインしてください。"})
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


# ---- デバッグ ----

@bp.route("/ping")
def ping():
    """CGI 疎通確認用 (GET)"""
    import sys
    return jsonify({"status": "ok", "python": sys.version,
                    "project": Config.CURRENCY_PAIRS})


@bp.route("/test-post", methods=["POST"])
def test_post():
    """POST 動作確認用 (認証不要) - DB接続なし"""
    data = request.get_json(force=True, silent=True) or {}
    return jsonify({"status": "ok", "received": data,
                    "method": request.method,
                    "content_type": request.content_type})


# ---- ダッシュボード ----

@bp.route("/")
@login_required
def dashboard():
    from app.models.settings import Setting
    from app.models.price_data import PriceData
    from app.models.signal import TradingSignal
    from app.models.backtest import BacktestResult
    from app import db
    from sqlalchemy import text

    last_fetch       = Setting.get("last_data_fetch_at",    "未実行")
    last_daily_fetch = Setting.get("last_daily_fetch_at",   "未実行")
    last_bt          = Setting.get("last_backtest_at",      "未実行")
    last_signal      = Setting.get("last_signal_update_at", "未実行")

    stats = {
        "price_rows":   PriceData.query.count(),
        "signal_count": TradingSignal.query.filter_by(is_active=True).count(),
        "bt_count":     BacktestResult.query.count(),
    }

    # ---- DB 使用量内訳 ----
    db_tables = []
    try:
        rows = db.session.execute(text("""
            SELECT
                table_name,
                COALESCE(table_rows, 0)                                       AS row_est,
                ROUND(data_length  / 1024 / 1024, 2)                          AS data_mb,
                ROUND(index_length / 1024 / 1024, 2)                          AS idx_mb,
                ROUND((data_length + index_length) / 1024 / 1024, 2)          AS total_mb
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            ORDER BY (data_length + index_length) DESC
        """)).fetchall()
        for r in rows:
            db_tables.append({
                "name":     r[0],
                "rows":     int(r[1]),
                "data_mb":  float(r[2] or 0),
                "idx_mb":   float(r[3] or 0),
                "total_mb": float(r[4] or 0),
            })
    except Exception:
        pass

    # DB 合計サイズ
    db_total_mb = round(sum(t["total_mb"] for t in db_tables), 2)

    tf_order = ["5min", "15min", "30min", "1hr", "4hr", "daily"]

    MACRO_PAIRS_SET = {"US10Y", "USBF", "DXY"}

    # price_data: 通貨ペア × 足種 ごとの件数・最古・最新（マクロ除外）
    price_by_tf = []
    macro_status = []
    try:
        from sqlalchemy import func as sa_func
        TF_SORT = {tf: i for i, tf in enumerate(tf_order)}
        rows = (db.session.query(
            PriceData.currency_pair,
            PriceData.timeframe,
            sa_func.count().label("cnt"),
            sa_func.min(PriceData.timestamp).label("oldest"),
            sa_func.max(PriceData.timestamp).label("newest"),
        ).group_by(PriceData.currency_pair, PriceData.timeframe).all())
        rows_sorted = sorted(rows, key=lambda r: (r.currency_pair, TF_SORT.get(r.timeframe, 99)))
        macro_found = {}
        for r in rows_sorted:
            entry = {
                "pair":   r.currency_pair,
                "tf":     r.timeframe,
                "count":  r.cnt,
                "oldest": r.oldest.strftime("%Y/%m/%d %H:%M") if r.oldest else "-",
                "newest": r.newest.strftime("%Y/%m/%d %H:%M") if r.newest else "-",
            }
            if r.currency_pair in MACRO_PAIRS_SET:
                macro_found[r.currency_pair] = entry
            else:
                price_by_tf.append(entry)
        for pair in ["US10Y", "USBF", "DXY"]:
            if pair in macro_found:
                macro_status.append(macro_found[pair])
            else:
                macro_status.append({"pair": pair, "tf": "1hr", "count": 0, "oldest": "-", "newest": "-"})
    except Exception as e:
        logger.warning("price_by_tf error: %s", e)

    # ---- シミュレーショントレード集計 ----
    sim_stats = {"total": 0, "by_pair": [], "by_tf": [], "win": 0, "loss": 0}
    try:
        from app.models.simulation_trade import SimulationTrade
        sim_stats["total"] = SimulationTrade.query.count()
        for pair in Config.CURRENCY_PAIRS:
            c = SimulationTrade.query.filter_by(currency_pair=pair).count()
            sim_stats["by_pair"].append({"pair": pair, "count": c})
        for tf in tf_order:
            c = SimulationTrade.query.filter_by(timeframe=tf).count()
            if c > 0:
                sim_stats["by_tf"].append({"tf": tf, "count": c})
        sim_stats["win"]  = SimulationTrade.query.filter_by(outcome="WIN").count()
        sim_stats["loss"] = SimulationTrade.query.filter_by(outcome="LOSS").count()
    except Exception as e:
        logger.warning("sim_stats error: %s", e)

    # ---- バックテスト結果集計 ----
    bt_stats = {"total": 0, "by_pair": [], "by_tf": [], "top": []}
    try:
        bt_stats["total"] = BacktestResult.query.count()
        for pair in Config.CURRENCY_PAIRS:
            c = BacktestResult.query.filter_by(currency_pair=pair).count()
            bt_stats["by_pair"].append({"pair": pair, "count": c})
        for tf in tf_order:
            c = BacktestResult.query.filter_by(timeframe=tf).count()
            if c > 0:
                bt_stats["by_tf"].append({"tf": tf, "count": c})
        top = (BacktestResult.query
               .filter(BacktestResult.total_trades >= 5)
               .order_by(BacktestResult.win_rate.desc())
               .limit(10).all())
        for r in top:
            bt_stats["top"].append({
                "pair":      r.currency_pair,
                "tf":        r.timeframe,
                "indicator": r.indicator_name,
                "win_rate":  float(r.win_rate),
                "trades":    r.total_trades,
                "pf":        float(r.profit_factor) if r.profit_factor else 0,
            })
    except Exception as e:
        logger.warning("bt_stats error: %s", e)

    return render_template(
        "admin/dashboard.html",
        last_fetch=last_fetch,
        last_daily_fetch=last_daily_fetch,
        last_bt=last_bt,
        last_signal=last_signal,
        stats=stats,
        db_tables=db_tables,
        price_by_tf=price_by_tf,
        macro_status=macro_status,
        db_total_mb=db_total_mb,
        sim_stats=sim_stats,
        bt_stats=bt_stats,
    )


# ---- データ操作トリガー (すべて HTTP 200 で返す) ----

@bp.route("/run-fetch", methods=["POST"])
@login_required
def run_fetch():
    from app.services.data_fetcher import fetch_and_store_all
    from app.models.settings import Setting

    try:
        results = fetch_and_store_all()
        total = sum(v for tf_r in results.values() for v in tf_r.values())
        Setting.set("last_data_fetch_at",
                    datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC"))
        return jsonify({"status": "ok", "message": f"データ取得完了: {total}件保存"})
    except Exception as e:
        logger.exception("fetch error")
        return jsonify({"status": "error", "message": str(e)})


@bp.route("/run-backtest", methods=["POST"])
@login_required
def run_backtest():
    from app.models.settings import Setting
    from app.services.backtester import run_all_backtests, save_backtest_results
    from app.services.data_fetcher import get_candles

    try:
        initial_capital = Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL)
        sl_pips  = Setting.get_float("sl_pips",  Config.DEFAULT_SL_PIPS)
        tp_pips  = Setting.get_float("tp_pips",  Config.DEFAULT_TP_PIPS)
        bt_hours = Setting.get_int("backtest_hours", Config.DEFAULT_BACKTEST_HOURS)

        total_saved = 0
        for pair in Config.CURRENCY_PAIRS:
            for tf in Config.TIMEFRAMES:
                df = get_candles(pair, tf, limit=500)
                if df.empty:
                    continue
                res = run_all_backtests(pair=pair, timeframe=tf, df=df,
                                        initial_capital=initial_capital,
                                        sl_pips=sl_pips, tp_pips=tp_pips,
                                        backtest_hours=bt_hours)
                total_saved += save_backtest_results(res)

        Setting.set("last_backtest_at",
                    datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC"))
        return jsonify({"status": "ok", "message": f"バックテスト完了: {total_saved}件保存"})
    except Exception as e:
        logger.exception("backtest error")
        return jsonify({"status": "error", "message": str(e)})


@bp.route("/run-macro", methods=["POST"])
@login_required
def run_macro():
    from app.services.data_fetcher import fetch_and_store_macro
    from app.models.settings import Setting

    try:
        results = fetch_and_store_macro()
        total = sum(v for tf_r in results.values() for v in tf_r.values())
        Setting.set("last_macro_fetch_at",
                    datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC"))
        return jsonify({"status": "ok", "message": f"マクロ指標取得完了: {total}件保存"})
    except Exception as e:
        logger.exception("macro fetch error")
        return jsonify({"status": "error", "message": str(e)})


@bp.route("/run-quantflow-bt", methods=["POST"])
@login_required
def run_quantflow_bt():
    from app.services.quantflow_backtest import run_quantflow_backtest
    from app.models.settings import Setting

    try:
        sl_pips    = Setting.get_float("sl_pips", 20.0)
        tp_pips    = Setting.get_float("tp_pips", 40.0)
        start_date = Setting.get("quantflow_bt_start", "2026-01-01")
        result     = run_quantflow_backtest(
            pair="USDJPY", sl_pips=sl_pips, tp_pips=tp_pips, start_date=start_date)
        if "error" in result:
            return jsonify({"status": "error", "message": result["error"]})
        Setting.set("last_quantflow_bt_at",
                    datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC"))
        return jsonify({"status": "ok",
                        "message": f"QuantFlow BT完了: {result['total_trades']}トレード"})
    except Exception as e:
        logger.exception("quantflow bt error")
        return jsonify({"status": "error", "message": str(e)})


@bp.route("/run-signals", methods=["POST"])
@login_required
def run_signals():
    from app.models.settings import Setting
    from app.services.signal_engine import run_signal_engine

    try:
        result = run_signal_engine()
        total = sum(v for tf_r in result.values() for v in tf_r.values())
        Setting.set("last_signal_update_at",
                    datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC"))
        return jsonify({"status": "ok", "message": f"シグナル更新完了: {total}件"})
    except Exception as e:
        logger.exception("signal error")
        return jsonify({"status": "error", "message": str(e)})


# ---- バックテストツール ----

@bp.route("/backtest-tool")
@login_required
def backtest_tool():
    from app.models.price_data import PriceData
    import json

    date_ranges = {}
    for pair in Config.CURRENCY_PAIRS:
        date_ranges[pair] = {}
        for tf in ["15min", "1hr", "4hr", "daily"]:
            first = (PriceData.query
                     .filter_by(currency_pair=pair, timeframe=tf)
                     .order_by(PriceData.timestamp.asc()).first())
            last  = (PriceData.query
                     .filter_by(currency_pair=pair, timeframe=tf)
                     .order_by(PriceData.timestamp.desc()).first())
            if first and last:
                date_ranges[pair][tf] = {
                    "min": first.timestamp.strftime("%Y-%m-%d"),
                    "max": last.timestamp.strftime("%Y-%m-%d"),
                }
            else:
                date_ranges[pair][tf] = {"min": "", "max": ""}

    indicators = {
        "オシレーター": [
            ("RSI_14",         "RSI (14)"),
            ("MACD_12_26_9",   "MACD (12,26,9)"),
            ("Stochastic_14_3","Stochastic (14,3,3)"),
            ("CCI_20",         "CCI (20)"),
            ("Williams_R_14",  "Williams %R (14)"),
        ],
        "トレンド": [
            ("SMA_20",              "SMA (20)"),
            ("SMA_50",              "SMA (50)"),
            ("SMA_Cross_20_50",     "SMAクロス (20/50)"),
            ("EMA_Cross_9_21",      "EMAクロス (9/21)"),
            ("EMA_21",              "EMA (21)"),
            ("BollingerBands_20_2", "ボリンジャーバンド (20,2)"),
            ("BB_Squeeze",          "BBスクイーズ"),
        ],
        "ライン": [
            ("Pivot_Classic",         "ピボット (Classic)"),
            ("Fibonacci_Retracement", "フィボナッチ"),
            ("Support_Resistance",    "サポート/レジスタンス"),
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
        timeframes=[("15min","15分足"),("1hr","1時間足"),("4hr","4時間足"),("daily","日足")],
        pairs=[("USDJPY","ドル円"),("GBPJPY","ポンド円"),("EURJPY","ユーロ円")],
    )


@bp.route("/backtest-tool/run", methods=["POST"])
@login_required
def backtest_tool_run():
    """カスタムバックテスト実行 (常に HTTP 200 を返す)"""
    # 関数全体を try/except で囲む（Setting.get 含む全行をカバー）
    try:
        from app.models.settings import Setting

        # 排他制御: 10分以上経過していたら古いロックを自動解除
        if Setting.get("custom_bt_status") == "running":
            started_at_str = Setting.get("custom_bt_started_at", "")
            auto_reset = True
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str)
                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                    if elapsed < 600:
                        auto_reset = False
                except Exception:
                    pass
            if not auto_reset:
                return jsonify({"status": "busy",
                                "message": "別のバックテストが実行中です。しばらく待ってから再試行してください。"})
            logger.warning("custom_bt_status stuck 'running' over 10min, auto-reset")

        Setting.set("custom_bt_status", "running")
        Setting.set("custom_bt_started_at", datetime.now(timezone.utc).isoformat())
    except Exception as e:
        logger.exception("backtest startup error")
        return jsonify({"status": "error", "message": "起動エラー: " + str(e)})

    try:
        Setting.set("custom_bt_status", "running")
        Setting.set("custom_bt_started_at", datetime.now(timezone.utc).isoformat())

        data = request.get_json(force=True, silent=True) or {}
        pair            = data.get("pair", "USDJPY")
        timeframe       = data.get("timeframe", "1hr")
        start_date      = data.get("start_date", "")
        end_date        = data.get("end_date", "")
        capital         = float(data.get("initial_capital", 1_000_000))
        sl_pips         = float(data.get("sl_pips", 20))
        rr_ratio        = float(data.get("rr_ratio", 1.5))
        tp_pips         = round(sl_pips * rr_ratio, 1)
        indicator_names = data.get("indicators", [])

        if pair not in Config.CURRENCY_PAIRS:
            Setting.set("custom_bt_status", "idle")
            return jsonify({"status": "error", "message": "無効な通貨ペア"})
        if not indicator_names:
            Setting.set("custom_bt_status", "idle")
            return jsonify({"status": "error", "message": "指標を1つ以上選択してください"})

        from app.services.data_fetcher import get_candles
        from app.services.backtester import run_backtest_for_indicator
        from app.services.indicators.oscillators import calculate_oscillators
        from app.services.indicators.trend import calculate_trend
        from app.services.indicators.lines import calculate_lines
        from app.services.indicators.volatility import calculate_volatility
        from app.services.indicators.patterns import calculate_patterns
        import pandas as pd

        # 指標名 → 計算関数のマップ
        INDICATOR_FUNC_MAP = {}
        _FUNCS = [calculate_oscillators, calculate_trend,
                  calculate_lines, calculate_volatility, calculate_patterns]
        for func in _FUNCS:
            try:
                dummy = pd.DataFrame({c: [float(i) for i in range(1, 61)]
                                      for c in ["open", "high", "low", "close", "volume"]})
                for k in func(dummy).keys():
                    INDICATOR_FUNC_MAP[k] = func
            except Exception:
                pass

        df = get_candles(pair, timeframe, limit=5000)
        if df.empty:
            Setting.set("custom_bt_status", "idle")
            tf_labels = {"15min":"15分足","1hr":"1時間足","4hr":"4時間足","daily":"日足"}
            tf_lbl = tf_labels.get(timeframe, timeframe)
            return jsonify({"status": "error",
                            "message": f"{pair} の {tf_lbl} データがDBにありません。"
                                       "ダッシュボードで「データ取得を実行」してから再試行してください。"})

        total_rows = len(df)
        # 日付フィルタ
        if start_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=None)
                df = df[df["timestamp"] >= sd]
            except ValueError:
                pass
        if end_date:
            try:
                ed = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=None)
                df = df[df["timestamp"] <= ed]
            except ValueError:
                pass
        df = df.reset_index(drop=True)

        if len(df) < 30:
            Setting.set("custom_bt_status", "idle")
            db_min = df["timestamp"].min() if not df.empty else "なし"
            db_max = df["timestamp"].max() if not df.empty else "なし"
            return jsonify({"status": "error",
                            "message": (
                                f"選択期間のデータが {len(df)} 本しかありません（30本以上必要）。\n"
                                f"DBには {total_rows} 本ありますが、期間フィルタ後に減りました。\n"
                                f"利用可能期間: {db_min} 〜 {db_max}"
                            )})

        results = []
        for ind_name in indicator_names:
            func = INDICATOR_FUNC_MAP.get(ind_name)
            if func is None:
                continue
            try:
                res = run_backtest_for_indicator(
                    df=df, indicator_name=ind_name, indicator_func=func,
                    pair=pair, timeframe=timeframe,
                    initial_capital=capital, sl_pips=sl_pips, tp_pips=tp_pips,
                    backtest_hours=99999,
                )
            except Exception as ex:
                logger.warning("Indicator %s failed: %s", ind_name, ex)
                continue

            if not res:
                continue

            res["indicator_name"] = ind_name
            res["tp_pips"]  = tp_pips
            res["rr_ratio"] = rr_ratio

            trades_out = []
            for t in res.get("trades", []):
                ets = t.get("entry_ts")
                xts = t.get("exit_ts")
                trades_out.append({
                    "entry_ts":    ets.strftime("%Y/%m/%d %H:%M") if hasattr(ets, "strftime") else str(ets),
                    "exit_ts":     xts.strftime("%Y/%m/%d %H:%M") if hasattr(xts, "strftime") else str(xts),
                    "signal":      t.get("signal"),
                    "entry_price": round(float(t.get("entry_price", 0)), 3),
                    "exit_price":  round(float(t.get("exit_price", 0)), 3),
                    "outcome":     t.get("outcome"),
                    "capital_after": round(float(t.get("capital_after", 0))),
                })
            res["trades"] = trades_out

            for k in ["calculated_at"]:
                if k in res and hasattr(res[k], "strftime"):
                    res[k] = res[k].strftime("%Y/%m/%d %H:%M")

            results.append(res)

        Setting.set("custom_bt_status", "idle")
        return jsonify({"status": "ok", "results": results})

    except Exception as e:
        logger.exception("custom backtest error")
        try:
            Setting.set("custom_bt_status", "idle")
        except Exception:
            pass
        return jsonify({"status": "error", "message": str(e)})


@bp.route("/backtest-tool/status")
@login_required
def backtest_tool_status():
    from app.models.settings import Setting
    return jsonify({"status": Setting.get("custom_bt_status", "idle")})


@bp.route("/backtest-tool/reset", methods=["POST"])
@login_required
def backtest_tool_reset():
    """stuck した実行フラグを手動リセット"""
    from app.models.settings import Setting
    Setting.set("custom_bt_status", "idle")
    Setting.set("custom_bt_started_at", "")
    return jsonify({"status": "ok", "message": "実行フラグをリセットしました"})
