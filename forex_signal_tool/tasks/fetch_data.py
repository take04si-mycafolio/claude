#!/usr/bin/env python3
"""
データ取得Cronジョブ
Alpha Vantage APIから為替データを取得してDBに保存する。

Xサーバー Cronジョブ設定例:
  # 1日2回 (無料プランの25リクエスト/日制限に注意)
  0 0,12 * * * cd /home/user/public_html && python3 tasks/fetch_data.py >> logs/fetch.log 2>&1
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
    from app.services.data_fetcher import fetch_and_store_all

    app = create_app()
    with app.app_context():
        logger.info("データ取得開始")
        results = fetch_and_store_all()
        for pair, tf_results in results.items():
            for tf, saved in tf_results.items():
                logger.info("  %s %s: %d件保存", pair, tf, saved)
        logger.info("データ取得完了")


if __name__ == "__main__":
    main()
