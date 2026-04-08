#!/usr/bin/env python3
"""
静的HTML生成スクリプト
DBのデータを読み込み、各ページのHTMLを生成して public_html に保存する。

Cronジョブ設定例（30分ごと）:
  */30 * * * * cd /home/xs539690 && /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/generate_static.py >> \
    /home/xs539690/forex_project/logs/generate.log 2>&1
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))


def utc_str_to_jst(ts) -> str:
    """UTC datetime / str を JST文字列（Y/m/d H:M）に変換"""
    if ts is None:
        return ""
    try:
        if isinstance(ts, str):
            ts = ts[:19].replace("T", " ")
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elif hasattr(ts, "tzinfo"):
            dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            return str(ts)[:16]
        return dt.astimezone(JST).strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(ts)[:16]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PUBLIC_HTML = "/home/xs539690/fx-trend.net/public_html"


def get_pair_data(pair: str) -> dict:
    from app.services.data_fetcher import get_latest_price
    from app.models.signal import TradingSignal
    from app.models.backtest import BacktestResult

    price = get_latest_price(pair)

    signals = (
        TradingSignal.query
        .filter_by(currency_pair=pair, is_active=True)
        .order_by(TradingSignal.confidence_score.desc())
        .limit(10).all()
    )
    top_bt = (
        BacktestResult.query
        .filter_by(currency_pair=pair)
        .filter(BacktestResult.win_rate >= 55)
        .order_by(BacktestResult.win_rate.desc())
        .limit(5).all()
    )

    buy_count = sum(1 for s in signals if s.signal_type == "BUY")
    sell_count = sum(1 for s in signals if s.signal_type == "SELL")

    if buy_count > sell_count:
        overall = "BUY"
    elif sell_count > buy_count:
        overall = "SELL"
    else:
        overall = "NEUTRAL"

    # 価格タイムスタンプをJSTに変換
    price_dict = None
    if price:
        price_dict = price if isinstance(price, dict) else {
            k: getattr(price, k, None) for k in ("close", "open", "high", "low", "timestamp")
        }
        ts = price_dict.get("timestamp")
        price_dict["timestamp_jst"] = utc_str_to_jst(ts)

    return {
        "pair": pair,
        "display": f"{pair[:3]}/{pair[3:]}",
        "price": price_dict,
        "signals": [s.to_dict() for s in signals],
        "buy_count": buy_count,
        "sell_count": sell_count,
        "overall": overall,
        "top_backtest": [r.to_dict() for r in top_bt],
    }


def get_all_signals() -> list:
    from app.models.signal import TradingSignal
    from app.config import Config
    result = []
    for pair in Config.CURRENCY_PAIRS:
        sigs = (
            TradingSignal.query
            .filter_by(currency_pair=pair, is_active=True)
            .order_by(TradingSignal.confidence_score.desc())
            .all()
        )
        result.extend([s.to_dict() for s in sigs])
    return sorted(result, key=lambda x: x.get("confidence_score") or 0, reverse=True)


def get_all_backtest() -> list:
    from app.models.backtest import BacktestResult
    from app.config import Config
    result = []
    for pair in Config.CURRENCY_PAIRS:
        recs = (
            BacktestResult.query
            .filter_by(currency_pair=pair)
            .order_by(BacktestResult.win_rate.desc())
            .limit(20).all()
        )
        result.extend([r.to_dict() for r in recs])
    return sorted(result, key=lambda x: x.get("win_rate") or 0, reverse=True)


def get_reports() -> list:
    from app.models.report import AiReport
    recs = AiReport.query.order_by(AiReport.created_at.desc()).limit(10).all()
    return [r.to_dict() for r in recs]


CHART_TIMEFRAMES = ["15min", "1hr", "4hr", "daily"]
CHART_LIMITS = {"15min": 120, "1hr": 200, "4hr": 150, "daily": 300}


def _to_unix(ts) -> int:
    """datetime / str / timestamp → Unix秒"""
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        from datetime import datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return int(datetime.strptime(ts[:19], fmt).timestamp())
            except ValueError:
                pass
        return 0
    if hasattr(ts, "timestamp"):
        return int(ts.timestamp())
    return 0


def get_chart_data(pair: str, timeframe: str) -> dict:
    """ローソク足 + テクニカル指標データを返す"""
    import pandas as pd
    from app.services.data_fetcher import get_candles

    limit = CHART_LIMITS.get(timeframe, 200)
    df = get_candles(pair, timeframe, limit)
    if df is None or df.empty:
        return {"candles": [], "sma20": [], "sma50": [], "ema21": [],
                "bb_upper": [], "bb_lower": [], "rsi": [], "signals": []}

    df = df.sort_values("timestamp").reset_index(drop=True)
    close = df["close"].astype(float)

    times = [_to_unix(row["timestamp"]) for _, row in df.iterrows()]

    candles = [
        {"time": times[i],
         "open":  round(float(df.iloc[i]["open"]),  3),
         "high":  round(float(df.iloc[i]["high"]),  3),
         "low":   round(float(df.iloc[i]["low"]),   3),
         "close": round(float(df.iloc[i]["close"]), 3)}
        for i in range(len(df))
    ]

    def to_series(series):
        return [{"time": times[i], "value": round(float(v), 5)}
                for i, v in enumerate(series) if not pd.isna(v)]

    # SMA
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    # EMA21
    ema21 = close.ewm(span=21, adjust=False).mean()
    # Bollinger Bands (20, 2)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    # RSI(14) — Wilder's smoothing
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    # バックテスト取引マーカー（上位インジケーターの直近トレード）
    from app.models.backtest import BacktestResult
    from app.models.settings import Setting
    from app.services.backtester import get_recent_trades

    trade_markers = []
    try:
        top_bt = (BacktestResult.query
                  .filter_by(currency_pair=pair, timeframe=timeframe)
                  .filter(BacktestResult.win_rate >= 50)
                  .order_by(BacktestResult.win_rate.desc())
                  .first())
        if top_bt:
            ic = Setting.get_float("initial_capital", 1_000_000)
            sl = Setting.get_float("sl_pips", 20)
            tp = Setting.get_float("tp_pips", 40)
            bh = Setting.get_int("backtest_hours", 12)
            trades = get_recent_trades(pair, timeframe, df,
                                       top_bt.indicator_name, ic, sl, tp, bh,
                                       limit=30)
            for t in trades:
                et = _to_unix(t["entry_ts"])
                xt = _to_unix(t["exit_ts"]) if t.get("exit_ts") else None
                sig = t["signal"]
                outcome = t.get("outcome")
                is_buy = sig == "BUY"

                # エントリーマーカー
                trade_markers.append({
                    "time": et,
                    "position": "belowBar" if is_buy else "aboveBar",
                    "color": "#22c55e" if is_buy else "#ef4444",
                    "shape": "arrowUp" if is_buy else "arrowDown",
                    "text": "IN",
                    "size": 1,
                })
                # エグジットマーカー
                if xt:
                    win = outcome == "WIN"
                    trade_markers.append({
                        "time": xt,
                        "position": "aboveBar" if is_buy else "belowBar",
                        "color": "#22c55e" if win else "#ef4444",
                        "shape": "circle",
                        "text": "TP✓" if win else "SL✗",
                        "size": 1,
                    })
    except Exception as e:
        logger.warning("Trade markers error %s %s: %s", pair, timeframe, e)

    # アクティブシグナルのTP/SLレベル
    from app.models.signal import TradingSignal
    active_sig = (TradingSignal.query
                  .filter_by(currency_pair=pair, is_active=True)
                  .order_by(TradingSignal.confidence_score.desc())
                  .first())
    tp_level = float(active_sig.tp_price) if active_sig and active_sig.tp_price else None
    sl_level = float(active_sig.sl_price) if active_sig and active_sig.sl_price else None
    entry_level = float(active_sig.entry_price) if active_sig and active_sig.entry_price else None
    active_signal_type = active_sig.signal_type if active_sig else None

    return {
        "candles":     candles,
        "sma20":       to_series(sma20),
        "sma50":       to_series(sma50),
        "ema21":       to_series(ema21),
        "bb_upper":    to_series(bb_upper),
        "bb_lower":    to_series(bb_lower),
        "rsi":         [{"time": times[i], "value": round(float(v), 2)}
                        for i, v in enumerate(rsi) if not pd.isna(v)],
        "trades":      sorted(trade_markers, key=lambda x: x["time"]),
        "tp_level":    tp_level,
        "sl_level":    sl_level,
        "entry_level": entry_level,
        "signal_type": active_signal_type,
    }


def get_settings() -> dict:
    from app.models.settings import Setting
    return {
        "initial_capital": Setting.get("initial_capital", "1000000"),
        "sl_pips": Setting.get("sl_pips", "20"),
        "tp_pips": Setting.get("tp_pips", "40"),
        "backtest_hours": Setting.get("backtest_hours", "12"),
        "min_win_rate": Setting.get("min_win_rate", "55"),
        "min_trades": Setting.get("min_trades", "3"),
        "report_times": Setting.get("report_times", "06:00,12:00,18:00"),
        "gemini_model": Setting.get("gemini_model", "gemini-1.5-flash"),
    }


def render_html(app, template_name: str, context: dict) -> str:
    from flask import render_template
    with app.app_context():
        with app.test_request_context("/"):
            return render_template(template_name, **context)


def save(filename: str, html: str):
    path = Path(PUBLIC_HTML) / filename
    path.write_text(html, encoding="utf-8")
    logger.info("Generated: %s", filename)


def main():
    from app import create_app
    from app.config import Config

    app = create_app()
    with app.app_context():
        updated_at = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
        pairs = Config.CURRENCY_PAIRS
        pair_pages = {"USDJPY": "index.html", "GBPJPY": "gbpjpy.html", "EURJPY": "eurjpy.html"}

        # 各通貨ペアのダッシュボード
        for pair, filename in pair_pages.items():
            data = get_pair_data(pair)
            html = render_html(app, "dashboard_static.html", {
                "pairs": pairs,
                "pair_pages": pair_pages,
                "current_pair": pair,
                "data": data,
                "updated_at": updated_at,
                "active_page": "home",
            })
            save(filename, html)

        # シグナル一覧
        all_signals = get_all_signals()
        html = render_html(app, "signals_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "signals": all_signals,
            "updated_at": updated_at,
            "active_page": "signals",
        })
        save("signals.html", html)

        # バックテスト
        all_bt = get_all_backtest()
        html = render_html(app, "backtest_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "results": all_bt,
            "updated_at": updated_at,
            "active_page": "backtest",
        })
        save("backtest.html", html)

        # レポート
        reports = get_reports()
        html = render_html(app, "reports_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "reports": reports,
            "updated_at": updated_at,
            "active_page": "reports",
        })
        save("reports.html", html)

        # 設定ページ（静的テンプレートをそのままコピー）
        html = render_html(app, "settings_static.html", {})
        save("settings.html", html)

        # チャートデータ JSON（ペア×タイムフレーム）
        chart_dir = Path(PUBLIC_HTML) / "chart_data"
        chart_dir.mkdir(exist_ok=True)
        for pair in pairs:
            for tf in CHART_TIMEFRAMES:
                try:
                    cdata = get_chart_data(pair, tf)
                    fname = f"{pair.lower()}_{tf}.json"
                    (chart_dir / fname).write_text(
                        json.dumps(cdata, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8"
                    )
                    logger.info("Chart JSON: %s", fname)
                except Exception as e:
                    logger.warning("Chart JSON error %s %s: %s", pair, tf, e)

        # 設定ページ用JSONも出力
        settings = get_settings()
        settings_path = Path(PUBLIC_HTML) / "settings_data.json"
        settings_path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        logger.info("Settings JSON saved")

        logger.info("Static site generation complete")


if __name__ == "__main__":
    main()
