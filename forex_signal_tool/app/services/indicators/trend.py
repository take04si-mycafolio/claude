"""
トレンド系テクニカル指標
  - SMA (20, 50, 200)
  - EMA (9, 21, 55)
  - Bollinger Bands (20, 2)
"""

import pandas as pd
import numpy as np


def calculate_trend(df: pd.DataFrame) -> dict:
    """
    DataFrameからトレンド系指標を計算し、シグナルとともに返す。
    """
    if df.empty or len(df) < 50:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    results = {}

    # --- SMA ---
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series([np.nan] * len(close))

    current_close = close.iloc[-1]
    sma20_val = sma20.iloc[-1]
    sma50_val = sma50.iloc[-1]
    sma200_val = sma200.iloc[-1] if not sma200.empty else np.nan

    prev_close = close.iloc[-2] if len(close) > 1 else current_close
    prev_sma20 = sma20.iloc[-2] if len(sma20) > 1 else sma20_val

    # SMA20とのクロスで判断
    if not pd.isna(sma20_val):
        if current_close > sma20_val and prev_close <= prev_sma20:
            sma20_signal = "BUY"
        elif current_close < sma20_val and prev_close >= prev_sma20:
            sma20_signal = "SELL"
        elif current_close > sma20_val:
            sma20_signal = "BUY"
        else:
            sma20_signal = "SELL"
    else:
        sma20_signal = "NEUTRAL"

    results["SMA_20"] = {
        "value": round(float(sma20_val), 3) if not pd.isna(sma20_val) else None,
        "signal": sma20_signal,
        "category": "trend",
        "details": {
            "current_close": round(float(current_close), 3),
            "sma20": round(float(sma20_val), 3) if not pd.isna(sma20_val) else None,
            "sma50": round(float(sma50_val), 3) if not pd.isna(sma50_val) else None,
            "sma200": round(float(sma200_val), 3) if not pd.isna(sma200_val) else None,
        },
    }

    # SMA50
    if not pd.isna(sma50_val):
        sma50_signal = "BUY" if current_close > sma50_val else "SELL"
    else:
        sma50_signal = "NEUTRAL"

    results["SMA_50"] = {
        "value": round(float(sma50_val), 3) if not pd.isna(sma50_val) else None,
        "signal": sma50_signal,
        "category": "trend",
        "details": {
            "current_close": round(float(current_close), 3),
            "sma50": round(float(sma50_val), 3) if not pd.isna(sma50_val) else None,
        },
    }

    # SMA Golden/Dead Cross (20 vs 50)
    if not pd.isna(sma20_val) and not pd.isna(sma50_val):
        prev_sma50 = sma50.iloc[-2] if len(sma50) > 1 else sma50_val
        if sma20_val > sma50_val and prev_sma20 <= prev_sma50:
            cross_signal = "BUY"   # ゴールデンクロス
        elif sma20_val < sma50_val and prev_sma20 >= prev_sma50:
            cross_signal = "SELL"  # デッドクロス
        elif sma20_val > sma50_val:
            cross_signal = "BUY"
        else:
            cross_signal = "SELL"
    else:
        cross_signal = "NEUTRAL"

    results["SMA_Cross_20_50"] = {
        "value": round(float(sma20_val - sma50_val), 4) if not pd.isna(sma20_val) and not pd.isna(sma50_val) else None,
        "signal": cross_signal,
        "category": "trend",
        "details": {
            "sma20": round(float(sma20_val), 3) if not pd.isna(sma20_val) else None,
            "sma50": round(float(sma50_val), 3) if not pd.isna(sma50_val) else None,
        },
    }

    # --- EMA ---
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema55 = close.ewm(span=55, adjust=False).mean()

    ema9_val = ema9.iloc[-1]
    ema21_val = ema21.iloc[-1]
    ema55_val = ema55.iloc[-1]

    prev_ema9 = ema9.iloc[-2] if len(ema9) > 1 else ema9_val
    prev_ema21 = ema21.iloc[-2] if len(ema21) > 1 else ema21_val

    # EMA9 vs EMA21 クロス
    if ema9_val > ema21_val and prev_ema9 <= prev_ema21:
        ema_cross_signal = "BUY"
    elif ema9_val < ema21_val and prev_ema9 >= prev_ema21:
        ema_cross_signal = "SELL"
    elif ema9_val > ema21_val:
        ema_cross_signal = "BUY"
    else:
        ema_cross_signal = "SELL"

    results["EMA_Cross_9_21"] = {
        "value": round(float(ema9_val - ema21_val), 4),
        "signal": ema_cross_signal,
        "category": "trend",
        "details": {
            "ema9": round(float(ema9_val), 3),
            "ema21": round(float(ema21_val), 3),
            "ema55": round(float(ema55_val), 3),
        },
    }

    results["EMA_21"] = {
        "value": round(float(ema21_val), 3),
        "signal": "BUY" if current_close > ema21_val else "SELL",
        "category": "trend",
        "details": {
            "current_close": round(float(current_close), 3),
            "ema21": round(float(ema21_val), 3),
        },
    }

    # --- Bollinger Bands ---
    bb_period = 20
    bb_std = 2.0
    bb_mid = close.rolling(bb_period).mean()
    bb_std_dev = close.rolling(bb_period).std()
    bb_upper = bb_mid + bb_std * bb_std_dev
    bb_lower = bb_mid - bb_std * bb_std_dev
    bb_width = (bb_upper - bb_lower) / bb_mid  # %帯幅

    mid_val = bb_mid.iloc[-1]
    upper_val = bb_upper.iloc[-1]
    lower_val = bb_lower.iloc[-1]
    width_val = bb_width.iloc[-1]

    if pd.isna(mid_val):
        bb_signal = "NEUTRAL"
    elif current_close <= lower_val:
        bb_signal = "BUY"    # 下バンドにタッチ → 買い
    elif current_close >= upper_val:
        bb_signal = "SELL"   # 上バンドにタッチ → 売り
    elif current_close > mid_val:
        bb_signal = "BUY"
    else:
        bb_signal = "SELL"

    results["BollingerBands_20_2"] = {
        "value": round(float(mid_val), 3) if not pd.isna(mid_val) else None,
        "signal": bb_signal,
        "category": "trend",
        "details": {
            "upper": round(float(upper_val), 3) if not pd.isna(upper_val) else None,
            "middle": round(float(mid_val), 3) if not pd.isna(mid_val) else None,
            "lower": round(float(lower_val), 3) if not pd.isna(lower_val) else None,
            "width_pct": round(float(width_val) * 100, 2) if not pd.isna(width_val) else None,
            "current_close": round(float(current_close), 3),
        },
    }

    # BBスクイーズ（バンド幅が狭い = ブレイクアウト前兆）
    bb_width_sma = bb_width.rolling(20).mean()
    if not pd.isna(width_val) and not pd.isna(bb_width_sma.iloc[-1]):
        is_squeeze = width_val < bb_width_sma.iloc[-1] * 0.8
    else:
        is_squeeze = False

    results["BB_Squeeze"] = {
        "value": round(float(width_val) * 100, 2) if not pd.isna(width_val) else None,
        "signal": "BUY" if is_squeeze and current_close > mid_val else (
                  "SELL" if is_squeeze and current_close < mid_val else "NEUTRAL"),
        "category": "trend",
        "details": {
            "is_squeeze": is_squeeze,
            "band_width_pct": round(float(width_val) * 100, 2) if not pd.isna(width_val) else None,
        },
    }

    return results


