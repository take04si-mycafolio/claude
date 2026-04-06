#!/usr/bin/env python3
"""
レポート配信Cronジョブ
設定された時刻にレポートを生成・メール送信する。

Xサーバー Cronジョブ設定例:
  # UTC 6:00, 12:00, 18:00 に実行
  0 6,12,18 * * * cd /home/user/public_html && python3 tasks/send_report.py >> logs/report.log 2>&1
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


def should_run_now(report_times_str: str) -> bool:
    """
    設定された配信時刻に現在時刻が合致するか確認する（±5分の許容）。
    report_times_str: "06:00,12:00,18:00" 形式
    """
    now = datetime.now(timezone.utc)
    current_hm = now.hour * 60 + now.minute

    for time_str in report_times_str.split(","):
        time_str = time_str.strip()
        try:
            h, m = map(int, time_str.split(":"))
            target_hm = h * 60 + m
            if abs(current_hm - target_hm) <= 5:
                return True
        except (ValueError, AttributeError):
            continue
    return False


def main():
    from app import create_app
    from app.models.settings import Setting
    from app.services.report_generator import create_and_save_report
    from app.services.email_sender import send_report_email

    app = create_app()
    with app.app_context():
        report_times = Setting.get("report_times", "06:00,12:00,18:00")

        # --force オプションがある場合は時刻チェックをスキップ
        force = "--force" in sys.argv
        if not force and not should_run_now(report_times):
            logger.info("配信時刻外のため実行をスキップ (現在: %s UTC, 設定: %s)",
                        datetime.now(timezone.utc).strftime("%H:%M"), report_times)
            return

        logger.info("レポート生成開始")
        report_id = create_and_save_report()
        if report_id is None:
            logger.error("レポート生成失敗")
            return
        logger.info("レポート生成完了 (ID: %d)", report_id)

        logger.info("メール送信開始")
        ok = send_report_email(report_id)
        if ok:
            logger.info("メール送信完了")
        else:
            logger.warning("メール送信失敗（レポートはDBに保存済み）")


if __name__ == "__main__":
    main()
