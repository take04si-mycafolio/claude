"""
オシレーター系テクニカル指標
  - RSI (14)
  - MACD (12, 26, 9)
  - Stochastic (14, 3, 3)
  - CCI (20)
  - Williams %R (14)
"""

import pandas as pd
import numpy as np


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period=14, d_period=3, smooth_k=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    stoch_k_smooth = stoch_k.rolling(smooth_k).mean()
    stoch_d = stoch_k_smooth.rolling(d_period).mean()
    return stoch_k_smooth, stoch_d


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, period=20):
    typical_price = (high + low + close) / 3
    sma_tp = typical_price.rolling(period).mean()
    mean_dev = typical_price.rolling(period).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    return (typical_price - sma_tp) / (0.015 * mean_dev)


def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period=14):
    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    return -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan)


def calculate_oscillators(df: pd.DataFrame) -> dict:
    """
    DataFrameからオシレーター系指標を計算し、シグナルとともに返す。

    Returns
    -------
    dict: {
        "RSI_14": {"value": float, "signal": "BUY"|"SELL"|"NEUTRAL", "details": {...}},
        ...
    }
    """
    if df.empty or len(df) < 30:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    results = {}

    # --- RSI ---
    rsi = _rsi(close)
    rsi_val = rsi.iloc[-1]
    if pd.isna(rsi_val):
        rsi_signal = "NEUTRAL"
    elif rsi_val < 30:
        rsi_signal = "BUY"    # 売られすぎ → 買いシグナル
    elif rsi_val > 70:
        rsi_signal = "SELL"   # 買われすぎ → 売りシグナル
    else:
        rsi_signal = "NEUTRAL"

    results["RSI_14"] = {
        "value": round(float(rsi_val), 2) if not pd.isna(rsi_val) else None,
        "signal": rsi_signal,
        "category": "oscillator",
        "details": {
            "overbought": 70,
            "oversold": 30,
        },
    }

    # --- MACD ---
    macd_line, signal_line, histogram = _macd(close)
    macd_val = macd_line.iloc[-1]
    sig_val = signal_line.iloc[-1]
    hist_val = histogram.iloc[-1]
    prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0

    if pd.isna(macd_val) or pd.isna(sig_val):
        macd_signal = "NEUTRAL"
    elif hist_val > 0 and prev_hist <= 0:
        macd_signal = "BUY"   # ヒストグラムがゼロ以上にクロス
    elif hist_val < 0 and prev_hist >= 0:
        macd_signal = "SELL"  # ヒストグラムがゼロ以下にクロス
    elif macd_val > sig_val:
        macd_signal = "BUY"
    elif macd_val < sig_val:
        macd_signal = "SELL"
    else:
        macd_signal = "NEUTRAL"

    results["MACD_12_26_9"] = {
        "value": round(float(macd_val), 6) if not pd.isna(macd_val) else None,
        "signal": macd_signal,
        "category": "oscillator",
        "details": {
            "macd": round(float(macd_val), 6) if not pd.isna(macd_val) else None,
            "signal_line": round(float(sig_val), 6) if not pd.isna(sig_val) else None,
            "histogram": round(float(hist_val), 6) if not pd.isna(hist_val) else None,
        },
    }

    # --- Stochastic ---
    stoch_k, stoch_d = _stochastic(high, low, close)
    sk_val = stoch_k.iloc[-1]
    sd_val = stoch_d.iloc[-1]
    prev_sk = stoch_k.iloc[-2] if len(stoch_k) > 1 else None
    prev_sd = stoch_d.iloc[-2] if len(stoch_d) > 1 else None

    if pd.isna(sk_val) or pd.isna(sd_val):
        stoch_signal = "NEUTRAL"
    elif sk_val < 20 and sd_val < 20:
        if prev_sk is not None and not pd.isna(prev_sk) and sk_val > sd_val and prev_sk <= prev_sd:
            stoch_signal = "BUY"   # 売られすぎゾーンでのゴールデンクロス
        else:
            stoch_signal = "BUY" if sk_val > sd_val else "NEUTRAL"
    elif sk_val > 80 and sd_val > 80:
        if prev_sk is not None and not pd.isna(prev_sk) and sk_val < sd_val and prev_sk >= prev_sd:
            stoch_signal = "SELL"  # 買われすぎゾーンでのデッドクロス
        else:
            stoch_signal = "SELL" if sk_val < sd_val else "NEUTRAL"
    else:
        stoch_signal = "NEUTRAL"

    results["Stochastic_14_3"] = {
        "value": round(float(sk_val), 2) if not pd.isna(sk_val) else None,
        "signal": stoch_signal,
        "category": "oscillator",
        "details": {
            "K": round(float(sk_val), 2) if not pd.isna(sk_val) else None,
            "D": round(float(sd_val), 2) if not pd.isna(sd_val) else None,
        },
    }

    # --- CCI ---
    cci = _cci(high, low, close)
    cci_val = cci.iloc[-1]
    prev_cci = cci.iloc[-2] if len(cci) > 1 else None

    if pd.isna(cci_val):
        cci_signal = "NEUTRAL"
    elif cci_val > 100:
        cci_signal = "SELL"   # 買われすぎ
    elif cci_val < -100:
        cci_signal = "BUY"    # 売られすぎ
    else:
        # ゼロクロスを確認
        if prev_cci is not None and not pd.isna(prev_cci):
            if cci_val > 0 and prev_cci <= 0:
                cci_signal = "BUY"
            elif cci_val < 0 and prev_cci >= 0:
                cci_signal = "SELL"
            else:
                cci_signal = "NEUTRAL"
        else:
            cci_signal = "NEUTRAL"

    results["CCI_20"] = {
        "value": round(float(cci_val), 2) if not pd.isna(cci_val) else None,
        "signal": cci_signal,
        "category": "oscillator",
        "details": {
            "overbought": 100,
            "oversold": -100,
        },
    }

    # --- Williams %R ---
    wr = _williams_r(high, low, close)
    wr_val = wr.iloc[-1]

    if pd.isna(wr_val):
        wr_signal = "NEUTRAL"
    elif wr_val > -20:
        wr_signal = "SELL"    # 買われすぎ
    elif wr_val < -80:
        wr_signal = "BUY"     # 売られすぎ
    else:
        wr_signal = "NEUTRAL"

    results["Williams_R_14"] = {
        "value": round(float(wr_val), 2) if not pd.isna(wr_val) else None,
        "signal": wr_signal,
        "category": "oscillator",
        "details": {
            "overbought": -20,
            "oversold": -80,
        },
    }

    return results


