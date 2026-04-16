#!/usr/bin/env python3
"""
シグナル更新のみ実行（バックテストなし）→ 静的HTML再生成

Xserver Cron 設定例（7分ごと）:
  */7 * * * * /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/run_signals_only.py \
    >> /home/xs539690/forex_project/logs/signals.log 2>&1
"""

import sys
import os
import subprocess
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app
    from app.models.settings import Setting
    from app.services.signal_engine import run_signal_engine
    from datetime import datetime, timezone, timedelta

    JST = timezone(timedelta(hours=9))
    app = create_app()
    with app.app_context():
        logger.info("シグナル生成開始")
        signal_results = run_signal_engine()
        for pair, tf_results in signal_results.items():
            for tf, count in tf_results.items():
                logger.info("  %s %s: %d個のシグナル", pair, tf, count)
        now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_signal_update_at", now_str)
        Setting.set("signal_status", "done")
        logger.info("シグナル生成完了")

    # 静的HTML再生成・デプロイ
    logger.info("静的HTML生成開始")
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    ret = subprocess.call([sys.executable, script])
    if ret == 0:
        logger.info("静的HTML生成完了")
    else:
        logger.error("静的HTML生成失敗 (exit=%d)", ret)


if __name__ == "__main__":
    main()

