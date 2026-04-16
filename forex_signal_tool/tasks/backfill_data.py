#!/usr/bin/env python3
"""
データ欠損期間の補完スクリプト

通常の fetch_data.py は直近数時間しか取得しないため、
Cronが止まっていた期間のデータが欠損する。
このスクリプトは指定日数分を遡って取得・補完する。

使い方:
    python tasks/backfill_data.py              # デフォルト: 直近7日間
    python tasks/backfill_data.py --days 14    # 直近14日間
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timezone, timedelta

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PAIRS = ["USDJPY", "GBPJPY", "EURJPY"]

# 補完対象TFと取得ウィンドウ（時間単位）
# 5minは7日制限があるため7日×24hで上限
BACKFILL_HOURS = {
    "5min":  7 * 24,   # 168時間（yfinance上限）
    "15min": 7 * 24,   # 168時間
    "1hr":   7 * 24,   # 168時間
    "4hr":   7 * 24,   # 168時間（1hrで取得してリサンプリング）
}


def backfill(days: int):
    import yfinance as yf
    import pandas as pd
    from app import create_app
    from app.services.data_fetcher import save_price_data, resample_to_4hr

    YF_PAIR_MAP = {
        "USDJPY": "USDJPY=X",
        "GBPJPY": "GBPJPY=X",
        "EURJPY": "EURJPY=X",
    }
    YF_INTERVAL = {
        "5min":  "5m",
        "15min": "15m",
        "1hr":   "60m",
        "4hr":   "60m",   # 1hrで取得してリサンプリング
    }

    # 5minのyfinance上限は7日
    hours_back = min(days * 24, BACKFILL_HOURS.get("5min", 168))
    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=days * 24)

    logger.info("補完期間: %s 〜 %s UTC (%d日間)",
                start_dt.strftime("%Y-%m-%d %H:%M"),
                end_dt.strftime("%Y-%m-%d %H:%M"),
                days)

    app = create_app()
    total_saved = 0

    for pair in PAIRS:
        sym    = YF_PAIR_MAP[pair]
        ticker = yf.Ticker(sym)

        for tf in ["5min", "15min", "1hr", "4hr"]:
            interval = YF_INTERVAL[tf]
            # 5minは7日制限
            tf_hours = min(days * 24, 7 * 24) if tf == "5min" else days * 24
            tf_start = end_dt - timedelta(hours=tf_hours)

            logger.info("取得中: %s %s (%d時間)", pair, tf, tf_hours)
            try:
                df = ticker.history(
                    start=tf_start,
                    end=end_dt,
                    interval=interval,
                    auto_adjust=True,
                )
            except Exception as e:
                logger.error("  %s %s 取得エラー: %s", pair, tf, e)
                continue

            if df is None or df.empty:
                logger.warning("  %s %s: データなし", pair, tf)
                continue

            df = df.reset_index()

            # カラム統一
            col_map = {}
            for col in df.columns:
                cl = col.lower()
                if cl in ("datetime", "date", "timestamp"):
                    col_map[col] = "timestamp"
                elif cl == "open":   col_map[col] = "open"
                elif cl == "high":   col_map[col] = "high"
                elif cl == "low":    col_map[col] = "low"
                elif cl == "close":  col_map[col] = "close"
                elif cl == "volume": col_map[col] = "volume"
            df = df.rename(columns=col_map)

            needed = [c for c in ["timestamp", "open", "high", "low", "close", "volume"]
                      if c in df.columns]
            df = df[needed]
            if "volume" not in df.columns:
                df["volume"] = 0

            import pandas as _pd
            df["timestamp"] = _pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
            df = df.sort_values("timestamp").reset_index(drop=True)

            if tf == "4hr":
                df = resample_to_4hr(df)

            with app.app_context():
                saved = save_price_data(pair, tf, df)
            total_saved += saved
            logger.info("  %s %s: %d件補完 (取得 %d行)", pair, tf, saved, len(df))

    logger.info("補完完了: 合計 %d件追加/更新", total_saved)


def main():
    ap = argparse.ArgumentParser(description="欠損データ補完スクリプト")
    ap.add_argument("--days", type=int, default=7,
                    help="遡る日数 (デフォルト: 7日, 5minは最大7日)")
    args = ap.parse_args()

    backfill(args.days)


if __name__ == "__main__":
    main()
