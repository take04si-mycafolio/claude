"""
compute.py — Phase 1 中央インジケーター系列ディスパッチャー

condition_evaluator と riskManager が使用する。
indicator 名と params dict を受け取り、pd.Series を返す。

対応インジケーター名:
  オシレーター系: RSI, MACD_LINE, MACD_SIGNAL, MACD_HIST,
                  STOCH_K, STOCH_D, CCI, WILLIAMS_R
  トレンド系:     SMA, EMA, BB_UPPER, BB_LOWER, BB_MID, BB_WIDTH
  ボラティリティ: ATR
  価格系:        CLOSE, OPEN, HIGH, LOW
"""

from __future__ import annotations

import pandas as pd

from .oscillators import (
    compute_rsi,
    compute_macd_line,
    compute_macd_signal,
    compute_macd_hist,
    compute_stoch_k,
    compute_stoch_d,
    compute_cci,
    compute_williams_r,
)
from .trend import (
    compute_sma,
    compute_ema,
    compute_ema_slope,
    compute_bb_upper,
    compute_bb_lower,
    compute_bb_mid,
    compute_bb_width,
)
from .volatility import compute_atr
from .patterns import (
    compute_hammer,
    compute_inverted_hammer,
    compute_doji,
    compute_bullish_engulfing,
    compute_bearish_engulfing,
    compute_three_white_soldiers,
    compute_three_black_crows,
    compute_bullish_pin_bar,
    compute_bearish_pin_bar,
)


def _close(df: pd.DataFrame, _params: dict) -> pd.Series:
    return df["close"].astype(float)


def _open(df: pd.DataFrame, _params: dict) -> pd.Series:
    return df["open"].astype(float)


def _high(df: pd.DataFrame, _params: dict) -> pd.Series:
    return df["high"].astype(float)


def _low(df: pd.DataFrame, _params: dict) -> pd.Series:
    return df["low"].astype(float)


_REGISTRY: dict[str, callable] = {
    # オシレーター
    "RSI":          compute_rsi,
    "MACD_LINE":    compute_macd_line,
    "MACD_SIGNAL":  compute_macd_signal,
    "MACD_HIST":    compute_macd_hist,
    "STOCH_K":      compute_stoch_k,
    "STOCH_D":      compute_stoch_d,
    "CCI":          compute_cci,
    "WILLIAMS_R":   compute_williams_r,
    # トレンド
    "SMA":          compute_sma,
    "EMA":          compute_ema,
    "EMA_SLOPE":    compute_ema_slope,
    "BB_UPPER":     compute_bb_upper,
    "BB_LOWER":     compute_bb_lower,
    "BB_MID":       compute_bb_mid,
    "BB_WIDTH":     compute_bb_width,
    # ボラティリティ
    "ATR":          compute_atr,
    # 価格系
    "CLOSE":        _close,
    "OPEN":         _open,
    "HIGH":         _high,
    "LOW":          _low,
    # ローソク足パターン（検出=1.0, 未検出=0.0）
    "HAMMER":               compute_hammer,
    "INVERTED_HAMMER":      compute_inverted_hammer,
    "DOJI":                 compute_doji,
    "BULLISH_ENGULFING":    compute_bullish_engulfing,
    "BEARISH_ENGULFING":    compute_bearish_engulfing,
    "THREE_WHITE_SOLDIERS": compute_three_white_soldiers,
    "THREE_BLACK_CROWS":    compute_three_black_crows,
    "BULLISH_PIN_BAR":      compute_bullish_pin_bar,
    "BEARISH_PIN_BAR":      compute_bearish_pin_bar,
}


def compute_series(indicator: str, params: dict, df: pd.DataFrame) -> pd.Series:
    """
    指定した indicator の全系列（pd.Series）を返す。

    Parameters
    ----------
    indicator : str
        インジケーター名（大文字）。_REGISTRY に定義されたキーと一致する必要がある。
    params : dict
        各インジケーター固有のパラメータ。不要なキーは無視される。
        None を渡した場合はデフォルト値が使われる。
    df : pd.DataFrame
        OHLCV データ。columns: open, high, low, close, volume

    Returns
    -------
    pd.Series
        df と同じ長さの系列。先頭付近は NaN になる。

    Raises
    ------
    ValueError
        indicator が未対応の場合。
    """
    fn = _REGISTRY.get(indicator)
    if fn is None:
        raise ValueError(
            f"Unknown indicator: {indicator!r}. "
            f"Supported: {sorted(_REGISTRY)}"
        )
    return fn(df, params)


__all__ = ["compute_series"]
