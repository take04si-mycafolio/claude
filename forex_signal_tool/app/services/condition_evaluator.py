"""
condition_evaluator.py — Phase 1 条件評価エンジン

StrategyCondition / ConditionGroup を DataFrame の特定インデックスに対して評価する。

約定ルール（Rule 1）準拠:
  シグナル判定は確定足ベース。
  bar[i] を評価する際は bar[i-1] までの系列を使用する。
  呼び出し側が i を「比較したい直前の確定足インデックス」として渡すこと。
  例: ループが bar[i] の open でエントリーするか判断する時は
      evaluate_group(group, df, i-1) を呼ぶ。

crosses_above / crosses_below 判定:
  インデックス idx と idx-1 の2点を比較する。
  idx == 0 の場合はクロスなしとして False を返す。
"""

from __future__ import annotations

from typing import List

import pandas as pd
import numpy as np

from app.services.data_structures import StrategyCondition, ConditionGroup
from app.services.indicators.compute import compute_series


# ---------------------------------------------------------------------------
# 単一条件の評価
# ---------------------------------------------------------------------------

def evaluate_condition(cond: StrategyCondition, df: pd.DataFrame, idx: int) -> bool:
    """
    単一の StrategyCondition を df[idx] の時点で評価する。

    Parameters
    ----------
    cond : StrategyCondition
    df   : pd.DataFrame — 全系列（全長で指標を計算するため）
    idx  : int          — 評価対象インデックス（確定足）

    Returns
    -------
    bool
    """
    comparison = cond["comparison"]

    # 自指標の現在値（idx）を取得
    indicator_series = compute_series(cond["indicator"], cond["params"], df)

    if idx < 0 or idx >= len(indicator_series):
        return False

    current_val = indicator_series.iloc[idx]
    if pd.isna(current_val):
        return False

    # スカラー比較
    if comparison in ("less_than", "greater_than", "less_than_or_equal",
                      "greater_than_or_equal", "equals"):
        threshold = cond["value"]
        if threshold is None:
            return False
        if comparison == "less_than":
            return float(current_val) < float(threshold)
        if comparison == "greater_than":
            return float(current_val) > float(threshold)
        if comparison == "less_than_or_equal":
            return float(current_val) <= float(threshold)
        if comparison == "greater_than_or_equal":
            return float(current_val) >= float(threshold)
        if comparison == "equals":
            return float(current_val) == float(threshold)

    # クロス比較（compare_to_indicator が必要）
    if comparison in ("crosses_above", "crosses_below"):
        if idx == 0:
            return False  # 前足がないためクロス判定不可

        compare_ind = cond.get("compare_to_indicator")
        compare_params = cond.get("compare_to_params")

        if compare_ind is not None:
            # インジケーター vs インジケーター
            compare_series = compute_series(compare_ind, compare_params, df)
            compare_current = compare_series.iloc[idx]
            compare_prev = compare_series.iloc[idx - 1]
        elif cond.get("value") is not None:
            # インジケーター vs スカラー値（固定閾値クロス）
            threshold = float(cond["value"])
            compare_current = threshold
            compare_prev = threshold
        else:
            return False

        prev_val = indicator_series.iloc[idx - 1]
        if pd.isna(prev_val) or pd.isna(compare_current) or pd.isna(compare_prev):
            return False

        if comparison == "crosses_above":
            # 前足 ≤ 比較対象 かつ 現足 > 比較対象
            return float(prev_val) <= float(compare_prev) and float(current_val) > float(compare_current)
        if comparison == "crosses_below":
            # 前足 ≥ 比較対象 かつ 現足 < 比較対象
            return float(prev_val) >= float(compare_prev) and float(current_val) < float(compare_current)

    return False  # 未知の comparison


# ---------------------------------------------------------------------------
# グループ評価（AND / OR）
# ---------------------------------------------------------------------------

def evaluate_group(group: ConditionGroup, df: pd.DataFrame, idx: int) -> tuple[bool, List[str]]:
    """
    ConditionGroup を評価し、(result: bool, matched_ids: List[str]) を返す。

    matched_ids は真になった条件の id リスト。
    AND の場合: 全条件が True のときのみ matched_ids に全条件 id が入る。
    OR  の場合: 少なくとも1条件が True のとき True になった条件 id が入る。

    Parameters
    ----------
    group : ConditionGroup
    df    : pd.DataFrame
    idx   : int — 評価対象インデックス（確定足）

    Returns
    -------
    (bool, List[str])
    """
    logic = group["logic"]
    conditions: List[StrategyCondition] = group["conditions"]

    results = [(cond["id"], evaluate_condition(cond, df, idx)) for cond in conditions]
    true_ids = [cid for cid, ok in results if ok]

    if logic == "AND":
        passed = len(true_ids) == len(conditions)
        return passed, (true_ids if passed else [])

    if logic == "OR":
        passed = len(true_ids) > 0
        return passed, (true_ids if passed else [])

    return False, []
