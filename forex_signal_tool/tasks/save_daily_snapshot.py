#!/usr/bin/env python3
"""
日次スナップショット保存タスク

backtest_results テーブルの現在値を backtest_daily_snapshots に保存する。
「今日の勝率」「今週の傾向」「ランキング変動」などの時系列分析に使用。

Xサーバー Cronジョブ設定例:
  # 毎日 0時00分に実行（バックテスト実行後に自動的に呼ばれるため通常不要）
  0 0 * * * cd /home/user/public_html && python3 tasks/save_daily_snapshot.py >> logs/snapshot.log 2>&1
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
    from app.services.backtester import save_daily_snapshot

    app = create_app()
    with app.app_context():
        count = save_daily_snapshot()
        logger.info("完了: %d件のスナップショットを保存しました", count)


if __name__ == "__main__":
    main()
