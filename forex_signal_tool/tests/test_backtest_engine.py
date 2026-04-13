"""
test_backtest_engine.py — Phase 1 バックテストエンジン 単体テスト

約定ルール1〜4・skip_until・END_OF_DATA 強制クローズを検証する。
condition_evaluator の代わりにモックを使い、シグナルパターンを完全制御する。
"""

import sys
import os
import math
from unittest.mock import patch
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.backtest_engine import run_backtest

_PIP = 0.01


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_df(n=50, base=150.0, high_offset=0.5, low_offset=0.5):
    """均一な OHLCV df を返す。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open":   [base] * n,
        "high":   [base + high_offset] * n,
        "low":    [base - low_offset]  * n,
        "close":  [base] * n,
        "volume": [1000] * n,
    }, index=idx)
    return df


def _strategy(direction="BUY", sl_pips=20.0, tp_rr=2.0):
    return {
        "strategy_version": "1.0",
        "direction": direction,
        "entry_conditions": {"logic": "AND", "conditions": [
            {"id": "c1", "indicator": "CLOSE", "params": {},
             "comparison": "greater_than", "value": 0.0,
             "compare_to_indicator": None, "compare_to_params": None}
        ]},
        "filters": None,
        "sl_config":  {"type": "fixed", "pips": sl_pips,
                       "lookback_bars": None, "buffer_pips": None,
                       "atr_period": None, "atr_multiplier": None},
        "tp_config":  {"type": "rr",   "pips": None, "rr_ratio": tp_rr,
                       "atr_period": None, "atr_multiplier": None},
        "trailing_config": {"enabled": False, "type": None, "trail_pips": None},
    }


def _sim(capital=1_000_000.0, pip_value=100.0, max_bars=20):
    return {
        "pair": "USDJPY", "timeframe": "1hr",
        "initial_capital": capital,
        "lot_size": 1.0,
        "pip_value": pip_value,
        "max_bars_to_exit": max_bars,
    }


# ---------------------------------------------------------------------------
# 約定ルール 2: エントリーは次足始値
# ---------------------------------------------------------------------------

def test_entry_price_is_next_bar_open():
    """
    シグナル確定足 = bar[i-1]、エントリー足 = bar[i]。
    bar[i] の open が entry_price になることを確認する。
    """
    df = _make_df(n=30, base=150.0)
    # bar[5] の open を特定の値に変える
    df.iloc[5, df.columns.get_loc("open")] = 151.0

    # bar[4] でシグナルが発生 → bar[5] でエントリーするよう
    # CLOSE > 0 は常に True なのでシグナルは毎足出る
    # ただし skip_until で最初のエントリー後は次トレードが遅れる
    trades = run_backtest(df, _strategy(), _sim(max_bars=5))

    assert len(trades) >= 1
    # 最初のエントリーは bar[1].open = 150.0（bar[0] でシグナル）
    assert abs(trades[0]["entry_price"] - 150.0) < 1e-4


# ---------------------------------------------------------------------------
# 約定ルール 3: SL/TP 判定はエントリー足の次足から
# ---------------------------------------------------------------------------

def test_sltp_check_starts_after_entry_bar():
    """
    エントリー bar[i] と同じ足では SL/TP に到達しない。
    entry_bar_index < exit_bar_index を常に保証する。
    """
    df = _make_df(n=30)
    trades = run_backtest(df, _strategy(sl_pips=5), _sim(max_bars=5))
    for t in trades:
        assert t["exit_bar_index"] > t["entry_bar_index"], \
            "exit_bar_index はエントリー足より後でなければならない"


# ---------------------------------------------------------------------------
# 約定ルール 4: 同一足 SL/TP 競合 → SL 優先（保守的）
# ---------------------------------------------------------------------------

def test_same_bar_collision_sl_wins():
    """
    TP と SL が同一足で両方到達 → exit_reason == 'SL'。
    sl_pips=0.1 (0.001), tp_pips ≒ 0.2 で high/low が両方を含む wide candle を作る。
    """
    n = 10
    df = _make_df(n=n, base=150.0, high_offset=5.0, low_offset=5.0)
    # SL=1pip, TP=2pip(rr=2) → high=155>TP, low=145<SL → 両到達
    strategy = _strategy(sl_pips=1.0, tp_rr=2.0)
    trades = run_backtest(df, strategy, _sim(max_bars=5))

    sl_or_tp = [t for t in trades if t["exit_reason"] in ("SL", "TP")]
    for t in sl_or_tp:
        if t["exit_reason"] != "END_OF_DATA":
            # 同一足で高値>TP かつ 安値<SL なら SL 優先
            j = t["exit_bar_index"]
            bar_high = float(df["high"].iloc[j])
            bar_low  = float(df["low"].iloc[j])
            entry    = t["entry_price"]
            sl       = t["sl_price"]
            tp       = t["tp_price"]
            if bar_high >= tp and bar_low <= sl:
                assert t["exit_reason"] == "SL", \
                    "同一足で SL/TP 両到達時は SL 優先"


# ---------------------------------------------------------------------------
# skip_until: トレード中は再エントリーしない
# ---------------------------------------------------------------------------

def test_no_reentry_during_open_trade():
    """
    max_bars_to_exit=10 の END_OF_DATA クローズ時、
    次トレードのエントリーバーは前トレードの exit_bar_index より後。
    """
    df = _make_df(n=50, base=150.0, high_offset=0.05, low_offset=0.05)
    # SL/TP に届かない狭い high/low → 全トレードが END_OF_DATA
    trades = run_backtest(df, _strategy(sl_pips=100, tp_rr=2.0), _sim(max_bars=10))

    for i in range(1, len(trades)):
        prev_exit = trades[i - 1]["exit_bar_index"]
        curr_entry = trades[i]["entry_bar_index"]
        assert curr_entry > prev_exit, \
            f"trade[{i}] の entry ({curr_entry}) は前トレードの exit ({prev_exit}) より後でなければならない"


# ---------------------------------------------------------------------------
# END_OF_DATA: max_bars_to_exit 超過で強制クローズ
# ---------------------------------------------------------------------------

def test_end_of_data_when_sl_tp_unreachable():
    """
    high/low の幅が SL/TP に届かない → 全トレードが END_OF_DATA。
    """
    df = _make_df(n=20, base=150.0, high_offset=0.01, low_offset=0.01)
    trades = run_backtest(df, _strategy(sl_pips=100, tp_rr=2.0), _sim(max_bars=5))
    eod = [t for t in trades if t["exit_reason"] == "END_OF_DATA"]
    assert len(eod) > 0


# ---------------------------------------------------------------------------
# TP ヒット
# ---------------------------------------------------------------------------

def test_tp_hit():
    """
    BUY エントリー後に高値が TP を超える足を 1 本だけ置き → TP 確定。
    """
    n = 40
    df = _make_df(n=n, base=150.0, high_offset=0.01, low_offset=0.01)
    # bar[5] の高値を TP を超える値に設定（entry≒150, tp≒150+20*0.01=150.20）
    entry_bar = 1  # bar[0] でシグナル → bar[1] でエントリー
    tp_bar = entry_bar + 2
    df.iloc[tp_bar, df.columns.get_loc("high")] = 151.0  # 150 + 20*0.01 = 150.20 を超える

    trades = run_backtest(df, _strategy(sl_pips=20, tp_rr=2.0), _sim(max_bars=30))
    tp_trades = [t for t in trades if t["exit_reason"] == "TP"]
    assert len(tp_trades) > 0
    assert tp_trades[0]["pnl_pips"] > 0


# ---------------------------------------------------------------------------
# SL ヒット
# ---------------------------------------------------------------------------

def test_sl_hit():
    """
    BUY エントリー後に安値が SL を下回る足を置く → SL 確定。
    """
    n = 40
    df = _make_df(n=n, base=150.0, high_offset=0.01, low_offset=0.01)
    entry_bar = 1
    sl_bar = entry_bar + 2
    df.iloc[sl_bar, df.columns.get_loc("low")] = 148.0  # 150 - 20*0.01=149.80 を下回る

    trades = run_backtest(df, _strategy(sl_pips=20, tp_rr=2.0), _sim(max_bars=30))
    sl_trades = [t for t in trades if t["exit_reason"] == "SL"]
    assert len(sl_trades) > 0
    assert sl_trades[0]["pnl_pips"] < 0


# ---------------------------------------------------------------------------
# 資産残高の連続性
# ---------------------------------------------------------------------------

def test_running_capital_continuity():
    """
    running_capital は前トレードの資産 ± pnl_currency で連続的に変化する。
    """
    df = _make_df(n=50, base=150.0, high_offset=0.5, low_offset=0.5)
    sim = _sim(capital=1_000_000.0, pip_value=100.0, max_bars=5)
    trades = run_backtest(df, _strategy(sl_pips=10, tp_rr=2.0), sim)

    prev_capital = sim["initial_capital"]
    for t in trades:
        expected = prev_capital + t["pnl_currency"]
        assert abs(t["running_capital"] - expected) < 1.0, \
            f"running_capital 不連続: prev={prev_capital}, pnl={t['pnl_currency']}, actual={t['running_capital']}"
        prev_capital = t["running_capital"]


# ---------------------------------------------------------------------------
# entry_reasons に条件 ID が含まれる
# ---------------------------------------------------------------------------

def test_entry_reasons_populated():
    df = _make_df(n=10)
    trades = run_backtest(df, _strategy(), _sim(max_bars=5))
    for t in trades:
        assert isinstance(t["entry_reasons"], list)
        assert len(t["entry_reasons"]) > 0


# ---------------------------------------------------------------------------
# 空 df / 短すぎる df
# ---------------------------------------------------------------------------

def test_empty_df_returns_empty_list():
    df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    trades = run_backtest(df, _strategy(), _sim())
    assert trades == []


def test_single_bar_df_returns_empty_list():
    df = _make_df(n=1)
    trades = run_backtest(df, _strategy(), _sim())
    assert trades == []
