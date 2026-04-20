#!/usr/bin/env python3
"""
バックテスト自動実行（cron用ラッパー）

run_ranking_bt.py はパラメータファイルが必要なため、
このスクリプトがデフォルトパラメータを用意して呼び出す。

Xサーバー Cronジョブ設定例（2時間ごと）:
  0 */2 * * * /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/run_backtest_cron.py \
    >> /tmp/ranking_bt.log 2>&1
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
