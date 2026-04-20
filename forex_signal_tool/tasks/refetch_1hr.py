#!/usr/bin/env python3
"""
1時間足データを5日分再取得して DB に保存する（一回限り実行スクリプト）。

用途: yfinance が保存した不正データ（週末の平坦なOHLCなど）を
      正しいデータで上書きしたいとき。
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PAIRS = ["USDJPY", "GBPJPY", "EURJPY"]
YF_MAP = {"USDJPY": "USDJPY=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X"}

def main():
    import yfinance as yf
    import pandas as pd
    from app import create_app
    from app.services.data_fetcher import save_price_data

    app = create_app()
    with app.app_context():
        for pair in PAIRS:
            sym = YF_MAP[pair]
            logger.info("Fetching %s 1hr (period=5d) ...", pair)
            df = yf.Ticker(sym).history(period="5d", interval="60m", auto_adjust=True)
            if df.empty:
                logger.warning("  %s: データなし", pair)
                continue

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

            needed = [c for c in ["timestamp","open","high","low","close","volume"] if c in df.columns]
            df = df[needed]
            if "volume" not in df.columns:
                df["volume"] = 0

            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)

            # 週末（土・日）は除外
            df = df[df["timestamp"].dt.dayofweek < 5].copy()

            # O=H=L=C の行を前足 close で合成
            for i in range(1, len(df)):
                r = df.iloc[i]
                if r["open"] == r["close"] == r["high"] == r["low"]:
                    prev_c = df.iloc[i-1]["close"]
                    df.at[df.index[i], "open"]  = prev_c
                    df.at[df.index[i], "high"]  = max(prev_c, r["close"])
                    df.at[df.index[i], "low"]   = min(prev_c, r["close"])

            saved = save_price_data(pair, "1hr", df)
            logger.info("  %s 1hr: %d件保存", pair, saved)


if __name__ == "__main__":
    main()
