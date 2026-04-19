#!/usr/bin/env python3
"""
QuantFlow スコアを5分足ごとに計算して quantflow_scores_5min テーブルに保存する。

5分足の close を price_5m / ma20_5m に使い、1時間足の MA75/MA200/RSI で
方向性・マクロ指標を判定する（既存スコアロジックと同一）。

cron（5分ごと）:
  */5 * * * * /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/update_quantflow_scores_5min.py \
    >> /home/xs539690/forex_project/logs/qf_scores_5min.log 2>&1
"""
import sys
import os
import math
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_BARS = 4032   # 2週間（14 × 24 × 12）
WARMUP_1H = 210    # 1hr MA200 ウォームアップ


def _to_naive(ts):
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts


def main():
    import pandas as pd
    from app import create_app, db
    from app.services.data_fetcher import get_candles
    from app.services.usdjpy_analysis import calculate_trend_score
    from app.services.score_backtest import _hybrid_us10y_rising_series, _macro_rising_series
    from app.services.quantflow_backtest import _load_macro_close
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        pair = "USDJPY"

        df_5m = get_candles(pair, "5min", limit=SAVE_BARS + 25)
        df_1h = get_candles(pair, "1hr",  limit=WARMUP_1H + 350)

        if df_5m.empty or df_1h.empty:
            logger.error("データ取得失敗: 5min=%d 1hr=%d", len(df_5m), len(df_1h))
            return

        # --- 1hr 指標計算 ---
        df_1h = df_1h.sort_values("timestamp").reset_index(drop=True)
        close_1h = df_1h["close"].astype(float)
        ma20_1h  = close_1h.rolling(20).mean()
        ma75_1h  = close_1h.rolling(75).mean()
        ma200_1h = close_1h.rolling(200).mean()

        delta = close_1h.diff()
        gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi_1h = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))

        # マクロ指標（US10Y / DXY）を 1hr に対して align
        us10y_close = _load_macro_close("US10Y", WARMUP_1H + 350)
        usbf_close  = _load_macro_close("USBF",  WARMUP_1H + 350)
        dxy_close   = _load_macro_close("DXY",   WARMUP_1H + 350)
        us10y_s = _hybrid_us10y_rising_series(us10y_close, usbf_close, df_1h["timestamp"])
        dxy_s   = _macro_rising_series(dxy_close, df_1h["timestamp"])

        df_1h_ind = pd.DataFrame({
            "ts":       pd.to_datetime([_to_naive(t) for t in df_1h["timestamp"]]),
            "ma20_1h":  ma20_1h.values,
            "ma75_1h":  ma75_1h.values,
            "ma200_1h": ma200_1h.values,
            "rsi_1h":   rsi_1h.values,
            "us10y_r":  us10y_s.values,
            "dxy_r":    dxy_s.values,
        }).sort_values("ts")

        # --- 5min 指標計算 ---
        df_5m = df_5m.sort_values("timestamp").reset_index(drop=True)
        close_5m = df_5m["close"].astype(float)
        ma20_5m  = close_5m.rolling(20).mean()

        df_5m_work = pd.DataFrame({
            "ts":      pd.to_datetime([_to_naive(t) for t in df_5m["timestamp"]]),
            "close":   close_5m.values,
            "ma20_5m": ma20_5m.values,
        }).sort_values("ts")

        # merge_asof: 5min 足それぞれに直前の 1hr 指標を割り当て
        merged = pd.merge_asof(
            df_5m_work,
            df_1h_ind,
            on="ts",
            direction="backward",
        )

        # 直近 SAVE_BARS 本（MA20(5min) ウォームアップ 20本後）
        start_idx = max(20, len(merged) - SAVE_BARS)
        rows = []

        for i in range(start_idx, len(merged)):
            r = merged.iloc[i]

            ma200 = r["ma200_1h"]
            if pd.isna(ma200):
                continue

            close_val   = float(r["close"])
            ma20_5m_val = r["ma20_5m"]
            ma20_1h_val = r["ma20_1h"]
            ma75_1h_val = r["ma75_1h"]
            rsi_val     = r["rsi_1h"]

            try:
                result = calculate_trend_score(
                    price_5m     = close_val,
                    ma20_5m      = float(ma20_5m_val) if not pd.isna(ma20_5m_val) else close_val,
                    price_1h     = close_val,
                    ma75_1h      = float(ma75_1h_val) if not pd.isna(ma75_1h_val) else close_val,
                    ma20_1h      = float(ma20_1h_val) if not pd.isna(ma20_1h_val) else close_val,
                    ma200_1h     = float(ma200),
                    rsi_14       = float(rsi_val) if not pd.isna(rsi_val) else 50.0,
                    us10y_rising = bool(r["us10y_r"]),
                    dxy_rising   = bool(r["dxy_r"]),
                )
            except Exception:
                continue

            bd = result.get("breakdown", {})
            ts_val = _to_naive(r["ts"].to_pydatetime() if hasattr(r["ts"], "to_pydatetime") else r["ts"])

            rows.append({
                "currency_pair":  pair,
                "timestamp":      ts_val,
                "score":          int(result["score"]),
                "trend_score":    int(bd["trend_score"])    if bd.get("trend_score")    is not None else None,
                "external_score": int(bd["external_score"]) if bd.get("external_score") is not None else None,
                "close_price":    round(close_val, 5),
            })

        if not rows:
            logger.warning("保存対象なし")
            return

        upsert_sql = text("""
            INSERT INTO quantflow_scores_5min
                (currency_pair, `timestamp`, score, trend_score, external_score, close_price)
            VALUES
                (:currency_pair, :timestamp, :score, :trend_score, :external_score, :close_price)
            ON DUPLICATE KEY UPDATE
                score          = VALUES(score),
                trend_score    = VALUES(trend_score),
                external_score = VALUES(external_score),
                close_price    = VALUES(close_price)
        """)
        db.session.execute(upsert_sql, rows)
        db.session.commit()
        logger.info("quantflow_scores_5min UPSERT 完了: %d 行", len(rows))


if __name__ == "__main__":
    main()
