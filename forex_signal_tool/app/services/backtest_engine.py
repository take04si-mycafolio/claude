"""
backtest_engine.py — Phase 1 バックテストエンジン

約定ルール（data_structures.py 参照）:
  1. シグナル判定は確定足（bar[i-1]）ベース
  2. エントリーは次足始値（bar[i].open）
  3. SL/TP 判定は bar[i+1] 以降
  4. 同一足 SL/TP 競合 → SL 優先（保守的）

メイン関数: run_backtest(df, strategy_config, sim_params) -> List[TradeLog]
"""

from __future__ import annotations

import uuid
from typing import List, Literal, Optional

import pandas as pd
import numpy as np

from app.services.data_structures import (
    StrategyConfig,
    SimulationParams,
    TradeLog,
    RiskLevels,
)
from app.services.condition_evaluator import evaluate_group
from app.services.risk_manager import compute_risk_levels, update_trailing_sl


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_MAX_BARS = 200


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _bar_time(df: pd.DataFrame, idx: int) -> str:
    """bar[idx] のタイムスタンプを ISO 8601 UTC 文字列で返す。
    get_candles() は timestamp をカラムとして返す（インデックスは整数）ため
    カラムを優先し、なければインデックスにフォールバックする。
    """
    if "timestamp" in df.columns:
        ts = df["timestamp"].iloc[idx]
    else:
        ts = df.index[idx]
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _open_price(df: pd.DataFrame, idx: int) -> float:
    return float(df["open"].iloc[idx])


# ---------------------------------------------------------------------------
# 1トレードのシミュレーション（エントリー後の足をスキャン）
# ---------------------------------------------------------------------------

def _simulate_trade(
    df: pd.DataFrame,
    direction: Literal["BUY", "SELL"],
    entry_bar_index: int,
    risk: RiskLevels,
    trailing_config,
    max_bars_to_exit: int,
    entry_reasons: List[str],
    pip_value: float,
    initial_capital: float,
    running_capital: float,
) -> TradeLog:
    """
    エントリー足 entry_bar_index から SL/TP を監視してトレードを完結させる。

    約定ルール3準拠: チェックは entry_bar_index+1 から開始。
    """
    entry_price = _open_price(df, entry_bar_index)
    entry_time = _bar_time(df, entry_bar_index)

    current_sl = risk["sl_price"]
    tp_price = risk["tp_price"]

    exit_bar_index = None
    exit_price = None
    exit_reason = None

    scan_end = min(entry_bar_index + max_bars_to_exit + 1, len(df))

    for j in range(entry_bar_index + 1, scan_end):
        bar_high = float(df["high"].iloc[j])
        bar_low = float(df["low"].iloc[j])

        # トレーリングストップ更新（今足の SL/TP 判定前に更新）
        if trailing_config.get("enabled"):
            current_sl = update_trailing_sl(
                trailing_config, current_sl, direction, bar_high, bar_low
            )

        if direction == "BUY":
            sl_hit = bar_low <= current_sl
            tp_hit = bar_high >= tp_price
        else:
            sl_hit = bar_high >= current_sl
            tp_hit = bar_low <= tp_price

        if sl_hit or tp_hit:
            exit_bar_index = j
            # 約定ルール4: 同一足で両方到達 → SL 優先
            if sl_hit and tp_hit:
                exit_price = current_sl
                exit_reason = "TRAILING_SL" if trailing_config.get("enabled") else "SL"
            elif sl_hit:
                exit_price = current_sl
                exit_reason = "TRAILING_SL" if trailing_config.get("enabled") else "SL"
            else:
                exit_price = tp_price
                exit_reason = "TP"
            break

    # TP/SL 未到達 → 最終足で決済
    if exit_bar_index is None:
        exit_bar_index = scan_end - 1
        exit_price = _open_price(df, exit_bar_index)
        exit_reason = "END_OF_DATA"

    exit_time = _bar_time(df, exit_bar_index)

    # PnL 計算
    if direction == "BUY":
        pnl_pips = (exit_price - entry_price) / 0.01
    else:
        pnl_pips = (entry_price - exit_price) / 0.01

    pnl_currency = pnl_pips * pip_value
    running_capital = running_capital + pnl_currency

    return TradeLog(
        trade_id=str(uuid.uuid4()),
        direction=direction,
        entry_bar_index=entry_bar_index,
        exit_bar_index=exit_bar_index,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=round(entry_price, 5),
        exit_price=round(exit_price, 5),
        sl_price=round(current_sl, 5),
        tp_price=round(tp_price, 5),
        pnl_pips=round(pnl_pips, 2),
        pnl_currency=round(pnl_currency, 2),
        running_capital=round(running_capital, 2),
        exit_reason=exit_reason,
        entry_reasons=entry_reasons,
    )