# ---------------------------------------------------------------------------
# Phase 1 — parameterizable series computers (condition_evaluator 用)
# ---------------------------------------------------------------------------

def compute_rsi(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """RSI の全系列を返す。params: {"period": int} (default 14)"""
    p = params or {}
    return _rsi(df["close"].astype(float), p.get("period", 14))


def compute_macd_line(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """MACD ライン（fast EMA − slow EMA）。params: {"fast", "slow", "signal"}"""
    p = params or {}
    line, _, _ = _macd(df["close"].astype(float),
                       p.get("fast", 12), p.get("slow", 26), p.get("signal", 9))
    return line


def compute_macd_signal(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """MACD シグナルライン。params: {"fast", "slow", "signal"}"""
    p = params or {}
    _, signal_line, _ = _macd(df["close"].astype(float),
                              p.get("fast", 12), p.get("slow", 26), p.get("signal", 9))
    return signal_line


def compute_macd_hist(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """MACD ヒストグラム（MACD − signal）。params: {"fast", "slow", "signal"}"""
    p = params or {}
    _, _, histogram = _macd(df["close"].astype(float),
                            p.get("fast", 12), p.get("slow", 26), p.get("signal", 9))
    return histogram


def compute_stoch_k(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Stochastic %K 系列。params: {"k_period", "d_period", "smooth_k"}"""
    p = params or {}
    k, _ = _stochastic(df["high"].astype(float), df["low"].astype(float),
                       df["close"].astype(float),
                       p.get("k_period", 14), p.get("d_period", 3), p.get("smooth_k", 3))
    return k


def compute_stoch_d(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Stochastic %D 系列。params: {"k_period", "d_period", "smooth_k"}"""
    p = params or {}
    _, d = _stochastic(df["high"].astype(float), df["low"].astype(float),
                       df["close"].astype(float),
                       p.get("k_period", 14), p.get("d_period", 3), p.get("smooth_k", 3))
    return d


def compute_cci(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """CCI 系列。params: {"period"} (default 20)"""
    p = params or {}
    return _cci(df["high"].astype(float), df["low"].astype(float),
                df["close"].astype(float), p.get("period", 20))


def compute_williams_r(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """Williams %R 系列。params: {"period"} (default 14)"""
    p = params or {}
    return _williams_r(df["high"].astype(float), df["low"].astype(float),
                       df["close"].astype(float), p.get("period", 14))
