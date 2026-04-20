#!/usr/bin/env python3
"""
指定タイムフレームのデータを period='5d' で再取得して DB に上書き保存する。

使い方:
  python tasks/refetch_1hr.py              # 1hr のみ（デフォルト）
  python tasks/refetch_1hr.py 15min        # 15min のみ
  python tasks/refetch_1hr.py 1hr 15min    # 複数指定
  python tasks/refetch_1hr.py all          # 5min/15min/30min/1hr/4hr すべて
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PAIRS  = ["USDJPY", "GBPJPY", "EURJPY"]
YF_MAP = {"USDJPY": "USDJPY=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X"}
YF_IV  = {"5min": "5m", "15min": "15m", "30min": "30m", "1hr": "60m", "4hr": "60m"}
ALL_TF = ["5min", "15min", "30min", "1hr", "4hr"]


def refetch(pair: str, timeframe: str):
    import yfinance as yf
    import pandas as pd
    from app.services.data_fetcher import save_price_data

    sym      = YF_MAP[pair]
    interval = YF_IV[timeframe]

    logger.info("Fetching %s %s (period=5d, interval=%s) ...", pair, timeframe, interval)
    df = yf.Ticker(sym).history(period="5d", interval=interval, auto_adjust=True)
    if df.empty:
        logger.warning("  %s %s: データなし", pair, timeframe)
        return

    df = df.reset_index()
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ("datetime", "date", "timestamp"): col_map[col] = "timestamp"
        elif cl == "open":   col_map[col] = "open"
        elif cl == "high":   col_map[col] = "high"
        elif cl == "low":    col_map[col] = "low"
        elif cl == "close":  col_map[col] = "close"
        elif cl == "volume": col_map[col] = "volume"
    df = df.rename(columns=col_map)

    needed = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[needed].copy()
    if "volume" not in df.columns:
        df["volume"] = 0

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)

    # 4hr は 1hr データをリサンプリング
    if timeframe == "4hr":
        df = df.set_index("timestamp").resample("4h").agg(
            open=("open","first"), high=("high","max"),
            low=("low","min"),     close=("close","last"),
            volume=("volume","sum")
        ).dropna(subset=["open"]).reset_index()

    # save_price_data 内で週末除外される（weekday >= 5 をスキップ）
    saved = save_price_data(pair, timeframe, df)
    logger.info("  %s %s: %d件保存", pair, timeframe, saved)


def main():
    from app import create_app

    args = sys.argv[1:]
    if not args:
        target_tfs = ["1hr"]
    elif args == ["all"]:
        target_tfs = ALL_TF
    else:
        target_tfs = [a for a in args if a in ALL_TF]
        unknown = [a for a in args if a not in ALL_TF and a != "all"]
        if unknown:
            logger.warning("不明なタイムフレーム: %s（有効: %s）", unknown, ALL_TF)

    if not target_tfs:
        logger.error("タイムフレームが指定されていません")
        sys.exit(1)

    logger.info("対象: %s", target_tfs)
    app = create_app()
    with app.app_context():
        for tf in target_tfs:
            for pair in PAIRS:
                refetch(pair, tf)


if __name__ == "__main__":
    main()
