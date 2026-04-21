#!/usr/bin/env python3
"""
バックテスト自動実行（cron用ラッパー）

run_ranking_bt.py はパラメータファイルが必要なため、
このスクリプトがデフォルトパラメータを用意して呼び出す。

---
Xサーバー Cronジョブ設定（市場セッション終了後に実行）:

  # 東京セッション終了後 (JST 15:30 = UTC 06:30)
  30 6 * * 1-5 /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/run_backtest_cron.py \
    >> /tmp/ranking_bt.log 2>&1

  # ロンドンセッション終了後 (JST 21:30 = UTC 12:30)
  30 12 * * 1-5 /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/run_backtest_cron.py \
    >> /tmp/ranking_bt.log 2>&1

  # NYセッション終了後 (JST 翌9:30 = UTC 00:30 / 曜日は火〜土)
  30 0 * * 2-6 /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/run_backtest_cron.py \
    >> /tmp/ranking_bt.log 2>&1

セッション時間（JST基準）:
  東京   09:00〜15:00  → 終了後 15:30 に実行
  ロンドン 15:00〜21:00  → 終了後 21:30 に実行
  NY    21:00〜翌09:00 → 終了後 翌09:30 に実行
---
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARAMS_FILE = "/tmp/ranking_bt_params.json"


def main():
    # パラメータファイルを生成（日付指定なし = DB内全データを対象）
    params = {
        "start_date":       "",   # 空 = 全期間
        "end_date":         "",
        "swing_start_date": "",
        "swing_end_date":   "",
        "force_full":       False,  # インクリメンタルモード（差分のみ計算）
    }
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False)
    logger.info("バックテスト cron 開始（インクリメンタルモード）")

    # run_ranking_bt の main を呼び出す
    from tasks.run_ranking_bt import main as bt_main
    bt_main()

    logger.info("バックテスト cron 完了")


if __name__ == "__main__":
    main()
