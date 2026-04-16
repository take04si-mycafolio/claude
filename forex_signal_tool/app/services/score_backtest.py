"""
トレンドスコア帯別バックテスト集計

過去の 1hr 足データに対してスコアを遡及計算し、
N 時間後の損益をスコア帯別に集計する。
"""

import math
import pandas as pd

SCORE_BANDS = [
    {"label": "Strong Buy", "level": "strong-buy", "min": 90,   "max": 999},
    {"label": "Buy",        "level": "buy",         "min": 70,   "max": 89},
    {"label": "Neutral",    "level": "neutral",     "min": 40,   "max": 69},
    {"label": "Warning",    "level": "warning",     "min": -999, "max": 39},
]


def _macro_rising_series(macro_close: pd.Series, usdjpy_ts: pd.Series) -> pd.Series:
    """
    マクロ指標（US10Y/DXY）の各タイムスタンプにおける MA5 上抜けフラグを
    USDJPY の timestamp 系列に merge_asof で対応付けて返す。
    欠損は False。
    """
    if macro_close.empty:
        return pd.Series(False, index=usdjpy_ts.index)

    ma5 = macro_close.rolling(5).mean()
    rising = (macro_close > ma5).astype(bool)

    # merge_asof 用に DataFrame に変換（列名を揃える）
    left = pd.DataFrame({"ts": usdjpy_ts.values}, index=usdjpy_ts.index)
    right = pd.DataFrame({
        "ts":     macro_close.index,
        "rising": rising.values,
    }).sort_values("ts")

    merged = pd.merge_asof(
        left.sort_values("ts"),
        right,
        on="ts",
        direction="backward",
    )
    # 元の index 順に戻す
    merged.index = left.sort_values("ts").index
    result = merged["rising"].reindex(usdjpy_ts.index).fillna(False)
    return result


def compute_score_band_stats(
    pair: str = "USDJPY",
    limit: int = 700,
    forward_hours: int = 24,
) -> dict:
    """
    過去 limit 本の 1hr 足でスコアを遡及計算し、
    forward_hours 時間後の損益をスコア帯別に集計して返す。

    Returns
    -------
    dict with keys:
        bands           : スコア帯ごとの集計リスト
        total_analyzed  : 分析対象件数
        forward_hours   : 前向き時間
        period_start/end: 分析期間
    """
    from app.services.data_fetcher import get_candles
    from app.services.usdjpy_analysis import calculate_trend_score

    # ---- USDJPY 1hr ローソク足 ----
    df = get_candles(pair, "1hr", limit=limit)
    if len(df) < 210:
        return {"error": "データ不足（200本以上必要）"}

    df = df.reset_index(drop=True)
    close = df["close"].astype(float)
    ts    = df["timestamp"]  # UTC naive

    # ---- MA 系列（ベクトル計算）----
    ma20  = close.rolling(20).mean()
    ma75  = close.rolling(75).mean()
    ma200 = close.rolling(200).mean()

    # ---- RSI(14) Wilder EWM ----
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))

    # ---- マクロ指標（US10Y / DXY）----
    def _load_macro_close(macro_pair: str) -> pd.Series:
        dm = get_candles(macro_pair, "1hr", limit=limit)
        if dm.empty:
            return pd.Series(dtype=float)
        return dm.set_index("timestamp")["close"].astype(float).sort_index()

    us10y_close = _load_macro_close("US10Y")
    dxy_close   = _load_macro_close("DXY")

    us10y_rising_s = _macro_rising_series(us10y_close, ts)
    dxy_rising_s   = _macro_rising_series(dxy_close,   ts)

    # ---- 遡及スコア計算 ----
    warmup   = 200
    max_idx  = len(df) - forward_hours - 1

    scores_list = []
    pips_list   = []

    for i in range(warmup, max_idx + 1):
        ma20_v  = float(ma20.iloc[i])
        ma75_v  = float(ma75.iloc[i])
        ma200_v = float(ma200.iloc[i])
        rsi_v   = float(rsi.iloc[i])
        price_v = float(close.iloc[i])

        if any(math.isnan(v) for v in [ma20_v, ma75_v, ma200_v, rsi_v]):
            continue

        result = calculate_trend_score(
            price_5m=price_v,  ma20_5m=ma20_v,   # 5m は 1h MA20 で近似
            price_1h=price_v,
            ma75_1h=ma75_v,    ma20_1h=ma20_v,    ma200_1h=ma200_v,
            rsi_14=rsi_v,
            us10y_rising=bool(us10y_rising_s.iloc[i]),
            dxy_rising=bool(dxy_rising_s.iloc[i]),
        )

        forward_price = float(close.iloc[i + forward_hours])
        pips = round((forward_price - price_v) / 0.01, 1)  # JPY ペア: 1pip = 0.01

        scores_list.append(result["score"])
        pips_list.append(pips)

    if not scores_list:
        return {"error": "集計データなし"}

    df_r = pd.DataFrame({"score": scores_list, "pips": pips_list})

    # ---- スコア帯別集計 ----
    bands_out = []
    for band in SCORE_BANDS:
        mask = (df_r["score"] >= band["min"]) & (df_r["score"] <= band["max"])
        sub  = df_r[mask]
        n    = int(len(sub))

        if n == 0:
            bands_out.append({
                **band,
                "count": 0,
                "win_rate": None,
                "avg_pips": None,
                "max_loss_pips": None,
            })
            continue

        wins     = int((sub["pips"] > 0).sum())
        avg_pips = round(float(sub["pips"].mean()), 1)
        max_loss = round(float(sub["pips"].min()), 1)

        bands_out.append({
            **band,
            "count":         n,
            "win_rate":      round(wins / n * 100, 1),
            "avg_pips":      avg_pips,
            "max_loss_pips": max_loss,
        })

    period_start = ts.iloc[warmup].strftime("%Y/%m/%d")
    period_end   = ts.iloc[max_idx].strftime("%Y/%m/%d")

    return {
        "bands":          bands_out,
        "total_analyzed": len(df_r),
        "forward_hours":  forward_hours,
        "period_start":   period_start,
        "period_end":     period_end,
    }
