#!/usr/bin/env python3
"""
シミュレーショントレードを全削除して4月1日から再生成するスクリプト

使い方:
  /home/xs539690/forex_env/bin/python3 forex_signal_tool/tasks/reset_simulation_trades.py
"""

import sys
import os
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

START_DATE = datetime(2026, 4, 1, 0, 0, 0)  # 4月1日から


def main():
    from app import create_app, db
    from app.config import Config
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade
    from app.models.settings import Setting
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_all_backtests, save_backtest_results

    app = create_app()
    with app.app_context():

        # ---- 全削除 ----
        st_count = SimulationTrade.query.count()
        br_count = BacktestResult.query.count()
        logger.info("削除前: simulation_trades=%d件, backtest_results=%d件", st_count, br_count)

        SimulationTrade.query.delete()
        BacktestResult.query.delete()
        db.session.commit()
        logger.info("全件削除完了")

        # ---- 設定値 ----
        initial_capital = Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL)
        sl_pips         = Setting.get_float("sl_pips",         Config.DEFAULT_SL_PIPS)
        tp_pips         = Setting.get_float("tp_pips",         Config.DEFAULT_TP_PIPS)

        logger.info("設定: 初期資金=¥%s, SL=%spips, TP=%spips",
                    f"{initial_capital:,.0f}", sl_pips, tp_pips)
        logger.info("対象期間: %s 以降", START_DATE.strftime("%Y-%m-%d"))

        total_saved = 0
        for pair in Config.CURRENCY_PAIRS:
            for tf in Config.TIMEFRAMES:
                logger.info("処理中: %s %s", pair, tf)

                # 十分な件数を取得（4月1日分をカバーするため多めに）
                df = get_candles(pair, tf, limit=2000)
                if df.empty:
                    logger.warning("  データなし: %s %s", pair, tf)
                    continue

                # 4月1日以降にフィルタ
                df = df[df['timestamp'] >= START_DATE].reset_index(drop=True)
                if len(df) < 10:
                    logger.warning("  4月1日以降のデータが%d件のみ（スキップ）", len(df))
                    continue

                logger.info("  使用データ: %d本 (%s 〜 %s)",
                            len(df),
                            str(df['timestamp'].min())[:16],
                            str(df['timestamp'].max())[:16])

                results = run_all_backtests(
                    pair=pair, timeframe=tf, df=df,
                    initial_capital=initial_capital,
                    sl_pips=sl_pips, tp_pips=tp_pips,
                    backtest_hours=99999,  # 全期間
                )
                saved = save_backtest_results(results)
                total_saved += saved
                logger.info("  保存: %d件", saved)

        logger.info("完了: 合計%d件のバックテスト結果を保存", total_saved)

        now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_backtest_at", now_str)
        Setting.set("backtest_status", "done")


if __name__ == "__main__":
    main()
