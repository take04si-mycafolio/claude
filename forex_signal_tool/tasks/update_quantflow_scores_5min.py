#!/usr/bin/env python3
"""
QuantFlow スコアを5分足ごとに計算して quantflow_scores_5min テーブルに保存する。

差分モード: DBの最終タイムスタンプ以降の新規バーのみ計算・挿入する。
初回のみフル計算（2週間分）を実行する。

cron（5分ごと）:
  */5 * * * * /path/to/python3 /path/to/tasks/update_quantflow_scores_5min.py \
    >> /tmp/qf_scores_5min.log 2>&1
"""
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FULL_BARS = 4032   # 初回フル計算（2週間: 14×24×12）
WARMUP_5M = 25     # MA20(5min) ウォームアップ
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

        # --- 最終タイムスタンプ確認 ---
        last_ts_raw = db.session.execute(text(
            "SELECT MAX(`timestamp`) FROM quantflow_scores_5min WHERE currency_pair='USDJPY'"
        )).scalar()
        last_ts = _to_naive(last_ts_raw) if last_ts_raw else None

        if last_ts is None:
            limit_5m = FULL_BARS + WARMUP_5M
            logger.info("初回フル計算: %d本取得", limit_5m)
        else:
            minutes_since = max(5, (datetime.utcnow() - last_ts).total_seconds() / 60)
            new_bars = int(minutes_since / 5) + 10
            limit_5m = min(WARMUP_5M + new_bars, FULL_BARS + WARMUP_5M)
            logger.info("差分計算: last_ts=%s (%d分前), %d本取得", last_ts, int(minutes_since), limit_5m)

        df_5m = get_candles(pair, "5min", limit=limit_5m)
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

        merged = pd.merge_asof(df_5m_work, df_1h_ind, on="ts", direction="backward")

        # --- スコア計算（差分のみ） ---
        rows = []
        for i in range(20, len(merged)):
            r = merged.iloc[i]

            ma200 = r["ma200_1h"]
            if pd.isna(ma200):
                continue

            ts_val = _to_naive(r["ts"].to_pydatetime() if hasattr(r["ts"], "to_pydatetime") else r["ts"])

            if last_ts is not None and ts_val <= last_ts:
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
            rows.append({
                "currency_pair":  pair,
                "timestamp":      ts_val,
                "score":          int(result["score"]),
                "trend_score":    int(bd["trend_score"])    if bd.get("trend_score")    is not None else None,
                "external_score": int(bd["external_score"]) if bd.get("external_score") is not None else None,
                "close_price":    round(close_val, 5),
            })

        if not rows:
            logger.info("新規データなし（last_ts=%s）", last_ts)
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
        logger.info("quantflow_scores_5min 完了: %d 行追加", len(rows))


if __name__ == "__main__":
    main()
