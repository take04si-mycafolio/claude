#!/usr/bin/env python3
"""
Twelve Data API を使って複数タイムフレームのデータを遡及取得し DB に保存するスクリプト。

対象ペア : USDJPY → GBPJPY → EURJPY
対象足種 :
    5min  : 2026-01-01 〜 2026-03-31 22:55 UTC（既存 23:00〜 の直前まで）
    15min : 2025-10-01 〜 現在
    30min : 2025-10-01 〜 現在

使い方:
    python tasks/backfill_5min_twelvedata.py

レート制限: Free プラン 8 req/min → リクエスト間 12 秒 sleep
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta

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
SLEEP_SEC  = 12     # 8 req/min 制限対応

PAIRS = [
    ("USDJPY", "USD/JPY"),
    ("GBPJPY", "GBP/JPY"),
    ("EURJPY", "EUR/JPY"),
]

# タイムフレーム設定: (DB名, APIパラメータ, 足間隔分, 取得開始, 取得終了)
NOW = datetime.utcnow().replace(second=0, microsecond=0)

TIMEFRAMES = [
    {
        "db_tf":    "5min",
        "api_tf":   "5min",
        "interval_min": 5,
        "start":    datetime(2026, 1, 1, 0, 0, 0),
        "end":      datetime(2026, 3, 31, 22, 55, 0),  # 既存データ 23:00〜 の直前
    },
    {
        "db_tf":    "15min",
        "api_tf":   "15min",
        "interval_min": 15,
        "start":    datetime(2025, 10, 1, 0, 0, 0),
        "end":      NOW,
    },
    {
        "db_tf":    "30min",
        "api_tf":   "30min",
        "interval_min": 30,
        "start":    datetime(2025, 10, 1, 0, 0, 0),
        "end":      NOW,
    },
]


def fetch_chunk(symbol: str, api_tf: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Twelve Data API から 1 チャンクを取得して DataFrame で返す。"""
    params = {
        "symbol":     symbol,
        "interval":   api_tf,
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
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def backfill_pair_tf(pair_db: str, pair_api: str, tf: dict, app) -> int:
    """1ペア × 1タイムフレームをチャンク単位で取得・保存する。"""
    from app.services.data_fetcher import save_price_data

    db_tf        = tf["db_tf"]
    api_tf       = tf["api_tf"]
    interval_min = tf["interval_min"]
    fill_end     = tf["end"]

    chunk_minutes = OUTPUTSIZE * interval_min  # 1 チャンクあたりの時間幅（分）

    logger.info("  [%s %s] 取得開始: %s 〜 %s",
                pair_db, db_tf,
                tf["start"].strftime("%Y-%m-%d"),
                fill_end.strftime("%Y-%m-%d %H:%M"))

    total_saved = 0
    chunk_start = tf["start"]

    while chunk_start <= fill_end:
        chunk_end = min(
            chunk_start + timedelta(minutes=chunk_minutes - interval_min),
            fill_end,
        )

        logger.info("    取得: %s 〜 %s",
                    chunk_start.strftime("%Y-%m-%d %H:%M"),
                    chunk_end.strftime("%Y-%m-%d %H:%M"))

        df = fetch_chunk(pair_api, api_tf, chunk_start, chunk_end)

        if df.empty:
            chunk_start = chunk_end + timedelta(minutes=interval_min)
            time.sleep(SLEEP_SEC)
            continue

        df = df[df["timestamp"] <= pd.Timestamp(fill_end)].reset_index(drop=True)

        if not df.empty:
            with app.app_context():
                saved = save_price_data(pair_db, db_tf, df)
            total_saved += saved
            logger.info("      → %d件保存 (取得 %d行)", saved, len(df))

            last_ts = df["timestamp"].iloc[-1]
            chunk_start = last_ts.to_pydatetime() + timedelta(minutes=interval_min)
        else:
            chunk_start = chunk_end + timedelta(minutes=interval_min)

        if chunk_start <= fill_end:
            time.sleep(SLEEP_SEC)

    logger.info("  [%s %s] 完了: 合計 %d件", pair_db, db_tf, total_saved)
    return total_saved


def main():
    from app import create_app

    app = create_app()
    grand_total = 0

    for pair_db, pair_api in PAIRS:
        logger.info("=== %s 開始 ===", pair_db)
        for tf in TIMEFRAMES:
            saved = backfill_pair_tf(pair_db, pair_api, tf, app)
            grand_total += saved
            # ペア × TF 間も待機（最後のチャンクは sleep 済みなので最小限）
            time.sleep(SLEEP_SEC)

        logger.info("=== %s 全 TF 完了 ===", pair_db)

    logger.info("全ペア・全 TF 完了: 合計 %d件 追加/更新", grand_total)


if __name__ == "__main__":
    main()