# ---------------------------------------------------------------------------
# メインエントリーポイント
# ---------------------------------------------------------------------------

def run_backtest(
    df: pd.DataFrame,
    strategy_config: StrategyConfig,
    sim_params: SimulationParams,
) -> List[TradeLog]:
    """
    ストラテジー設定とシミュレーションパラメータに基づいてバックテストを実行する。

    Parameters
    ----------
    df               : OHLCV DataFrame（インデックスは datetime）
    strategy_config  : StrategyConfig
    sim_params       : SimulationParams

    Returns
    -------
    List[TradeLog] — 全トレードログ（END_OF_DATA 含む）
    """
    if df.empty or len(df) < 2:
        return []

    direction = strategy_config["direction"]
    entry_conditions = strategy_config["entry_conditions"]
    filters = strategy_config.get("filters")
    sl_config = strategy_config["sl_config"]
    tp_config = strategy_config["tp_config"]
    trailing_config = strategy_config["trailing_config"]

    pip_value = sim_params["pip_value"]
    max_bars = sim_params.get("max_bars_to_exit", _DEFAULT_MAX_BARS)
    running_capital = sim_params["initial_capital"]

    trades: List[TradeLog] = []

    # skip_until: このインデックス以前の足はシグナル評価しない
    skip_until: int = -1

    n = len(df)

    # bar[i] の open でエントリーするか判断するため、
    # シグナル評価は bar[i-1]（確定足）で行う。
    # ループは i=1 から開始（i-1 が存在する最小インデックス）。
    for i in range(1, n):
        # オープントレード中はスキップ
        if i <= skip_until:
            continue

        signal_idx = i - 1  # 確定足

        # --- エントリー方向ごとに評価 ---
        directions_to_check: List[Literal["BUY", "SELL"]] = []
        if direction in ("BUY", "BOTH"):
            directions_to_check.append("BUY")
        if direction in ("SELL", "BOTH"):
            directions_to_check.append("SELL")

        for trade_dir in directions_to_check:
            # エントリー条件評価
            entry_ok, matched_ids = evaluate_group(entry_conditions, df, signal_idx)
            if not entry_ok:
                continue

            # フィルター評価（設定がある場合）
            if filters is not None:
                filter_ok, _ = evaluate_group(filters, df, signal_idx)
                if not filter_ok:
                    continue

            # エントリー: bar[i].open
            entry_bar = i

            # SL/TP 計算
            risk = compute_risk_levels(
                sl_config, tp_config, trade_dir,
                float(df["open"].iloc[entry_bar]),
                df, entry_bar,
            )

            # トレードシミュレーション
            trade = _simulate_trade(
                df=df,
                direction=trade_dir,
                entry_bar_index=entry_bar,
                risk=risk,
                trailing_config=trailing_config,
                max_bars_to_exit=max_bars,
                entry_reasons=matched_ids,
                pip_value=pip_value,
                initial_capital=sim_params["initial_capital"],
                running_capital=running_capital,
            )

            trades.append(trade)
            running_capital = trade["running_capital"]

            # 次のシグナル評価はトレード決済後から
            skip_until = trade["exit_bar_index"]

            # 1本の確定足につき1方向のみエントリー（BOTH でも BUY/SELL どちらか）
            break

    return trades
