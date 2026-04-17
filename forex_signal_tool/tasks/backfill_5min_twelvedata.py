#!/usr/bin/env python3
"""
Twelve Data API を使って 5 分足データを遡及取得し DB に保存するスクリプト。

対象: USDJPY → GBPJPY → EURJPY
期間: 2026-01-01 00:00 UTC 〜 2026-03-31 22:55 UTC
      （DB には既に 2026-03-31 23:00〜 が存在するため重複上書きは無害）

使い方:
    python tasks/backfill_5min_twelvedata.py

レート制限: Free プラン 8 req/min → リクエスト間 10 秒 sleep
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_KEY    = "3885ff93dfc3409da028a3912f3f473d"
BASE_URL   = "https://api.twelvedata.com/time_series"
OUTPUTSIZE = 5000   # 1 リクエストあたりの最大ローソク足数
SLEEP_SEC  = 12     # レート制限: 8 req/min → 7.5s 必要、余裕をもって 12s

PAIRS = [
    ("USDJPY", "USD/JPY"),
    ("GBPJPY", "GBP/JPY"),
    ("EURJPY", "EUR/JPY"),
]

# 5000 本 × 5min = 25000 分 ≈ 17.36 日
CHUNK_MINUTES = OUTPUTSIZE * 5

FILL_START = datetime(2026, 1, 1,  0,  0, 0)   # UTC naive
FILL_END   = datetime(2026, 3, 31, 22, 55, 0)  # UTC naive（既存の 23:00 の直前）


def fetch_chunk(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Twelve Data API から 1 チャンクを取得して DataFrame で返す。
    空の場合は空 DataFrame を返す。
    """
    params = {
        "symbol":     symbol,
        "interval":   "5min",
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date":   end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "outputsize": OUTPUTSIZE,
        "order":      "ASC",
        "timezone":   "UTC",
        "apikey":     API_KEY,
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("  HTTPエラー: %s", e)
        return pd.DataFrame()

    if data.get("status") == "error":
        logger.error("  APIエラー: %s", data.get("message", data))
        return pd.DataFrame()

    values = data.get("values", [])
    if not values:
        logger.warning("  データなし (start=%s)", start_dt)
        return pd.DataFrame()

    rows = []
    for v in values:
        rows.append({
            "timestamp": datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S"),
            "open":      float(v["open"]),
            "high":      float(v["high"]),
            "low":       float(v["low"]),
            "close":     float(v["close"]),
            "volume":    float(v.get("volume", 0)),
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])  # UTC naive
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def backfill_pair(pair_db: str, pair_api: str, app):
    """1 ペア分のデータをチャンク単位で取得・保存する。"""
    from app.services.data_fetcher import save_price_data

    logger.info("=== %s 開始 ===", pair_db)
    total_saved = 0
    chunk_start = FILL_START

    while chunk_start <= FILL_END:
        chunk_end = min(
            chunk_start + timedelta(minutes=CHUNK_MINUTES - 5),
            FILL_END,
        )

        logger.info("  取得: %s 〜 %s",
                    chunk_start.strftime("%Y-%m-%d %H:%M"),
                    chunk_end.strftime("%Y-%m-%d %H:%M"))

        df = fetch_chunk(pair_api, chunk_start, chunk_end)

        if df.empty:
            # 空チャンクでも次に進む（週末・祝日等）
            chunk_start = chunk_end + timedelta(minutes=5)
            time.sleep(SLEEP_SEC)
            continue

        # FILL_END を超えた行をトリミング
        df = df[df["timestamp"] <= FILL_END].reset_index(drop=True)

        if not df.empty:
            with app.app_context():
                saved = save_price_data(pair_db, "5min", df)
            total_saved += saved
            logger.info("    → %d件保存 (取得 %d行)", saved, len(df))

            # 次チャンクの開始 = 最後のタイムスタンプ + 5分
            last_ts = df["timestamp"].iloc[-1]
            chunk_start = last_ts.to_pydatetime() + timedelta(minutes=5)
        else:
            chunk_start = chunk_end + timedelta(minutes=5)

        if chunk_start <= FILL_END:
            logger.info("    次チャンクまで %d秒待機...", SLEEP_SEC)
            time.sleep(SLEEP_SEC)

    logger.info("=== %s 完了: 合計 %d件 ===", pair_db, total_saved)
    return total_saved


def main():
    from app import create_app

    app = create_app()

    grand_total = 0
    for pair_db, pair_api in PAIRS:
        saved = backfill_pair(pair_db, pair_api, app)
        grand_total += saved
        if pair_db != PAIRS[-1][0]:
            logger.info("次ペアまで %d秒待機...", SLEEP_SEC)
            time.sleep(SLEEP_SEC)

    logger.info("全ペア完了: 合計 %d件 追加/更新", grand_total)


if __name__ == "__main__":
    main()
