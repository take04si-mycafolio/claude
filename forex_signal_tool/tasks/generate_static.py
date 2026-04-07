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
from datetime import datetime, timezone
from pathlib import Path

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

    return {
        "pair": pair,
        "display": f"{pair[:3]}/{pair[3:]}",
        "price": price,
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
        updated_at = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
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

        # 設定ページ用JSONも出力
        settings = get_settings()
        settings_path = Path(PUBLIC_HTML) / "settings_data.json"
        settings_path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        logger.info("Settings JSON saved")

        logger.info("Static site generation complete")


if __name__ == "__main__":
    main()
