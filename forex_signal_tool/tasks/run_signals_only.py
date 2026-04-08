#!/usr/bin/env python3
"""
シグナル更新のみ実行（バックテストなし）
PHP 管理パネルの「シグナル更新」ボタンから nohup で起動される。
"""

import sys
import os
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
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_signal_update_at", now_str)
        Setting.set("signal_status", "done")
        logger.info("シグナル生成完了")


if __name__ == "__main__":
    main()
