#!/usr/bin/env python3
"""
タスク実行スクリプト
action.phpから呼び出され、各種タスクを実行する。

使用方法:
  python3 run_task.py fetch_data
  python3 run_task.py backtest
  python3 run_task.py signals
  python3 run_task.py report
  python3 run_task.py save_settings '{"sl_pips":"20",...}'
  python3 run_task.py all
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def task_fetch_data(app):
    from app.services.data_fetcher import fetch_and_store_all
    logger.info("=== データ取得開始 ===")
    with app.app_context():
        fetch_and_store_all()
    logger.info("=== データ取得完了 ===")


def task_backtest(app):
    from app.services.backtester import run_all_backtests, save_backtest_results
    from app.services.data_fetcher import get_candles
    from app.models.settings import Setting
    from app.config import Config
    logger.info("=== バックテスト開始 ===")
    with app.app_context():
        initial_capital = Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL)
        sl_pips         = Setting.get_float("sl_pips",         Config.DEFAULT_SL_PIPS)
        tp_pips         = Setting.get_float("tp_pips",         Config.DEFAULT_TP_PIPS)
        backtest_hours  = Setting.get_int("backtest_hours",    Config.DEFAULT_BACKTEST_HOURS)

        for pair in Config.CURRENCY_PAIRS:
            for tf in Config.TIMEFRAMES:
                df = get_candles(pair, tf, limit=500)
                if df is None or df.empty:
                    logger.info("データなし: %s %s", pair, tf)
                    continue
                results = run_all_backtests(
                    pair, tf, df,
                    initial_capital=initial_capital,
                    sl_pips=sl_pips,
                    tp_pips=tp_pips,
                    backtest_hours=backtest_hours,
                )
                saved = save_backtest_results(results)
                logger.info("バックテスト完了: %s %s %d件保存", pair, tf, saved)
    logger.info("=== バックテスト完了 ===")


def task_signals(app):
    from app.services.signal_engine import run_signal_engine
    logger.info("=== シグナル更新開始 ===")
    with app.app_context():
        run_signal_engine()
    logger.info("=== シグナル更新完了 ===")


def task_report(app):
    from app.services.report_generator import create_and_save_report
    logger.info("=== レポート生成開始 ===")
    with app.app_context():
        report = create_and_save_report(send_email=True)
        if report:
            logger.info("レポート生成完了 ID=%s", report.id)
        else:
            logger.warning("レポート生成失敗")
    logger.info("=== レポート生成完了 ===")


def task_refetch_short_tf(app, timeframes=None):
    """
    短期足（5min / 30min）の price_data を削除して再取得する。
    O=H=L=C で保存されてしまったデータを正しい OHLC に置き換えるために使用。
    """
    from app import db
    from app.models.price_data import PriceData
    from app.services.data_fetcher import fetch_yfinance, save_price_data
    from app.config import Config

    if timeframes is None:
        timeframes = ["5min", "30min"]

    with app.app_context():
        for tf in timeframes:
            for pair in Config.CURRENCY_PAIRS:
                deleted = PriceData.query.filter_by(
                    currency_pair=pair, timeframe=tf
                ).delete()
                db.session.commit()
                logger.info("削除: %s %s %d件", pair, tf, deleted)

                df = fetch_yfinance(pair, tf)
                if df is not None and not df.empty:
                    saved = save_price_data(pair, tf, df)
                    logger.info("再取得: %s %s %d件保存", pair, tf, saved)
                else:
                    logger.warning("再取得失敗: %s %s", pair, tf)


def task_generate_static(app):
    """静的HTMLを再生成する（各タスク後に呼ばれる）"""
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    python = sys.executable
    ret = subprocess.call([python, script])
    if ret == 0:
        logger.info("静的HTML生成完了")
    else:
        logger.error("静的HTML生成失敗 (exit=%d)", ret)


def task_save_settings(app, data_json: str):
    from app.models.settings import Setting
    from app import db
    logger.info("=== 設定保存開始 ===")
    data = json.loads(data_json)
    with app.app_context():
        key_map = {
            "initial_capital": "initial_capital",
            "sl_pips": "sl_pips",
            "tp_pips": "tp_pips",
            "backtest_hours": "backtest_hours",
            "min_win_rate": "min_win_rate",
            "min_trades": "min_trades",
            "report_times": "report_times",
            "gemini_model": "gemini_model",
        }
        for field, key in key_map.items():
            if field in data:
                Setting.set(key, str(data[field]))
        db.session.commit()
        logger.info("設定保存完了: %s", list(data.keys()))
    # settings_data.json を更新
    task_generate_static(app)
    logger.info("=== 設定保存完了 ===")


def main():
    if len(sys.argv) < 2:
        print("Usage: run_task.py <action> [args...]")
        print("Actions: fetch_data, backtest, signals, report, save_settings, refetch_short_tf, all")
        sys.exit(1)

    action = sys.argv[1]

    from app import create_app
    app = create_app()

    try:
        if action == "fetch_data":
            task_fetch_data(app)
            task_generate_static(app)

        elif action == "backtest":
            task_backtest(app)
            task_generate_static(app)

        elif action == "signals":
            task_signals(app)
            task_generate_static(app)

        elif action == "report":
            task_report(app)
            task_generate_static(app)

        elif action == "save_settings":
            if len(sys.argv) < 3:
                logger.error("save_settings requires JSON argument")
                sys.exit(1)
            task_save_settings(app, sys.argv[2])

        elif action == "refetch_short_tf":
            # 5min / 30min の壊れたデータを削除して再取得
            tfs = sys.argv[2].split(",") if len(sys.argv) >= 3 else None
            task_refetch_short_tf(app, tfs)
            task_generate_static(app)

        elif action == "all":
            task_fetch_data(app)
            task_backtest(app)
            task_signals(app)
            task_generate_static(app)

        elif action == "generate_static":
            task_generate_static(app)

        else:
            logger.error("Unknown action: %s", action)
            sys.exit(1)

    except Exception as e:
        logger.exception("タスク実行エラー: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
