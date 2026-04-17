"""
QuantFlow 月次バックテスト

1hr 足の QuantFlow スコアをもとにシグナルを生成し、
SL/TP ヒットまでのトレード結果を quantflow_trades テーブルに保存する。

エントリー条件 : |スコア| >= SCORE_THRESHOLD（デフォルト 30）
エントリー価格 : シグナル発生の次足 open
エグジット     : TP または SL ヒット（同足で両方ヒット → SL 優先）
最大保有時間  : MAX_HOLD_BARS 本（デフォルト 48h）を超えたら close で決済
"""

import logging
import math
import pandas as pd

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 30
MAX_HOLD_BARS   = 48
PIP_VALUE       = 0.01   # JPY ペア: 1 pip = 0.01
WARMUP          = 200    # MA200 の計算に必要


def _load_macro_close(pair: str, limit: int) -> pd.Series:
    from app.services.data_fetcher import get_candles
    dm = get_candles(pair, "1hr", limit=limit)
    if dm.empty:
        return pd.Series(dtype=float)
    return dm.set_index("timestamp")["close"].astype(float).sort_index()


def _compute_scores(df: pd.DataFrame, limit: int) -> list:
    """全 1hr 足に対して QuantFlow スコアを遡及計算して返す。"""
    from app.services.score_backtest import (
        _hybrid_us10y_rising_series, _macro_rising_series,
    )
    from app.services.usdjpy_analysis import calculate_trend_score

    close = df["close"].astype(float)
    ma20  = close.rolling(20).mean()
    ma75  = close.rolling(75).mean()
    ma200 = close.rolling(200).mean()

    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))

    ts          = df["timestamp"]
    us10y_close = _load_macro_close("US10Y", limit)
    usbf_close  = _load_macro_close("USBF",  limit)
    dxy_close   = _load_macro_close("DXY",   limit)

    us10y_s = _hybrid_us10y_rising_series(us10y_close, usbf_close, ts)
    dxy_s   = _macro_rising_series(dxy_close, ts)

    scores = []
    for i in range(len(df)):
        if i < WARMUP or math.isnan(float(ma200.iloc[i])):
            scores.append(None)
            continue
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
            scores.append(result.get("score"))
        except Exception:
            scores.append(None)

    return scores


