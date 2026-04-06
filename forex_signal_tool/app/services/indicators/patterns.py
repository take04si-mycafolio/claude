"""
ローソク足パターン系テクニカル指標
  - ハンマー / 逆ハンマー
  - 包み足 (Engulfing)
  - 十字線 (Doji)
  - 三兵 (Three Soldiers / Three Crows)
  - ピンバー
"""

import pandas as pd
import numpy as np


def _body_size(open_: float, close: float) -> float:
    return abs(close - open_)


def _upper_shadow(open_: float, close: float, high: float) -> float:
    return high - max(open_, close)


def _lower_shadow(open_: float, close: float, low: float) -> float:
    return min(open_, close) - low


def _candle_range(high: float, low: float) -> float:
    return high - low


def detect_hammer(open_: float, high: float, low: float, close: float) -> bool:
    """ハンマー: 下ヒゲが実体の2倍以上、上ヒゲが短い"""
    body = _body_size(open_, close)
    lower = _lower_shadow(open_, close, low)
    upper = _upper_shadow(open_, close, high)
    if body == 0:
        return False
    return lower >= body * 2 and upper <= body * 0.3


def detect_inverted_hammer(open_: float, high: float, low: float, close: float) -> bool:
    """逆ハンマー: 上ヒゲが実体の2倍以上、下ヒゲが短い"""
    body = _body_size(open_, close)
    lower = _lower_shadow(open_, close, low)
    upper = _upper_shadow(open_, close, high)
    if body == 0:
        return False
    return upper >= body * 2 and lower <= body * 0.3


def detect_doji(open_: float, high: float, low: float, close: float) -> bool:
    """十字線: 実体がレンジの10%以下"""
    body = _body_size(open_, close)
    rng = _candle_range(high, low)
    if rng == 0:
        return False
    return body / rng < 0.1


def detect_bullish_engulfing(prev_open: float, prev_close: float,
                              curr_open: float, curr_close: float) -> bool:
    """強気の包み足: 前のキャンドルを現在の陽線が完全に包む"""
    prev_bearish = prev_close < prev_open
    curr_bullish = curr_close > curr_open
    return (prev_bearish and curr_bullish
            and curr_open < prev_close
            and curr_close > prev_open)


def detect_bearish_engulfing(prev_open: float, prev_close: float,
                              curr_open: float, curr_close: float) -> bool:
    """弱気の包み足: 前のキャンドルを現在の陰線が完全に包む"""
    prev_bullish = prev_close > prev_open
    curr_bearish = curr_close < curr_open
    return (prev_bullish and curr_bearish
            and curr_open > prev_close
            and curr_close < prev_open)


def detect_three_white_soldiers(df_slice: pd.DataFrame) -> bool:
    """三白兵: 3本連続の強い陽線"""
    if len(df_slice) < 3:
        return False
    for i in range(3):
        row = df_slice.iloc[-(3 - i)]
        if row["close"] <= row["open"]:
            return False
        body = _body_size(row["open"], row["close"])
        rng = _candle_range(row["high"], row["low"])
        if rng == 0 or body / rng < 0.6:
            return False
    # 各陽線が前の陽線より高い終値
    closes = [df_slice.iloc[-(3 - i)]["close"] for i in range(3)]
    return closes[0] < closes[1] < closes[2]


def detect_three_black_crows(df_slice: pd.DataFrame) -> bool:
    """三羽烏: 3本連続の強い陰線"""
    if len(df_slice) < 3:
        return False
    for i in range(3):
        row = df_slice.iloc[-(3 - i)]
        if row["close"] >= row["open"]:
            return False
        body = _body_size(row["open"], row["close"])
        rng = _candle_range(row["high"], row["low"])
        if rng == 0 or body / rng < 0.6:
            return False
    closes = [df_slice.iloc[-(3 - i)]["close"] for i in range(3)]
    return closes[0] > closes[1] > closes[2]


