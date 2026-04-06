"""
ライン系テクニカル指標
  - ピボットポイント (Classic)
  - フィボナッチリトレースメント
  - サポート・レジスタンス（動的）
"""

import pandas as pd
import numpy as np


def _pivot_classic(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """クラシックピボットポイントとサポート・レジスタンスを計算"""
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    r2 = pivot + (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)
    s1 = 2 * pivot - prev_high
    s2 = pivot - (prev_high - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)
    return {
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3,
    }


def _fibonacci_levels(swing_high: float, swing_low: float, is_uptrend: bool) -> dict:
    """フィボナッチリトレースメントレベルを計算"""
    diff = swing_high - swing_low
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    if is_uptrend:
        levels = {f"fib_{int(r*1000)}": swing_high - diff * r for r in ratios}
    else:
        levels = {f"fib_{int(r*1000)}": swing_low + diff * r for r in ratios}
    return levels


def _find_swing_highs_lows(high: pd.Series, low: pd.Series, window: int = 5):
    """スウィングハイ・ローを検出"""
    swing_highs = []
    swing_lows = []
    for i in range(window, len(high) - window):
        if high.iloc[i] == high.iloc[i - window:i + window + 1].max():
            swing_highs.append((i, float(high.iloc[i])))
        if low.iloc[i] == low.iloc[i - window:i + window + 1].min():
            swing_lows.append((i, float(low.iloc[i])))
    return swing_highs, swing_lows


def _dynamic_support_resistance(high: pd.Series, low: pd.Series, close: pd.Series,
                                 window: int = 20, tolerance: float = 0.001) -> dict:
    """動的サポート・レジスタンスレベルを検出"""
    swing_highs, swing_lows = _find_swing_highs_lows(high, low)

    current_price = float(close.iloc[-1])

    # クラスタリングでキーレベルを特定
    resistance_levels = sorted([h for _, h in swing_highs], reverse=True)
    support_levels = sorted([l for _, l in swing_lows])

    # 現在値より上の直近レジスタンス
    resistances_above = [r for r in resistance_levels if r > current_price * (1 + tolerance)]
    # 現在値より下の直近サポート
    supports_below = [s for s in support_levels if s < current_price * (1 - tolerance)]

    nearest_resistance = resistances_above[0] if resistances_above else None
    nearest_support = supports_below[-1] if supports_below else None

    return {
        "nearest_resistance": nearest_resistance,
        "nearest_support": nearest_support,
        "all_resistances": resistances_above[:3],
        "all_supports": supports_below[-3:] if len(supports_below) >= 3 else supports_below,
    }


def calculate_lines(df: pd.DataFrame) -> dict:
    """
    DataFrameからライン系指標を計算し、シグナルとともに返す。
    """
    if df.empty or len(df) < 20:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    current_price = float(close.iloc[-1])
    results = {}

    # --- ピボットポイント (前日の高値・安値・終値を使用) ---
    # 日足データが無い場合は直近の期間で代替
    lookback = min(len(df) - 1, 20)
    prev_high = float(high.iloc[-lookback:-1].max()) if lookback > 0 else float(high.iloc[-2])
    prev_low = float(low.iloc[-lookback:-1].min()) if lookback > 0 else float(low.iloc[-2])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1])

    pivots = _pivot_classic(prev_high, prev_low, prev_close)
    pivot = pivots["pivot"]

    # 現在値とピボットの位置関係でシグナル判定
    if current_price > pivots["r1"]:
        pivot_signal = "BUY"    # R1突破 → 強気
    elif current_price < pivots["s1"]:
        pivot_signal = "SELL"   # S1割れ → 弱気
    elif current_price > pivot:
        pivot_signal = "BUY"
    else:
        pivot_signal = "SELL"

    results["Pivot_Classic"] = {
        "value": round(pivot, 3),
        "signal": pivot_signal,
        "category": "line",
        "details": {
            "pivot": round(pivot, 3),
            "r1": round(pivots["r1"], 3),
            "r2": round(pivots["r2"], 3),
            "r3": round(pivots["r3"], 3),
            "s1": round(pivots["s1"], 3),
            "s2": round(pivots["s2"], 3),
            "s3": round(pivots["s3"], 3),
            "current_price": round(current_price, 3),
        },
    }

    # --- フィボナッチリトレースメント ---
    # 過去N本の高値・安値でスウィングを特定
    fib_window = min(len(df), 50)
    period_high = float(high.iloc[-fib_window:].max())
    period_low = float(low.iloc[-fib_window:].min())
    high_idx = high.iloc[-fib_window:].idxmax()
    low_idx = low.iloc[-fib_window:].idxmin()

    is_uptrend = high_idx > low_idx  # 安値→高値の順なら上昇トレンド

    fib_levels = _fibonacci_levels(period_high, period_low, is_uptrend)

    # フィボナッチレベルとの位置関係
    fib_50 = fib_levels.get("fib_500", (period_high + period_low) / 2)
    fib_618 = fib_levels.get("fib_618", period_low + (period_high - period_low) * 0.382)

    if is_uptrend:
        # 上昇トレンド: 61.8%リトレースメント付近は押し目買い
        if abs(current_price - fib_618) / fib_618 < 0.002:
            fib_signal = "BUY"
        elif current_price > fib_50:
            fib_signal = "BUY"
        else:
            fib_signal = "SELL"
    else:
        if abs(current_price - fib_618) / fib_618 < 0.002:
            fib_signal = "SELL"
        elif current_price < fib_50:
            fib_signal = "SELL"
        else:
            fib_signal = "BUY"

    results["Fibonacci_Retracement"] = {
        "value": round(current_price, 3),
        "signal": fib_signal,
        "category": "line",
        "details": {
            "swing_high": round(period_high, 3),
            "swing_low": round(period_low, 3),
            "is_uptrend": is_uptrend,
            "fib_236": round(fib_levels.get("fib_236", 0), 3),
            "fib_382": round(fib_levels.get("fib_382", 0), 3),
            "fib_500": round(fib_levels.get("fib_500", 0), 3),
            "fib_618": round(fib_levels.get("fib_618", 0), 3),
            "current_price": round(current_price, 3),
        },
    }

    # --- 動的サポート・レジスタンス ---
    sr = _dynamic_support_resistance(high, low, close)
    nearest_res = sr["nearest_resistance"]
    nearest_sup = sr["nearest_support"]

    if nearest_res and nearest_sup:
        dist_to_res = (nearest_res - current_price) / current_price
        dist_to_sup = (current_price - nearest_sup) / current_price

        # レジスタンスに近い → 売り検討、サポートに近い → 買い検討
        if dist_to_sup < dist_to_res and dist_to_sup < 0.005:
            sr_signal = "BUY"
        elif dist_to_res < dist_to_sup and dist_to_res < 0.005:
            sr_signal = "SELL"
        elif dist_to_res < dist_to_sup:
            sr_signal = "SELL"
        else:
            sr_signal = "BUY"
    else:
        sr_signal = "NEUTRAL"

    results["Support_Resistance"] = {
        "value": round(current_price, 3),
        "signal": sr_signal,
        "category": "line",
        "details": {
            "nearest_resistance": round(nearest_res, 3) if nearest_res else None,
            "nearest_support": round(nearest_sup, 3) if nearest_sup else None,
            "current_price": round(current_price, 3),
        },
    }

    return results
