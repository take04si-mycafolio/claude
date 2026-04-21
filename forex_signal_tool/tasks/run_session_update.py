#!/usr/bin/env python3
"""
市場セッション別ランキング・トレード履歴を単独更新するタスク

フルバックテストは行わず、既存の simulation_trades から
セッション別データ（session_ranking_results / session_trade_history）のみ再計算する。
管理画面から手動実行、またはバックテスト後の個別再集計に使用。
"""
import sys
import os
import json
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARAMS_FILE = "/tmp/session_update_params.json"
RESULT_FILE = "/tmp/session_update_result.json"


def write_status(status: str, message: str):
    data = {
        "status":     status,
        "message":    message,
        "updated_at": time.strftime("%Y/%m/%d %H:%M:%S"),
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    if not os.path.exists(PARAMS_FILE):
        write_status("error", "パラメータファイルが見つかりません")
        return

    with open(PARAMS_FILE, encoding="utf-8") as f:
        params = json.load(f)

    days        = max(1, min(90, int(params.get("days", 30))))
    target_date = params.get("target_date") or None   # None = 当日
    date_label  = target_date if target_date else "当日"

    logger.info("セッション別データ更新開始（%s・過去%d日）", date_label, days)
    write_status("running", f"セッション別データ集計中（{date_label}・過去{days}日）...")

    from app import create_app
    from tasks.run_ranking_bt import save_session_data_to_db

    app = create_app()
    with app.app_context():
        try:
            save_session_data_to_db(days=days, target_date=target_date)
            logger.info("セッション別データ保存完了")
        except Exception as exc:
            logger.error("セッションデータ保存失敗: %s", exc)
            write_status("error", f"保存失敗: {exc}")
            return

    write_status("running", "静的ページ生成中...")
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    ret    = subprocess.call([sys.executable, script])

    if ret == 0:
        write_status("done", f"完了（{date_label}・過去{days}日のセッションデータ更新・静的ページ生成済み）")
    else:
        write_status("done", f"セッションデータ更新完了 ※静的ページ生成失敗")
    logger.info("セッション別データ更新完了")


if __name__ == "__main__":
    main()
