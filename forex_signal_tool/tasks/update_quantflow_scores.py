#!/usr/bin/env python3
"""
QuantFlow スコアを1時間足ごとに計算して quantflow_scores テーブルに保存する。

差分モード: DBの最終タイムスタンプ以降の新規バーのみ計算・挿入する。
初回のみフル計算（30日分）を実行する。

cron 例（1時間ごと）:
  0 * * * * /path/to/python3 /path/to/update_quantflow_scores.py
"""
import sys, os, math, logging
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FULL_HOURS = 720   # 初回フル計算（約30日）
WARMUP     = 200


def main():
    from app import create_app, db
    from app.services.data_fetcher import get_candles
    from app.services.quantflow_backtest import _compute_scores
    from app.services.usdjpy_analysis import calculate_trend_score
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        pair = "USDJPY"

        # --- 最終タイムスタンプ確認 ---
        last_ts_raw = db.session.execute(text(
            "SELECT MAX(`timestamp`) FROM quantflow_scores WHERE currency_pair='USDJPY'"
        )).scalar()

        def _to_naive(ts):
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            return ts

        last_ts = _to_naive(last_ts_raw) if last_ts_raw else None

        if last_ts is None:
            limit = WARMUP + FULL_HOURS + 20
            logger.info("初回フル計算: %d本取得", limit)
        else:
            hours_since = max(1, (datetime.utcnow() - last_ts).total_seconds() / 3600)
            new_bars = max(10, int(hours_since) + 5)
            limit = min(WARMUP + new_bars, WARMUP + FULL_HOURS + 20)
            logger.info("差分計算: last_ts=%s (%d時間前), %d本取得", last_ts, int(hours_since), limit)

        df = get_candles(pair, "1hr", limit=limit)
        if df.empty or len(df) < WARMUP + 10:
            logger.error("データ不足: %d 本", len(df))
            return

        df     = df.reset_index(drop=True)
        scores = _compute_scores(df, limit)

        # breakdown を個別に取得するため再計算（スコア本体は使わず内訳のみ）
        import pandas as pd
        close = df["close"].astype(float)
        ma20  = close.rolling(20).mean()
        ma75  = close.rolling(75).mean()
        ma200 = close.rolling(200).mean()
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi   = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))

        from app.services.score_backtest import _hybrid_us10y_rising_series, _macro_rising_series
        from app.services.quantflow_backtest import _load_macro_close

        ts          = df["timestamp"]
        us10y_close = _load_macro_close("US10Y", limit)
        usbf_close  = _load_macro_close("USBF",  limit)
        dxy_close   = _load_macro_close("DXY",   limit)
        us10y_s     = _hybrid_us10y_rising_series(us10y_close, usbf_close, ts)
        dxy_s       = _macro_rising_series(dxy_close, ts)

        start_idx = max(WARMUP, 0)
        rows = []

        for i in range(start_idx, len(df)):
            score = scores[i]
            if score is None:
                continue

            candle_ts = df["timestamp"].iloc[i]
            if hasattr(candle_ts, "to_pydatetime"):
                candle_ts = candle_ts.to_pydatetime()
            if hasattr(candle_ts, "tzinfo") and candle_ts.tzinfo is not None:
                candle_ts = candle_ts.replace(tzinfo=None)

            if last_ts is not None and candle_ts <= last_ts:
                continue

            trend_s    = None
            external_s = None
            try:
                result = calculate_trend_score(
                    price_5m  = float(close.iloc[i]),
                    ma20_5m   = float(ma20.iloc[i])  if not math.isnan(float(ma20.iloc[i]))  else float(close.iloc[i]),
                    price_1h  = float(close.iloc[i]),
                    ma75_1h   = float(ma75.iloc[i])  if not math.isnan(float(ma75.iloc[i]))  else float(close.iloc[i]),
                    ma20_1h   = float(ma20.iloc[i])  if not math.isnan(float(ma20.iloc[i]))  else float(close.iloc[i]),
                    ma200_1h  = float(ma200.iloc[i]) if not math.isnan(float(ma200.iloc[i])) else float(close.iloc[i]),
                    rsi_14    = float(rsi.iloc[i])   if not math.isnan(float(rsi.iloc[i]))   else 50.0,
                    us10y_rising = bool(us10y_s.iloc[i]),
                    dxy_rising   = bool(dxy_s.iloc[i]),
                )
                bd         = result.get("breakdown", {})
                trend_s    = bd.get("trend_score")
                external_s = bd.get("external_score")
            except Exception:
                pass

            rows.append({
                "currency_pair":  pair,
                "timestamp":      candle_ts,
                "score":          int(score),
                "trend_score":    int(trend_s)    if trend_s    is not None else None,
                "external_score": int(external_s) if external_s is not None else None,
                "close_price":    round(float(close.iloc[i]), 5),
            })

        if not rows:
            logger.info("新規データなし（last_ts=%s）", last_ts)
            return

        # UPSERT（INSERT ... ON DUPLICATE KEY UPDATE）
        upsert_sql = text("""
            INSERT INTO quantflow_scores
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
        logger.info("quantflow_scores 完了: %d 行追加", len(rows))


if __name__ == "__main__":
    main()
