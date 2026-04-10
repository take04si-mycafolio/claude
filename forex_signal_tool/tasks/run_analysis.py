#!/usr/bin/env python3
"""
分析実行Cronジョブ
シグナル生成のみ実行する。
※ランキング用バックテストは SEO管理画面 → ランキング管理 から手動実行すること。

Xサーバー Cronジョブ設定例:
  # 30分ごとに実行
  */30 * * * * cd /home/user/public_html && python3 tasks/run_analysis.py >> logs/analysis.log 2>&1
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
    from datetime import datetime, timezone

    app = create_app()
    with app.app_context():
        logger.info("シグナル生成開始")
        signal_results = run_signal_engine()
        for pair, tf_results in signal_results.items():
            for tf, count in tf_results.items():
                logger.info("  %s %s: %d個のシグナル", pair, tf, count)
        logger.info("シグナル生成完了")
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_signal_update_at", now_str)
        Setting.set("signal_status", "done")

    # 静的HTML再生成
    logger.info("静的HTML生成開始")
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    ret = subprocess.call([sys.executable, script])
    if ret == 0:
        logger.info("静的HTML生成完了")
    else:
        logger.error("静的HTML生成失敗 (exit=%d)", ret)


if __name__ == "__main__":
    main()


