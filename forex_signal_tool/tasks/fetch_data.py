#!/usr/bin/env python3
"""
為替ペア価格取得 Cronジョブ（USDJPY / GBPJPY / EURJPY）
yfinance から全タイムフレームの価格データを取得してDBに保存する。
マクロ指標（DXY / 米金利）は fetch_macro_15min.py が担当。

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


def purge_weekend_data(db):
    """price_data テーブルから週末（土・日）データを削除する。"""
    from sqlalchemy import text
    # MySQL: DAYOFWEEK は 1=日, 7=土
    result = db.session.execute(text(
        "DELETE FROM price_data WHERE DAYOFWEEK(`timestamp`) IN (1, 7)"
    ))
    db.session.commit()
    deleted = result.rowcount
    if deleted:
        logger.info("週末データ自動削除: %d件", deleted)


def main():
    from app import create_app, db
    from app.services.data_fetcher import fetch_and_store_all
    from app.models.settings import Setting
    from datetime import datetime, timezone, timedelta

    JST = timezone(timedelta(hours=9))
    app = create_app()
    with app.app_context():
        logger.info("為替ペア価格取得開始")
        results = fetch_and_store_all()
        for pair, tf_results in results.items():
            for tf, saved in tf_results.items():
                logger.info("  %s %s: %d件保存", pair, tf, saved)

        purge_weekend_data(db)

        now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_data_fetch_at", now_str)
        Setting.set("fetch_status", "done")
        logger.info("為替ペア価格取得完了")


if __name__ == "__main__":
    main()
