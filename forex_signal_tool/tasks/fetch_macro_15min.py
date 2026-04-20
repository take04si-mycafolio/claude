#!/usr/bin/env python3
"""
マクロ指標（米10年債利回り US10Y / 米国債先物 USBF / ドルインデックス DXY）
の最新 1hr データを yfinance から取得して DB に保存する。
QuantFlow 5分足スコア計算がマクロ指標を使うため、5分ごとに実行する。

Xserver cron 設定例（5分ごと）:
  */5 * * * * /path/to/python3 /path/to/tasks/fetch_macro_15min.py \
    >> /tmp/fetch_macro.log 2>&1
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
    from app.services.data_fetcher import fetch_and_store_macro
    from app.models.settings import Setting
    from datetime import datetime, timezone, timedelta

    JST = timezone(timedelta(hours=9))
    app = create_app()
    with app.app_context():
        logger.info("マクロ指標取得開始")
        results = fetch_and_store_macro()
        for pair, tf_results in results.items():
            for tf, saved in tf_results.items():
                logger.info("  %s %s: %d件保存", pair, tf, saved)
        now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_macro_fetch_at", now_str)
        logger.info("マクロ指標取得完了")


if __name__ == "__main__":
    main()
