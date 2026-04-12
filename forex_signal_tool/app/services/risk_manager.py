"""
risk_manager.py — Phase 1 リスク管理モジュール

エントリー時点の SL/TP 価格を計算し RiskLevels を返す。
トレーリングストップ更新ロジックも提供する。

JPY ペア前提: 1 pip = 0.01 円（USD/JPY, GBP/JPY, EUR/JPY）
"""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd
import numpy as np

from app.services.data_structures import (
    StopLossConfig,
    TakeProfitConfig,
    TrailingStopConfig,
    RiskLevels,
)
from app.services.indicators.volatility import compute_atr

# JPY ペアの 1 pip = 0.01 円
_PIP = 0.01


def _pips_to_price(pips: float) -> float:
    return pips * _PIP


# ---------------------------------------------------------------------------
# SL 計算
# ---------------------------------------------------------------------------

def _calc_sl_price(
    sl_config: StopLossConfig,
    direction: Literal["BUY", "SELL"],
    entry_price: float,
    df: pd.DataFrame,
    entry_bar_index: int,
) -> tuple[float, float]:
    """
    SL 価格と SL pips を返す (sl_price, sl_pips)。
    df は全系列。entry_bar_index は約定足インデックス（次足始値）。
    SL 計算に使う高値・安値は entry_bar_index-1 以前（確定足）。
    """
    sl_type = sl_config["type"]

    if sl_type == "fixed":
        pips = float(sl_config["pips"])
        distance = _pips_to_price(pips)
        if direction == "BUY":
            sl_price = entry_price - distance
        else:
            sl_price = entry_price + distance
        return sl_price, pips

    if sl_type == "recentHighLow":
        lookback = int(sl_config["lookback_bars"])
        buffer_pips = float(sl_config.get("buffer_pips") or 0.0)
        buffer = _pips_to_price(buffer_pips)

        # entry_bar_index の確定足は index-1 まで
        window_end = entry_bar_index  # exclusive: bars[0 : entry_bar_index]
        window_start = max(0, window_end - lookback)
        window = df.iloc[window_start:window_end]

        if window.empty:
            # フォールバック: entry から 20 pips
            fallback_pips = 20.0
            distance = _pips_to_price(fallback_pips)
            sl_price = entry_price - distance if direction == "BUY" else entry_price + distance
            return sl_price, fallback_pips

        if direction == "BUY":
            sl_price = float(window["low"].min()) - buffer
            sl_pips = max((entry_price - sl_price) / _PIP, 1.0)
        else:
            sl_price = float(window["high"].max()) + buffer
            sl_pips = max((sl_price - entry_price) / _PIP, 1.0)

        return sl_price, round(sl_pips, 2)

    if sl_type == "atr":
        atr_period = int(sl_config["atr_period"])
        atr_mult = float(sl_config["atr_multiplier"])

        atr_series = compute_atr(df, {"period": atr_period})
        # 確定足のATR: entry_bar_index - 1
        atr_idx = max(0, entry_bar_index - 1)
        atr_val = atr_series.iloc[atr_idx]
        if pd.isna(atr_val):
            atr_val = _pips_to_price(20.0)  # フォールバック 20 pips

        distance = float(atr_val) * atr_mult
        sl_pips = distance / _PIP

        if direction == "BUY":
            sl_price = entry_price - distance
        else:
            sl_price = entry_price + distance

        return sl_price, round(sl_pips, 2)

    raise ValueError(f"Unknown SL type: {sl_type!r}")


# ---------------------------------------------------------------------------
# TP 計算
# ---------------------------------------------------------------------------

