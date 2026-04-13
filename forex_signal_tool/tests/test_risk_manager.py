"""
test_risk_manager.py — Phase 1 リスク管理 単体テスト

SL/TP 価格計算の正確性と、トレーリングストップ更新ロジックを検証する。
JPY ペア前提（1pip = 0.01）。
"""

import sys
import os
import math
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.risk_manager import compute_risk_levels, update_trailing_sl

_PIP = 0.01


def _sl(type_, **kw):
    base = {"type": type_, "pips": None, "lookback_bars": None,
            "buffer_pips": None, "atr_period": None, "atr_multiplier": None}
    return {**base, **kw}


def _tp(type_, **kw):
    base = {"type": type_, "pips": None, "rr_ratio": None,
            "atr_period": None, "atr_multiplier": None}
    return {**base, **kw}


def _trailing(enabled=False, trail_pips=None):
    return {"enabled": enabled,
            "type": "fixedTrailing" if enabled else None,
            "trail_pips": trail_pips}


def _make_df(n=60, base_price=150.0):
    close = pd.Series([base_price] * n)
    df = pd.DataFrame({
        "open":   close,
        "high":   close + 0.2,
        "low":    close - 0.2,
        "close":  close,
        "volume": 1000,
    }, index=pd.date_range("2024-01-01", periods=n, freq="1h"))
    return df


# ===========================================================================
# SL タイプ: fixed
# ===========================================================================

class TestSlFixed:
    def test_buy_sl_below_entry(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20), _tp("rr", rr_ratio=2.0),
            "BUY", 150.0, df, entry_bar_index=30
        )
        assert abs(r["sl_price"] - (150.0 - 20 * _PIP)) < 1e-5
        assert r["sl_pips"] == 20.0

    def test_sell_sl_above_entry(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20), _tp("rr", rr_ratio=2.0),
            "SELL", 150.0, df, entry_bar_index=30
        )
        assert abs(r["sl_price"] - (150.0 + 20 * _PIP)) < 1e-5


# ===========================================================================
# TP タイプ: fixed / rr / atr
# ===========================================================================

class TestTpTypes:
    def test_tp_fixed_buy(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20), _tp("fixed", pips=40),
            "BUY", 150.0, df, entry_bar_index=30
        )
        assert abs(r["tp_price"] - (150.0 + 40 * _PIP)) < 1e-5
        assert r["tp_pips"] == 40.0

    def test_tp_fixed_sell(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20), _tp("fixed", pips=40),
            "SELL", 150.0, df, entry_bar_index=30
        )
        assert abs(r["tp_price"] - (150.0 - 40 * _PIP)) < 1e-5

    def test_tp_rr_ratio(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20), _tp("rr", rr_ratio=2.0),
            "BUY", 150.0, df, entry_bar_index=30
        )
        # TP pips = SL pips × RR = 20 × 2.0 = 40
        assert abs(r["tp_pips"] - 40.0) < 1e-4
        assert abs(r["tp_price"] - (150.0 + 40 * _PIP)) < 1e-4

    def test_tp_rr_sell(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=10), _tp("rr", rr_ratio=1.5),
            "SELL", 150.0, df, entry_bar_index=30
        )
        assert abs(r["tp_pips"] - 15.0) < 1e-4
        assert abs(r["tp_price"] - (150.0 - 15 * _PIP)) < 1e-4

    def test_tp_atr(self):
        df = _make_df()
        r = compute_risk_levels(
            _sl("fixed", pips=20),
            _tp("atr", atr_period=14, atr_multiplier=3.0),
            "BUY", 150.0, df, entry_bar_index=30
        )
        # ATR は flat な df では low_prev_close ≒ 0 なので high-low ≒ 0.4
        # tp_price > entry_price の方向性のみ確認
        assert r["tp_price"] > 150.0


# ===========================================================================
# SL タイプ: recentHighLow
# ===========================================================================

