"""
ボラティリティ系テクニカル指標
  - ATR (14)
  - ボラティリティインデックス（BBバンド幅）
"""

import pandas as pd
import numpy as np


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    high_low = high - low
    high_prev_close = (high - close.shift(1)).abs()
    low_prev_close = (low - close.shift(1)).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def calculate_volatility(df: pd.DataFrame) -> dict:
    """
    DataFrameからボラティリティ系指標を計算し、シグナルとともに返す。
    """
    if df.empty or len(df) < 20:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    current_price = float(close.iloc[-1])
    results = {}

    # --- ATR ---
    atr = _atr(high, low, close)
    atr_val = atr.iloc[-1]
    atr_sma = atr.rolling(20).mean()
    atr_sma_val = atr_sma.iloc[-1]

    # ATRが平均より高い = 高ボラティリティ
    is_high_vol = not pd.isna(atr_sma_val) and atr_val > atr_sma_val * 1.2

    # ATRベースのSL/TP価格（参考値）
    atr_pips = round(float(atr_val) / 0.01, 1) if not pd.isna(atr_val) else None  # JPYペア用

    # ATRシグナル: 高ボラティリティ時はトレンドに追従
    close_vs_mid = (close.iloc[-1] - close.rolling(10).mean().iloc[-1])
    if is_high_vol:
        atr_signal = "BUY" if close_vs_mid > 0 else "SELL"
    else:
        atr_signal = "NEUTRAL"

    results["ATR_14"] = {
        "value": round(float(atr_val), 4) if not pd.isna(atr_val) else None,
        "signal": atr_signal,
        "category": "volatility",
        "details": {
            "atr": round(float(atr_val), 4) if not pd.isna(atr_val) else None,
            "atr_pips": atr_pips,
            "atr_sma20": round(float(atr_sma_val), 4) if not pd.isna(atr_sma_val) else None,
            "is_high_volatility": is_high_vol,
            "suggested_sl_pips": round(atr_pips * 1.5, 1) if atr_pips else None,
            "suggested_tp_pips": round(atr_pips * 3.0, 1) if atr_pips else None,
        },
    }

    # --- ボラティリティインデックス (Bollinger Band Width) ---
    bb_period = 20
    bb_mid = close.rolling(bb_period).mean()
    bb_std_dev = close.rolling(bb_period).std()
    bb_upper = bb_mid + 2 * bb_std_dev
    bb_lower = bb_mid - 2 * bb_std_dev
    bb_width = (bb_upper - bb_lower) / bb_mid

    width_val = bb_width.iloc[-1]
    width_sma = bb_width.rolling(20).mean().iloc[-1]

    if pd.isna(width_val):
        vi_signal = "NEUTRAL"
    elif not pd.isna(width_sma) and width_val < width_sma * 0.7:
        # スクイーズ状態 → ブレイクアウト前兆
        vi_signal = "BUY" if current_price > float(bb_mid.iloc[-1]) else "SELL"
    else:
        vi_signal = "NEUTRAL"

    results["Volatility_Index"] = {
        "value": round(float(width_val) * 100, 2) if not pd.isna(width_val) else None,
        "signal": vi_signal,
        "category": "volatility",
        "details": {
            "band_width_pct": round(float(width_val) * 100, 2) if not pd.isna(width_val) else None,
            "band_width_sma_pct": round(float(width_sma) * 100, 2) if not pd.isna(width_sma) else None,
            "is_squeeze": not pd.isna(width_sma) and width_val < width_sma * 0.7,
        },
    }

    return results


# ---------------------------------------------------------------------------
# Phase 1 — parameterizable series computer (condition_evaluator / riskManager 用)
# ---------------------------------------------------------------------------

def compute_atr(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """ATR 系列。params: {"period"} (default 14)"""
    p = params or {}
    return _atr(df["high"].astype(float), df["low"].astype(float),
                df["close"].astype(float), p.get("period", 14))