def _calc_tp_price(
    tp_config: TakeProfitConfig,
    direction: Literal["BUY", "SELL"],
    entry_price: float,
    sl_pips: float,
    df: pd.DataFrame,
    entry_bar_index: int,
) -> tuple[float, float]:
    """
    TP 価格と TP pips を返す (tp_price, tp_pips)。
    """
    tp_type = tp_config["type"]

    if tp_type == "fixed":
        pips = float(tp_config["pips"])
        distance = _pips_to_price(pips)
        if direction == "BUY":
            tp_price = entry_price + distance
        else:
            tp_price = entry_price - distance
        return tp_price, pips

    if tp_type == "rr":
        rr = float(tp_config["rr_ratio"])
        tp_pips = sl_pips * rr
        distance = _pips_to_price(tp_pips)
        if direction == "BUY":
            tp_price = entry_price + distance
        else:
            tp_price = entry_price - distance
        return tp_price, round(tp_pips, 2)

    if tp_type == "atr":
        atr_period = int(tp_config["atr_period"])
        atr_mult = float(tp_config["atr_multiplier"])

        atr_series = compute_atr(df, {"period": atr_period})
        atr_idx = max(0, entry_bar_index - 1)
        atr_val = atr_series.iloc[atr_idx]
        if pd.isna(atr_val):
            atr_val = _pips_to_price(20.0)

        distance = float(atr_val) * atr_mult
        tp_pips = distance / _PIP

        if direction == "BUY":
            tp_price = entry_price + distance
        else:
            tp_price = entry_price - distance

        return tp_price, round(tp_pips, 2)

    raise ValueError(f"Unknown TP type: {tp_type!r}")


# ---------------------------------------------------------------------------
# 公開 API: エントリー時の RiskLevels 計算
# ---------------------------------------------------------------------------

def compute_risk_levels(
    sl_config: StopLossConfig,
    tp_config: TakeProfitConfig,
    direction: Literal["BUY", "SELL"],
    entry_price: float,
    df: pd.DataFrame,
    entry_bar_index: int,
) -> RiskLevels:
    """
    エントリー時の SL/TP 価格を計算して RiskLevels を返す。

    Parameters
    ----------
    sl_config        : StopLossConfig
    tp_config        : TakeProfitConfig
    direction        : "BUY" or "SELL"
    entry_price      : 約定価格（次足始値）
    df               : OHLCV 全系列
    entry_bar_index  : 約定足インデックス（bar[i] — next-bar open）

    Returns
    -------
    RiskLevels
    """
    sl_price, sl_pips = _calc_sl_price(
        sl_config, direction, entry_price, df, entry_bar_index
    )
    tp_price, tp_pips = _calc_tp_price(
        tp_config, direction, entry_price, sl_pips, df, entry_bar_index
    )

    return RiskLevels(
        sl_price=round(sl_price, 5),
        tp_price=round(tp_price, 5),
        sl_pips=round(sl_pips, 2),
        tp_pips=round(tp_pips, 2),
    )


# ---------------------------------------------------------------------------
# トレーリングストップ更新
# ---------------------------------------------------------------------------

def update_trailing_sl(
    trailing_config: TrailingStopConfig,
    current_sl: float,
    direction: Literal["BUY", "SELL"],
    bar_high: float,
    bar_low: float,
) -> float:
    """
    1本分の足データを処理してトレーリングSLを更新し、新しい SL 価格を返す。

    fixedTrailing タイプ:
      BUY  の場合: bar の high が (現SL + trail_pips * 2) を超えたら SL を引き上げる
      SELL の場合: bar の low  が (現SL - trail_pips * 2) を下回ったら SL を引き下げる

    SL が不利方向に動くことはない（一方向のみ追従）。

    Parameters
    ----------
    trailing_config : TrailingStopConfig
    current_sl      : 現在の SL 価格
    direction       : "BUY" or "SELL"
    bar_high        : 評価中の足の高値
    bar_low         : 評価中の足の安値

    Returns
    -------
    float — 更新後の SL 価格（変化がなければ current_sl をそのまま返す）
    """
    if not trailing_config.get("enabled", False):
        return current_sl

    trail_pips = float(trailing_config.get("trail_pips") or 0.0)
    if trail_pips <= 0:
        return current_sl

    trail_dist = _pips_to_price(trail_pips)

    if direction == "BUY":
        # 価格が有利方向（上）に動いた場合、SL を bar_high - trail_dist に引き上げ
        new_sl = bar_high - trail_dist
        return max(new_sl, current_sl)  # SL は上方向にのみ動く
    else:
        # 価格が有利方向（下）に動いた場合、SL を bar_low + trail_dist に引き下げ
        new_sl = bar_low + trail_dist
        return min(new_sl, current_sl)  # SL は下方向にのみ動く
