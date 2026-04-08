#!/usr/bin/env python3
"""
分析実行Cronジョブ
バックテストとシグナル生成を実行する。

Xサーバー Cronジョブ設定例:
  # 30分ごとに実行
  */30 * * * * cd /home/user/public_html && python3 tasks/run_analysis.py >> logs/analysis.log 2>&1
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app
    from app.config import Config
    from app.models.settings import Setting
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_all_backtests, save_backtest_results
    from app.services.signal_engine import run_signal_engine
    from datetime import datetime, timezone

    app = create_app()
    with app.app_context():
        initial_capital = Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL)
        sl_pips = Setting.get_float("sl_pips", Config.DEFAULT_SL_PIPS)
        tp_pips = Setting.get_float("tp_pips", Config.DEFAULT_TP_PIPS)
        backtest_hours = Setting.get_int("backtest_hours", Config.DEFAULT_BACKTEST_HOURS)

        logger.info("バックテスト開始 (初期資金: ¥%s, SL: %spips, TP: %spips)",
                    f"{initial_capital:,.0f}", sl_pips, tp_pips)

        total_saved = 0
        for pair in Config.CURRENCY_PAIRS:
            for tf in Config.TIMEFRAMES:
                df = get_candles(pair, tf, limit=500)
                if df.empty:
                    logger.warning("データなし: %s %s", pair, tf)
                    continue
                results = run_all_backtests(
                    pair=pair, timeframe=tf, df=df,
                    initial_capital=initial_capital,
                    sl_pips=sl_pips, tp_pips=tp_pips,
                    backtest_hours=backtest_hours,
                )
                saved = save_backtest_results(results)
                total_saved += saved
                logger.info("  %s %s: バックテスト%d件保存", pair, tf, saved)

        logger.info("バックテスト完了: 合計%d件", total_saved)
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_backtest_at", now_str)

        logger.info("シグナル生成開始")
        signal_results = run_signal_engine()
        for pair, tf_results in signal_results.items():
            for tf, count in tf_results.items():
                logger.info("  %s %s: %d個のシグナル", pair, tf, count)
        logger.info("シグナル生成完了")
        now_str2 = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_signal_update_at", now_str2)


if __name__ == "__main__":
    main()