class TestSlRecentHighLow:
    def _df_with_range(self, low_vals, high_vals, n_base=20):
        """low/high が指定された末尾足を持つ df を返す"""
        n = n_base + len(low_vals)
        close = [150.0] * n
        low = [149.8] * n_base + list(low_vals)
        high = [150.2] * n_base + list(high_vals)
        df = pd.DataFrame({
            "open": close, "close": close,
            "high": high, "low": low, "volume": 1000,
        }, index=pd.date_range("2024-01-01", periods=n, freq="1h"))
        return df

    def test_buy_sl_is_recent_low_minus_buffer(self):
        # lookback=5 本の最安値が 148.0 → buffer=3pips → SL = 148.0 - 0.03
        lows  = [148.5, 148.0, 149.0, 148.8, 149.2]
        highs = [l + 0.5 for l in lows]
        df = self._df_with_range(lows, highs)
        entry_bar = len(df)  # 次足（まだ df にない）
        r = compute_risk_levels(
            _sl("recentHighLow", lookback_bars=5, buffer_pips=3),
            _tp("rr", rr_ratio=2.0),
            "BUY", 150.0, df, entry_bar_index=entry_bar
        )
        expected_sl = 148.0 - 3 * _PIP
        assert abs(r["sl_price"] - expected_sl) < 1e-4

    def test_sell_sl_is_recent_high_plus_buffer(self):
        lows  = [149.5, 149.0, 149.2, 149.1, 149.3]
        highs = [152.0, 151.5, 152.5, 151.8, 152.1]
        df = self._df_with_range(lows, highs)
        entry_bar = len(df)
        r = compute_risk_levels(
            _sl("recentHighLow", lookback_bars=5, buffer_pips=2),
            _tp("rr", rr_ratio=2.0),
            "SELL", 150.0, df, entry_bar_index=entry_bar
        )
        expected_sl = 152.5 + 2 * _PIP
        assert abs(r["sl_price"] - expected_sl) < 1e-4


# ===========================================================================
# SL タイプ: atr
# ===========================================================================

class TestSlAtr:
    def test_atr_sl_distance_positive(self):
        df = _make_df(n=60)
        r = compute_risk_levels(
            _sl("atr", atr_period=14, atr_multiplier=1.5),
            _tp("rr", rr_ratio=2.0),
            "BUY", 150.0, df, entry_bar_index=30
        )
        assert r["sl_price"] < 150.0
        assert r["sl_pips"] > 0

    def test_atr_sl_sell(self):
        df = _make_df(n=60)
        r = compute_risk_levels(
            _sl("atr", atr_period=14, atr_multiplier=1.5),
            _tp("rr", rr_ratio=2.0),
            "SELL", 150.0, df, entry_bar_index=30
        )
        assert r["sl_price"] > 150.0


# ===========================================================================
# RiskLevels の方向性チェック
# ===========================================================================

def test_buy_risk_levels_direction():
    df = _make_df()
    r = compute_risk_levels(
        _sl("fixed", pips=20), _tp("fixed", pips=40),
        "BUY", 150.0, df, entry_bar_index=30
    )
    assert r["sl_price"] < 150.0, "BUY の SL は entry より下"
    assert r["tp_price"] > 150.0, "BUY の TP は entry より上"


def test_sell_risk_levels_direction():
    df = _make_df()
    r = compute_risk_levels(
        _sl("fixed", pips=20), _tp("fixed", pips=40),
        "SELL", 150.0, df, entry_bar_index=30
    )
    assert r["sl_price"] > 150.0, "SELL の SL は entry より上"
    assert r["tp_price"] < 150.0, "SELL の TP は entry より下"


# ===========================================================================
# トレーリングストップ更新
# ===========================================================================

class TestTrailingSl:
    def test_trailing_disabled_no_change(self):
        cfg = _trailing(enabled=False)
        new_sl = update_trailing_sl(cfg, 149.0, "BUY", bar_high=152.0, bar_low=148.0)
        assert new_sl == 149.0

    def test_buy_trailing_moves_up(self):
        # trail_pips=10 → SL = bar_high - 0.10
        cfg = _trailing(enabled=True, trail_pips=10)
        new_sl = update_trailing_sl(cfg, 149.0, "BUY", bar_high=151.0, bar_low=149.5)
        expected = 151.0 - 10 * _PIP
        assert abs(new_sl - expected) < 1e-5

    def test_buy_trailing_never_moves_down(self):
        # SL が現在値より下になる場合は現在値を維持
        cfg = _trailing(enabled=True, trail_pips=100)  # 大きすぎる pips
        new_sl = update_trailing_sl(cfg, 150.0, "BUY", bar_high=149.0, bar_low=148.0)
        assert new_sl == 150.0  # 下がらない

    def test_sell_trailing_moves_down(self):
        cfg = _trailing(enabled=True, trail_pips=10)
        new_sl = update_trailing_sl(cfg, 151.0, "SELL", bar_high=150.5, bar_low=149.0)
        expected = 149.0 + 10 * _PIP
        assert abs(new_sl - expected) < 1e-5

    def test_sell_trailing_never_moves_up(self):
        cfg = _trailing(enabled=True, trail_pips=100)
        new_sl = update_trailing_sl(cfg, 149.0, "SELL", bar_high=152.0, bar_low=151.0)
        assert new_sl == 149.0  # 上がらない