# ---------------------------------------------------------------------------
# Phase 1 — parameterizable series computers (condition_evaluator 用)
# ---------------------------------------------------------------------------

def compute_sma(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """SMA 系列。params: {"period"} (default 20)"""
    p = params or {}
    return df["close"].astype(float).rolling(p.get("period", 20)).mean()


def compute_ema(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """EMA 系列。params: {"period"} (default 21)"""
    p = params or {}
    return df["close"].astype(float).ewm(span=p.get("period", 21), adjust=False).mean()


def compute_bb_upper(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Bollinger 上バンド系列。params: {"period", "std"} (defaults 20, 2.0)"""
    p = params or {}
    period = p.get("period", 20)
    std_mult = p.get("std", 2.0)
    close = df["close"].astype(float)
    mid = close.rolling(period).mean()
    return mid + std_mult * close.rolling(period).std()


def compute_bb_lower(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Bollinger 下バンド系列。params: {"period", "std"} (defaults 20, 2.0)"""
    p = params or {}
    period = p.get("period", 20)
    std_mult = p.get("std", 2.0)
    close = df["close"].astype(float)
    mid = close.rolling(period).mean()
    return mid - std_mult * close.rolling(period).std()


def compute_bb_mid(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Bollinger 中央バンド（SMA）系列。params: {"period"} (default 20)"""
    p = params or {}
    return df["close"].astype(float).rolling(p.get("period", 20)).mean()


def compute_bb_width(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Bollinger バンド幅（(upper−lower)/mid）系列。params: {"period", "std"}"""
    p = params or {}
    period = p.get("period", 20)
    std_mult = p.get("std", 2.0)
    close = df["close"].astype(float)
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return (upper - lower) / mid
