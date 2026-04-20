#!/usr/bin/env python3
"""
データ取得Cronジョブ
Yahoo Finance (yfinance) から為替データを取得してDBに保存する。
リクエスト制限なし。5分ごとのcronで直近1時間分を取得・差分保存。

Xサーバー Cronジョブ設定例:
  */5 * * * * /path/to/python3 /path/to/tasks/fetch_data.py >> /tmp/fetch_data.log 2>&1
"""

import sys
import os
import logging

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app
    from app.services.data_fetcher import fetch_and_store_all, fetch_and_store_macro
    from app.models.settings import Setting
    from datetime import datetime, timezone, timedelta

    JST = timezone(timedelta(hours=9))
    app = create_app()
    with app.app_context():
        logger.info("データ取得開始")
        results = fetch_and_store_all()
        for pair, tf_results in results.items():
            for tf, saved in tf_results.items():
                logger.info("  %s %s: %d件保存", pair, tf, saved)

        logger.info("マクロ指標取得開始")
        macro_results = fetch_and_store_macro()
        for pair, tf_results in macro_results.items():
            for tf, saved in tf_results.items():
                logger.info("  %s %s: %d件保存", pair, tf, saved)

        now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_data_fetch_at", now_str)
        Setting.set("last_macro_fetch_at", now_str)
        Setting.set("fetch_status", "done")
        logger.info("データ取得完了")


if __name__ == "__main__":
    main()
