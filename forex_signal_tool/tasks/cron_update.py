#!/usr/bin/env python3
"""
定期更新ジョブ（Cron から呼ぶ1本のスクリプト）
  1. 価格データ取得
  2. シグナル更新
  3. 静的HTML生成・デプロイ

Xserver Cron 設定例（30分ごと）:
  */30 * * * * /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/cron_update.py \
    >> /home/xs539690/forex_project/logs/cron_update.log 2>&1
"""

import sys
import os
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app
    from app.models.settings import Setting
    from datetime import datetime, timezone

    app = create_app()
    now = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
    logger.info("========== cron_update 開始 %s ==========", now)

    # ---- 1. データ取得 ----
    try:
        from app.services.data_fetcher import fetch_and_store_all
        with app.app_context():
            logger.info("--- データ取得 開始 ---")
            results = fetch_and_store_all()
            total = sum(v for tf_r in results.values() for v in tf_r.values())
            now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
            Setting.set("last_data_fetch_at", now_str)
            Setting.set("fetch_status", "done")
            logger.info("--- データ取得 完了: %d件 ---", total)
    except Exception as e:
        logger.exception("データ取得 エラー: %s", e)

    # ---- 2. シグナル更新 ----
    try:
        from app.services.signal_engine import run_signal_engine
        with app.app_context():
            logger.info("--- シグナル更新 開始 ---")
            signal_results = run_signal_engine()
            total_sig = sum(v for tf_r in signal_results.values() for v in tf_r.values())
            now_str2 = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
            Setting.set("last_signal_update_at", now_str2)
            Setting.set("signal_status", "done")
            logger.info("--- シグナル更新 完了: %d件 ---", total_sig)
    except Exception as e:
        logger.exception("シグナル更新 エラー: %s", e)

    # ---- 3. 静的HTML生成・デプロイ ----
    try:
        logger.info("--- 静的HTML生成 開始 ---")
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "generate_static.py")
        python = sys.executable
        ret = subprocess.call([python, script])
        if ret == 0:
            logger.info("--- 静的HTML生成 完了 ---")
        else:
            logger.error("--- 静的HTML生成 失敗 (exit=%d) ---", ret)
    except Exception as e:
        logger.exception("静的HTML生成 エラー: %s", e)

    logger.info("========== cron_update 完了 ==========")


if __name__ == "__main__":
    main()