def run_quantflow_backtest(
    pair:       str   = "USDJPY",
    sl_pips:    float = 20.0,
    tp_pips:    float = 40.0,
    limit:      int   = 5000,
    start_date: str   = "2026-01-01",
) -> dict:
    """
    QuantFlow 月次バックテストを実行して DB に保存する。
    既存データは全件削除してから再計算する。

    start_date: この日付以降のエントリーのみ記録（マクロデータが揃う期間に限定）
    """
    from app import db
    from app.models.quantflow_trade import QuantFlowTrade
    from app.services.data_fetcher import get_candles
    from datetime import datetime

    logger.info("QuantFlow BT 開始: %s  SL=%.1f TP=%.1f  開始日=%s",
                pair, sl_pips, tp_pips, start_date)

    df = get_candles(pair, "1hr", limit=limit)
    if df.empty or len(df) < WARMUP + 10:
        return {"error": f"データ不足 ({len(df)} 本)"}

    df = df.reset_index(drop=True)

    # start_date 以降のみエントリーを記録（スコア計算自体は全期間で行いWARMUP確保）
    try:
        entry_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        entry_start_dt = None

    scores = _compute_scores(df, limit)

    # ---------- 既存データ削除 ----------
    QuantFlowTrade.query.filter_by(currency_pair=pair).delete()
    db.session.commit()

    # ---------- トレード生成 ----------
    trades_to_add = []
    i = WARMUP

    while i < len(df) - 1:
        score = scores[i]
        if score is None or abs(score) < SCORE_THRESHOLD:
            i += 1
            continue

        direction = "BUY" if score > 0 else "SELL"

        entry_idx   = i + 1
        if entry_idx >= len(df):
            break

        entry_price = float(df["open"].iloc[entry_idx])
        entry_ts    = df["timestamp"].iloc[entry_idx]
        if hasattr(entry_ts, "to_pydatetime"):
            entry_ts = entry_ts.to_pydatetime()

        # start_date 以前のエントリーはスキップ（スコア計算は継続）
        if entry_start_dt and entry_ts.replace(tzinfo=None) < entry_start_dt:
            i += 1
            continue

        tp_dist = tp_pips * PIP_VALUE
        sl_dist = sl_pips * PIP_VALUE

        if direction == "BUY":
            tp_price = entry_price + tp_dist
            sl_price = entry_price - sl_dist
        else:
            tp_price = entry_price - tp_dist
            sl_price = entry_price + sl_dist

        outcome     = None
        exit_price  = None
        exit_idx    = None
        profit_pips = None

        for j in range(entry_idx + 1, min(entry_idx + MAX_HOLD_BARS + 1, len(df))):
            high = float(df["high"].iloc[j])
            low  = float(df["low"].iloc[j])

            if direction == "BUY":
                hit_tp = high >= tp_price
                hit_sl = low  <= sl_price
            else:
                hit_tp = low  <= tp_price
                hit_sl = high >= sl_price

            if hit_tp and hit_sl:
                outcome = "LOSS"; exit_price = sl_price; exit_idx = j
                profit_pips = -sl_pips
                break
            elif hit_tp:
                outcome = "WIN";  exit_price = tp_price; exit_idx = j
                profit_pips = tp_pips
                break
            elif hit_sl:
                outcome = "LOSS"; exit_price = sl_price; exit_idx = j
                profit_pips = -sl_pips
                break

        if outcome is None:
            exit_idx   = min(entry_idx + MAX_HOLD_BARS, len(df) - 1)
            exit_price = float(df["close"].iloc[exit_idx])
            if direction == "BUY":
                profit_pips = round((exit_price - entry_price) / PIP_VALUE, 2)
            else:
                profit_pips = round((entry_price - exit_price) / PIP_VALUE, 2)
            outcome = "WIN" if profit_pips > 0 else "LOSS"

        exit_ts = df["timestamp"].iloc[exit_idx]
        if hasattr(exit_ts, "to_pydatetime"):
            exit_ts = exit_ts.to_pydatetime()

        year_month = entry_ts.strftime("%Y-%m")

        trades_to_add.append(QuantFlowTrade(
            currency_pair  = pair,
            year_month     = year_month,
            entry_ts       = entry_ts,
            exit_ts        = exit_ts,
            direction      = direction,
            score_at_entry = int(score),
            entry_price    = entry_price,
            exit_price     = exit_price,
            outcome        = outcome,
            profit_pips    = profit_pips,
            sl_pips        = sl_pips,
            tp_pips        = tp_pips,
        ))

        i = exit_idx + 1

    if trades_to_add:
        db.session.bulk_save_objects(trades_to_add)
        db.session.commit()

    logger.info("QuantFlow BT 完了: %d トレード", len(trades_to_add))
    return {"total_trades": len(trades_to_add), "pair": pair}


def get_quantflow_monthly_summary(pair: str = "USDJPY") -> list:
    """
    quantflow_trades から月別集計を返す。
    新しい月順にソートして返す。
    """
    from app import db
    from sqlalchemy import text

    sql = text("""
        SELECT
            `year_month`,
            COUNT(*)                                         AS total,
            SUM(outcome = 'WIN')                             AS wins,
            SUM(outcome = 'LOSS')                            AS losses,
            ROUND(SUM(outcome = 'WIN') / COUNT(*) * 100, 1) AS win_rate,
            ROUND(SUM(profit_pips), 2)                       AS total_pips,
            ROUND(AVG(profit_pips), 2)                       AS avg_pips
        FROM quantflow_trades
        WHERE currency_pair = :pair
        GROUP BY `year_month`
        ORDER BY `year_month` DESC
    """)
    rows = db.session.execute(sql, {"pair": pair}).fetchall()

    result = []
    for r in rows:
        ym = r[0]
        y, m = ym.split("-")
        result.append({
            "year_month": ym,
            "label":      f"{y}年{int(m):d}月",
            "total":      int(r[1]),
            "wins":       int(r[2] or 0),
            "losses":     int(r[3] or 0),
            "win_rate":   float(r[4] or 0),
            "total_pips": float(r[5] or 0),
            "avg_pips":   float(r[6] or 0),
        })
    return result
