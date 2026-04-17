#!/usr/bin/env python3
"""
yfinance を使って US10Y（米10年債利回り）と DXY（ドルインデックス）の
1時間足データを遡及取得し DB に保存するスクリプト。

取得期間: 2025-10-01 〜 現在

使い方:
    python tasks/backfill_macro_yfinance.py

yfinance の 60m 足は過去 730 日まで取得可能。
"""

import sys
import os
import time
import logging
from datetime import datetime, timezone, timedelta

import yfinance as yf
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

# US10Y=^TNX, DXY=DX-Y.NYB
MACRO_TARGETS = [
    ("US10Y", "^TNX"),
    ("DXY",   "DX-Y.NYB"),
]

FILL_START = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
FILL_END   = datetime.now(timezone.utc)

# yfinance 60m 足は一度のリクエストで約 60 日まで安定取得できる
CHUNK_DAYS = 58


def fetch_yf_chunk(ticker_symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """yfinance から 1hr（60m）足を 1 チャンク取得して DataFrame で返す。"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(
            start=start_dt,
            end=end_dt,
            interval="60m",
            auto_adjust=True,
        )
    except Exception as e:
        logger.error("  yfinance エラー: %s", e)
        return pd.DataFrame()

    if df is None or df.empty:
        logger.warning("  データなし (start=%s)", start_dt.strftime("%Y-%m-%d"))
        return pd.DataFrame()

    df = df.reset_index()

    # カラム名を統一
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ("datetime", "date", "timestamp"):
            col_map[col] = "timestamp"
        elif cl == "open":
            col_map[col] = "open"
        elif cl == "high":
            col_map[col] = "high"
        elif cl == "low":
            col_map[col] = "low"
        elif cl == "close":
            col_map[col] = "close"
        elif cl == "volume":
            col_map[col] = "volume"
    df = df.rename(columns=col_map)

    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        logger.error("  必須カラム不足: %s", df.columns.tolist())
        return pd.DataFrame()

    if "volume" not in df.columns:
        df["volume"] = 0.0

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def backfill_macro(pair_db: str, ticker_symbol: str, app) -> int:
    """1 マクロ指標分を chunk 単位で取得・保存する。"""
    from app.services.data_fetcher import save_price_data

    logger.info("=== %s (%s) 開始: %s 〜 %s ===",
                pair_db, ticker_symbol,
                FILL_START.strftime("%Y-%m-%d"),
                FILL_END.strftime("%Y-%m-%d %H:%M"))

    total_saved = 0
    chunk_start = FILL_START

    while chunk_start < FILL_END:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), FILL_END)

        logger.info("  取得: %s 〜 %s",
                    chunk_start.strftime("%Y-%m-%d %H:%M"),
                    chunk_end.strftime("%Y-%m-%d %H:%M"))

        df = fetch_yf_chunk(ticker_symbol, chunk_start, chunk_end)

        if df.empty:
            chunk_start = chunk_end
            time.sleep(3)
            continue

        with app.app_context():
            saved = save_price_data(pair_db, "1hr", df)
        total_saved += saved
        logger.info("    → %d件保存 (取得 %d行)", saved, len(df))

        last_ts = df["timestamp"].iloc[-1]
        chunk_start = last_ts.to_pydatetime().replace(tzinfo=timezone.utc) + timedelta(hours=1)
        time.sleep(3)

    logger.info("=== %s 完了: 合計 %d件 ===", pair_db, total_saved)
    return total_saved


def main():
    from app import create_app

    app = create_app()
    grand_total = 0

    for pair_db, ticker_symbol in MACRO_TARGETS:
        saved = backfill_macro(pair_db, ticker_symbol, app)
        grand_total += saved
        time.sleep(5)

    logger.info("全マクロ指標完了: 合計 %d件 追加/更新", grand_total)


if __name__ == "__main__":
    main()