def calculate_patterns(df: pd.DataFrame) -> dict:
    """
    DataFrameからローソク足パターンを検出し、シグナルとともに返す。
    """
    if df.empty or len(df) < 5:
        return {}

    results = {}

    current = df.iloc[-1]
    prev = df.iloc[-2]

    o = float(current["open"])
    h = float(current["high"])
    l = float(current["low"])
    c = float(current["close"])

    po = float(prev["open"])
    ph = float(prev["high"])
    pl = float(prev["low"])
    pc = float(prev["close"])

    # 直近トレンド判定（過去10本）
    if len(df) >= 10:
        recent_close = df["close"].astype(float).iloc[-10:]
        trend_up = recent_close.iloc[-1] > recent_close.iloc[0]
    else:
        trend_up = c > o

    # --- ハンマー ---
    is_hammer = detect_hammer(o, h, l, c)
    hammer_signal = "BUY" if is_hammer and not trend_up else "NEUTRAL"
    results["Hammer"] = {
        "value": 1.0 if is_hammer else 0.0,
        "signal": hammer_signal,
        "category": "pattern",
        "details": {"detected": is_hammer, "trend_context": "downtrend" if not trend_up else "uptrend"},
    }

    # --- 逆ハンマー ---
    is_inv_hammer = detect_inverted_hammer(o, h, l, c)
    inv_hammer_signal = "SELL" if is_inv_hammer and trend_up else "NEUTRAL"
    results["Inverted_Hammer"] = {
        "value": 1.0 if is_inv_hammer else 0.0,
        "signal": inv_hammer_signal,
        "category": "pattern",
        "details": {"detected": is_inv_hammer},
    }

    # --- 十字線 ---
    is_doji = detect_doji(o, h, l, c)
    doji_signal = "SELL" if is_doji and trend_up else ("BUY" if is_doji and not trend_up else "NEUTRAL")
    results["Doji"] = {
        "value": 1.0 if is_doji else 0.0,
        "signal": doji_signal,
        "category": "pattern",
        "details": {"detected": is_doji, "trend_reversal_possible": is_doji},
    }

    # --- 強気包み足 ---
    is_bull_engulf = detect_bullish_engulfing(po, pc, o, c)
    results["Bullish_Engulfing"] = {
        "value": 1.0 if is_bull_engulf else 0.0,
        "signal": "BUY" if is_bull_engulf else "NEUTRAL",
        "category": "pattern",
        "details": {"detected": is_bull_engulf},
    }

    # --- 弱気包み足 ---
    is_bear_engulf = detect_bearish_engulfing(po, pc, o, c)
    results["Bearish_Engulfing"] = {
        "value": 1.0 if is_bear_engulf else 0.0,
        "signal": "SELL" if is_bear_engulf else "NEUTRAL",
        "category": "pattern",
        "details": {"detected": is_bear_engulf},
    }

    # --- 三白兵 ---
    is_3ws = detect_three_white_soldiers(df)
    results["Three_White_Soldiers"] = {
        "value": 1.0 if is_3ws else 0.0,
        "signal": "BUY" if is_3ws else "NEUTRAL",
        "category": "pattern",
        "details": {"detected": is_3ws},
    }

    # --- 三羽烏 ---
    is_3bc = detect_three_black_crows(df)
    results["Three_Black_Crows"] = {
        "value": 1.0 if is_3bc else 0.0,
        "signal": "SELL" if is_3bc else "NEUTRAL",
        "category": "pattern",
        "details": {"detected": is_3bc},
    }

    # --- ピンバー ---
    body = _body_size(o, c)
    upper = _upper_shadow(o, c, h)
    lower = _lower_shadow(o, c, l)
    rng = _candle_range(h, l)
    is_bullish_pin = rng > 0 and lower >= rng * 0.6 and body <= rng * 0.3
    is_bearish_pin = rng > 0 and upper >= rng * 0.6 and body <= rng * 0.3

    results["Pin_Bar"] = {
        "value": 1.0 if (is_bullish_pin or is_bearish_pin) else 0.0,
        "signal": "BUY" if is_bullish_pin else ("SELL" if is_bearish_pin else "NEUTRAL"),
        "category": "pattern",
        "details": {
            "detected": is_bullish_pin or is_bearish_pin,
            "type": "bullish" if is_bullish_pin else ("bearish" if is_bearish_pin else "none"),
        },
    }

    return results
