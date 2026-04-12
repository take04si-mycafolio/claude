"""
metrics_calculator.py — Phase 1 メトリクス計算

List[TradeLog] から BacktestMetrics を算出する純粋関数。
END_OF_DATA トレードは集計から除外する。

定義:
  profit_factor   = gross_profit_pips / gross_loss_pips（損失0時は inf）
  expectancy_pips = (win_rate × avg_win_pips) − ((1−win_rate) × avg_loss_pips)
  max_drawdown_pips = equity curve ピーク→谷の最大下落幅
  avg_rr          = avg_win_pips / avg_loss_pips（損失0時は inf）
"""

from __future__ import annotations

import math
from typing import List

from app.services.data_structures import TradeLog, BacktestMetrics


def calculate_metrics(trades: List[TradeLog]) -> BacktestMetrics:
    """
    List[TradeLog] から BacktestMetrics を算出して返す。

    END_OF_DATA の トレードは集計から除外する。
    trades が空（または全て END_OF_DATA）の場合はゼロ埋めの結果を返す。
    """
    # END_OF_DATA を除外した完結トレードのみ集計
    closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]

    if not closed:
        return _empty_metrics()

    total = len(closed)

    # 勝ち負け分類
    wins_trades  = [t for t in closed if t["pnl_pips"] > 0]
    losses_trades = [t for t in closed if t["pnl_pips"] <= 0]

    wins  = len(wins_trades)
    losses = len(losses_trades)
    win_rate = wins / total if total > 0 else 0.0

    # pips 集計
    gross_profit_pips = sum(t["pnl_pips"] for t in wins_trades)
    gross_loss_pips   = abs(sum(t["pnl_pips"] for t in losses_trades))  # 正値
    net_profit_pips   = gross_profit_pips - gross_loss_pips

    profit_factor = (
        gross_profit_pips / gross_loss_pips if gross_loss_pips > 0
        else math.inf
    )

    avg_win_pips  = gross_profit_pips / wins    if wins    > 0 else 0.0
    avg_loss_pips = gross_loss_pips   / losses  if losses  > 0 else 0.0  # 正値

    avg_rr = (
        avg_win_pips / avg_loss_pips if avg_loss_pips > 0
        else math.inf
    )

    expectancy_pips = (win_rate * avg_win_pips) - ((1.0 - win_rate) * avg_loss_pips)

    # 最大ドローダウン (pips ベース equity curve)
    max_drawdown_pips = _calc_max_drawdown(closed)

    # 連勝・連敗
    max_win_streak, max_loss_streak = _calc_streaks(closed)

    # 平均保有バー数
    avg_holding_bars = (
        sum(t["exit_bar_index"] - t["entry_bar_index"] for t in closed) / total
    )

    # ロング / ショート内訳
    long_trades  = [t for t in closed if t["direction"] == "BUY"]
    short_trades = [t for t in closed if t["direction"] == "SELL"]

    long_wins  = sum(1 for t in long_trades  if t["pnl_pips"] > 0)
    short_wins = sum(1 for t in short_trades if t["pnl_pips"] > 0)

    long_win_rate  = long_wins  / len(long_trades)  if long_trades  else 0.0
    short_win_rate = short_wins / len(short_trades) if short_trades else 0.0

    return BacktestMetrics(
        total_trades=total,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 4),
        gross_profit_pips=round(gross_profit_pips, 2),
        gross_loss_pips=round(gross_loss_pips, 2),
        net_profit_pips=round(net_profit_pips, 2),
        profit_factor=round(profit_factor, 4) if math.isfinite(profit_factor) else profit_factor,
        max_drawdown_pips=round(max_drawdown_pips, 2),
        avg_win_pips=round(avg_win_pips, 2),
        avg_loss_pips=round(avg_loss_pips, 2),
        avg_rr=round(avg_rr, 4) if math.isfinite(avg_rr) else avg_rr,
        expectancy_pips=round(expectancy_pips, 2),
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        avg_holding_bars=round(avg_holding_bars, 1),
        long_trades=len(long_trades),
        short_trades=len(short_trades),
        long_wins=long_wins,
        short_wins=short_wins,
        long_win_rate=round(long_win_rate, 4),
        short_win_rate=round(short_win_rate, 4),
    )


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _calc_max_drawdown(closed: List[TradeLog]) -> float:
    """pips 累積の equity curve でピーク→谷の最大下落幅を計算する。"""
    if not closed:
        return 0.0

    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for t in closed:
        equity += t["pnl_pips"]
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd


def _calc_streaks(closed: List[TradeLog]) -> tuple[int, int]:
    """最大連勝数・最大連敗数を (win_streak, loss_streak) で返す。"""
    max_win = 0
    max_loss = 0
    cur_win = 0
    cur_loss = 0

    for t in closed:
        if t["pnl_pips"] > 0:
            cur_win += 1
            cur_loss = 0
            max_win = max(max_win, cur_win)
        else:
            cur_loss += 1
            cur_win = 0
            max_loss = max(max_loss, cur_loss)

    return max_win, max_loss


def _empty_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        total_trades=0, wins=0, losses=0, win_rate=0.0,
        gross_profit_pips=0.0, gross_loss_pips=0.0, net_profit_pips=0.0,
        profit_factor=0.0, max_drawdown_pips=0.0,
        avg_win_pips=0.0, avg_loss_pips=0.0, avg_rr=0.0, expectancy_pips=0.0,
        max_win_streak=0, max_loss_streak=0, avg_holding_bars=0.0,
        long_trades=0, short_trades=0, long_wins=0, short_wins=0,
        long_win_rate=0.0, short_win_rate=0.0,
    )
