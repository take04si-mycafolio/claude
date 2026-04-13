#!/usr/bin/env python3
"""
日足データ取得 Cron ジョブ（Alpha Vantage 専用）

FX 日足は NY クローズ（22:00 UTC = 翌 07:00 JST）で確定する。
月〜土（JST）の 07:30 に1回だけ実行する。

Alpha Vantage 無料プラン: 25 リクエスト/日・3 通貨ペア = 3 リクエスト/実行

Xserver Cron 設定例（JST 07:30、月〜土）:
  30 22 * * 0-4 /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/fetch_daily.py \
    >> /home/xs539690/forex_project/logs/fetch_daily.log 2>&1

  ※ UTC 22:30（日〜木）= JST 07:30（月〜金）
     土曜 JST 07:30 = UTC 金曜 22:30 なので上記で月〜土をカバー
"""

import sys
import os
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def main():
    from app import create_app
    from app.services.data_fetcher import fetch_alphavantage_daily, save_price_data
    from app.models.settings import Setting
    from app.config import Config

    # JST で曜日チェック（月=0 〜 土=5、日=6 は除外）
    now_jst = datetime.now(JST)
    weekday = now_jst.weekday()  # 0=月 〜 6=日
    if weekday == 6:  # 日曜はスキップ
        logger.info("日曜日のためスキップ（FX 市場休場）")
        return

    app = create_app()
    with app.app_context():
        logger.info("===== 日足データ取得 開始（Alpha Vantage）%s JST =====",
                    now_jst.strftime("%Y/%m/%d %H:%M"))
        total_saved = 0

        for pair in Config.CURRENCY_PAIRS:
            logger.info("取得中: %s daily", pair)
            df = fetch_alphavantage_daily(pair)
            if df is not None and not df.empty:
                saved = save_price_data(pair, "daily", df)
                total_saved += saved
                logger.info("  %s daily: %d件保存", pair, saved)
            else:
                logger.warning("  %s daily: データ取得失敗", pair)

        now_str = now_jst.strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_daily_fetch_at", now_str)
        logger.info("===== 日足データ取得 完了: %d件 =====", total_saved)


if __name__ == "__main__":
    main()
