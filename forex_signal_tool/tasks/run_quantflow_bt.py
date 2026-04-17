#!/usr/bin/env python3
"""
QuantFlow 月次バックテスト（5分足スキャルピング）実行タスク
PHP admin の api.php から nohup で呼び出される。
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app
    from app.models.settings import Setting
    from app.services.quantflow_backtest import run_quantflow_backtest
    from datetime import datetime, timezone, timedelta

    JST = timezone(timedelta(hours=9))
    app = create_app()
    with app.app_context():
        sl_pips    = float(Setting.get("quantflow_sl_pips") or 10.0)
        tp_pips    = float(Setting.get("quantflow_tp_pips") or 20.0)
        start_date = Setting.get("quantflow_bt_start") or "2026-01-01"

        Setting.set("quantflow_bt_status", "running")
        logger.info("QuantFlow BT 開始: SL=%.1f TP=%.1f start=%s", sl_pips, tp_pips, start_date)

        try:
            result = run_quantflow_backtest(
                pair="USDJPY",
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                start_date=start_date,
            )
            if "error" in result:
                logger.error("BT エラー: %s", result["error"])
                Setting.set("quantflow_bt_status", "error")
            else:
                logger.info("BT 完了: %d トレード", result["total_trades"])
                now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
                Setting.set("last_quantflow_bt_at", now_str)
                Setting.set("quantflow_bt_status", "done")
        except Exception as e:
            logger.exception("BT 例外: %s", e)
            Setting.set("quantflow_bt_status", "error")


if __name__ == "__main__":
    main()
