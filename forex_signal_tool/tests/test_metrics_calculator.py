"""
test_metrics_calculator.py — Phase 1 メトリクス計算 単体テスト

Flask / DB 不要。TradeLog を直接構築して calculate_metrics() を検証する。
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.metrics_calculator import calculate_metrics


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _trade(direction="BUY", pnl_pips=10.0, entry_bar=1, exit_bar=5,
           exit_reason="TP", capital=1_010_000.0):
    """最小限の TradeLog ダミーを返す。"""
    return {
        "trade_id":        "x",
        "direction":       direction,
        "entry_bar_index": entry_bar,
        "exit_bar_index":  exit_bar,
        "entry_time":      "2024-01-01T00:00:00",
        "exit_time":       "2024-01-01T05:00:00",
        "entry_price":     150.0,
        "exit_price":      150.1,
        "sl_price":        149.8,
        "tp_price":        150.2,
        "pnl_pips":        pnl_pips,
        "pnl_currency":    pnl_pips * 100,
        "running_capital": capital,
        "exit_reason":     exit_reason,
        "entry_reasons":   ["c1"],
    }


# ---------------------------------------------------------------------------
# 空リスト → ゼロ埋め
# ---------------------------------------------------------------------------

def test_empty_trades_returns_zero_metrics():
    m = calculate_metrics([])
    assert m["total_trades"] == 0
    assert m["win_rate"] == 0.0
    assert m["profit_factor"] == 0.0


def test_all_end_of_data_treated_as_empty():
    trades = [_trade(pnl_pips=5.0, exit_reason="END_OF_DATA") for _ in range(3)]
    m = calculate_metrics(trades)
    assert m["total_trades"] == 0


# ---------------------------------------------------------------------------
# 基本集計
# ---------------------------------------------------------------------------

def test_total_trades_excludes_end_of_data():
    trades = [
        _trade(pnl_pips=10.0, exit_reason="TP"),
        _trade(pnl_pips=-5.0, exit_reason="SL"),
        _trade(pnl_pips=8.0,  exit_reason="END_OF_DATA"),  # 除外
    ]
    m = calculate_metrics(trades)
    assert m["total_trades"] == 2
    assert m["wins"]   == 1
    assert m["losses"] == 1


def test_win_rate():
    trades = [_trade(pnl_pips=p) for p in [10, 20, -5, 15, -3]]
    m = calculate_metrics(trades)
    assert m["wins"]   == 3
    assert m["losses"] == 2
    assert abs(m["win_rate"] - 0.6) < 1e-6


# ---------------------------------------------------------------------------
# profit_factor / expectancy
# ---------------------------------------------------------------------------

def test_profit_factor_basic():
    trades = [
        _trade(pnl_pips=20.0, exit_reason="TP"),
        _trade(pnl_pips=10.0, exit_reason="TP"),
        _trade(pnl_pips=-10.0, exit_reason="SL"),
    ]
    m = calculate_metrics(trades)
    # gross_profit=30, gross_loss=10 → PF=3.0
    assert abs(m["profit_factor"] - 3.0) < 1e-6
    assert abs(m["gross_profit_pips"] - 30.0) < 1e-6
    assert abs(m["gross_loss_pips"]   - 10.0) < 1e-6


def test_profit_factor_inf_when_no_loss():
    trades = [_trade(pnl_pips=10.0, exit_reason="TP") for _ in range(3)]
    m = calculate_metrics(trades)
    assert math.isinf(m["profit_factor"])


def test_expectancy_pips():
    # win_rate=0.5, avg_win=20, avg_loss=10
    # expectancy = 0.5*20 - 0.5*10 = 5.0
    trades = [
        _trade(pnl_pips=20.0, exit_reason="TP"),
        _trade(pnl_pips=-10.0, exit_reason="SL"),
    ]
    m = calculate_metrics(trades)
    assert abs(m["expectancy_pips"] - 5.0) < 1e-4


# ---------------------------------------------------------------------------
# 最大ドローダウン
# ---------------------------------------------------------------------------

def test_max_drawdown_simple():
    # equity curve: +10, +20, -15, +5
    # cumulative:    10,  30,  15,  20
    # peak=30, trough=15 → dd=15
    trades = [
        _trade(pnl_pips=10.0),
        _trade(pnl_pips=20.0),
        _trade(pnl_pips=-15.0, exit_reason="SL"),
        _trade(pnl_pips=5.0),
    ]
    m = calculate_metrics(trades)
    assert abs(m["max_drawdown_pips"] - 15.0) < 1e-6


def test_max_drawdown_no_loss():
    trades = [_trade(pnl_pips=10.0) for _ in range(5)]
    m = calculate_metrics(trades)
    assert m["max_drawdown_pips"] == 0.0


# ---------------------------------------------------------------------------
# 連勝・連敗
# ---------------------------------------------------------------------------

def test_streaks():
    # W W L W W W L L
    pnls = [10, 5, -3, 8, 4, 6, -2, -1]
    trades = [_trade(pnl_pips=p, exit_reason="TP" if p > 0 else "SL") for p in pnls]
    m = calculate_metrics(trades)
    assert m["max_win_streak"]  == 3
    assert m["max_loss_streak"] == 2


# ---------------------------------------------------------------------------
# ロング / ショート内訳
# ---------------------------------------------------------------------------

def test_long_short_win_rates():
    trades = [
        _trade(direction="BUY",  pnl_pips=10.0),
        _trade(direction="BUY",  pnl_pips=-5.0, exit_reason="SL"),
        _trade(direction="SELL", pnl_pips=8.0),
        _trade(direction="SELL", pnl_pips=6.0),
    ]
    m = calculate_metrics(trades)
    assert m["long_trades"]   == 2
    assert m["short_trades"]  == 2
    assert m["long_wins"]     == 1
    assert m["short_wins"]    == 2
    assert abs(m["long_win_rate"]  - 0.5) < 1e-6
    assert abs(m["short_win_rate"] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# avg_rr / avg_holding_bars
# ---------------------------------------------------------------------------

def test_avg_rr():
    trades = [
        _trade(pnl_pips=20.0),
        _trade(pnl_pips=-10.0, exit_reason="SL"),
    ]
    m = calculate_metrics(trades)
    # avg_win=20, avg_loss=10 → rr=2.0
    assert abs(m["avg_rr"] - 2.0) < 1e-6


def test_avg_holding_bars():
    trades = [
        _trade(entry_bar=0, exit_bar=10),   # 10 bars
        _trade(entry_bar=0, exit_bar=20),   # 20 bars
    ]
    m = calculate_metrics(trades)
    assert abs(m["avg_holding_bars"] - 15.0) < 1e-6
