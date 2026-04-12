"""
data_structures.py — Phase 1 共有型定義

全サービスモジュール（conditionEvaluator / riskManager / backtestEngine /
metricsCalculator / tradeLogBuilder）がここからインポートする。
循環インポートを防ぐため、このファイル自体は他のサービスを一切インポートしない。

==========================================================================
約定ルール（EXECUTION RULES） — フェーズ1 共通仕様
==========================================================================
1. シグナル判定は確定足ベース
       indicator_func は bar[i-1] までの window で計算する。
       未確定足（bar[i]）のデータはシグナル判定に使わない。

2. エントリーは次足始値
       シグナルが確定した bar[i-1] の次、bar[i] の open 価格でエントリーする。
       これにより look-ahead bias を排除する。

3. SL/TP 判定は エントリー成立後の足から開始
       bar[i] でエントリーが成立した場合、SL/TP のヒット判定は bar[i+1] 以降で行う。
       エントリー同一足での即時決済は発生しない。

4. 同一足で SL/TP 両到達時は不利側優先（保守的約定）
       同一 bar の high が TP に、low が SL に同時到達する場合、
       損失側（SL ヒット = LOSS）を優先して約定扱いとする。
       どちらが実際に先に到達したかは不明なため、保守的な判定を採用する。
==========================================================================
"""

from __future__ import annotations

from typing import List, Literal, Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# 条件層 (Condition Layer)
# ---------------------------------------------------------------------------

class StrategyCondition(TypedDict):
    """
    単一のテクニカル条件。

    例 — RSI < 30:
        {
            "id": "c1",
            "indicator": "RSI",
            "params": {"period": 14},
            "comparison": "less_than",
            "value": 30.0,
            "compare_to_indicator": None,
            "compare_to_params": None,
        }

    例 — EMA9 が EMA21 を上抜け（クロス検出）:
        {
            "id": "c2",
            "indicator": "EMA",
            "params": {"period": 9},
            "comparison": "crosses_above",
            "value": None,
            "compare_to_indicator": "EMA",
            "compare_to_params": {"period": 21},
        }
    """
    id: str
    indicator: str                            # "RSI" / "EMA" / "SMA" / "MACD_HIST" など
    params: dict                              # {"period": 14} など指標パラメータ
    comparison: Literal[
        "less_than",                          # value より小さい
        "greater_than",                       # value より大きい
        "less_than_or_equal",                 # value 以下
        "greater_than_or_equal",              # value 以上
        "crosses_above",                      # 前足≤比較対象かつ現足>比較対象
        "crosses_below",                      # 前足≥比較対象かつ現足<比較対象
        "equals",                             # 等値（浮動小数には非推奨）
    ]
    value: Optional[float]                    # スカラー比較値。crosses_* の場合は None
    compare_to_indicator: Optional[str]       # クロス比較先指標名。スカラー比較の場合は None
    compare_to_params: Optional[dict]         # 比較先指標のパラメータ


class ConditionGroup(TypedDict):
    """
    複数の StrategyCondition を AND / OR で束ねたグループ。
    ネストは将来拡張用の余地として設計上許容するが、Phase 1 ではフラットな1階層のみ対応。
    """
    logic: Literal["AND", "OR"]
    conditions: List[StrategyCondition]


# ---------------------------------------------------------------------------
# リスク管理層 (Risk Management Layer)
# ---------------------------------------------------------------------------

class StopLossConfig(TypedDict):
    """
    損切り設定。type によって使用するフィールドが異なる。

    type == "fixed"          → pips を使用
    type == "recentHighLow"  → lookback_bars, buffer_pips を使用
                               買い: 直近 lookback_bars 本の安値 − buffer_pips
                               売り: 直近 lookback_bars 本の高値 + buffer_pips
    type == "atr"            → atr_period, atr_multiplier を使用
                               SL距離 = ATR(atr_period) × atr_multiplier
    """
    type: Literal["fixed", "recentHighLow", "atr"]
    pips: Optional[float]                     # fixed 用
    lookback_bars: Optional[int]              # recentHighLow 用
    buffer_pips: Optional[float]              # recentHighLow 用
    atr_period: Optional[int]                 # atr 用
    atr_multiplier: Optional[float]           # atr 用


class TakeProfitConfig(TypedDict):
    """
    利確設定。type によって使用するフィールドが異なる。

    type == "fixed"  → pips を使用
    type == "rr"     → rr_ratio を使用（SL距離 × rr_ratio = TP距離）
    type == "atr"    → atr_period, atr_multiplier を使用
    """
    type: Literal["fixed", "rr", "atr"]
    pips: Optional[float]                     # fixed 用
    rr_ratio: Optional[float]                 # rr 用（例: 2.0 → SLの2倍の利確幅）
    atr_period: Optional[int]                 # atr 用
    atr_multiplier: Optional[float]           # atr 用


class TrailingStopConfig(TypedDict):
    """
    トレーリングストップ設定。

    enabled == False の場合、他フィールドは無視される。
    Phase 1 では type == "fixedTrailing" のみ対応。
    trail_pips: 価格が有利方向に動いた際に SL を何pips 後方に追従させるか。
    """
    enabled: bool
    type: Optional[Literal["fixedTrailing"]]  # Phase 1 は fixedTrailing のみ
    trail_pips: Optional[float]


class RiskLevels(TypedDict):
    """
    riskManager が計算した具体的なSL/TP価格。
    エントリー時点で確定し、トレード中は trailing_stop により SL のみ更新される。
    """
    sl_price: float
    tp_price: float
    sl_pips: float                            # 参照用（決済理由ログに使用）
    tp_pips: float                            # 参照用


# ---------------------------------------------------------------------------
# エンジン層 (Engine Layer)
# ---------------------------------------------------------------------------

class StrategyConfig(TypedDict):
    """
    バックテスト戦略の完全な定義。

    strategy_version: 後方互換制御のためのバージョン識別子。
        Phase 1 では "1.0" を使用する。
        将来スキーマが変わった場合に "2.0" 等へ更新し、
        デシリアライズ側でバージョン分岐できるようにする。
    direction: エントリー方向。"BOTH" の場合は BUY/SELL 両方のシグナルを評価する。
    filters: Optional。指定した場合は entry_conditions AND filters の両方が True
             のときのみエントリー可能とする。
    """
    strategy_version: str                     # "1.0" (Phase 1)
    direction: Literal["BUY", "SELL", "BOTH"]
    entry_conditions: ConditionGroup
    filters: Optional[ConditionGroup]
    sl_config: StopLossConfig
    tp_config: TakeProfitConfig
    trailing_config: TrailingStopConfig


class SimulationParams(TypedDict):
    """
    backtestEngine に渡すシミュレーション実行パラメータ。
    戦略の「何を」ではなく「どの条件で走らせるか」を定義する。
    """
    pair: str                                 # "USDJPY" / "GBPJPY" / "EURJPY"
    timeframe: str                            # "5min" / "15min" / "1hr" / "4hr" / "daily"
    initial_capital: float                    # 初期資金（円）
    lot_size: float                           # ロット数（pip_value 計算に使用）
    pip_value: float                          # 1pip の円換算額（lot_size 込み）
    max_bars_to_exit: int                     # TP/SL 未到達時の最大保有バー数（デフォルト200）


# ---------------------------------------------------------------------------
# 出力層 (Output Layer)
# ---------------------------------------------------------------------------

class TradeLog(TypedDict):
    """
    1トレードの完全なログ。backtestEngine が生成し、
    metricsCalculator と tradeLogBuilder が消費する。

    約定ルール準拠:
    - entry_price は entry_bar_index の open（次足始値）
    - sl/tp チェックは entry_bar_index+1 以降
    - exit_reason "SL" は同一足 SL/TP 競合時も含む（保守的約定）
    """
    trade_id: str                             # UUID v4 文字列
    direction: Literal["BUY", "SELL"]
    entry_bar_index: int                      # df上のバーインデックス（約定足）
    exit_bar_index: int                       # df上のバーインデックス（決済足）
    entry_time: str                           # ISO 8601 (UTC)
    exit_time: str                            # ISO 8601 (UTC)
    entry_price: float                        # 次足始値（約定ルール②）
    exit_price: float                         # 実際の決済価格（SL/TP価格）
    sl_price: float
    tp_price: float
    pnl_pips: float                           # 正=利益、負=損失
    pnl_currency: float                       # 円換算（pip_value 使用）
    running_capital: float                    # このトレード後の資産残高
    exit_reason: Literal[
        "TP",                                 # テイクプロフィット到達
        "SL",                                 # ストップロス到達（同一足競合含む）
        "TRAILING_SL",                        # トレーリングストップ到達
        "END_OF_DATA",                        # データ終端で未決済（集計除外）
    ]
    entry_reasons: List[str]                  # 条件IDリスト（例: ["c1", "c2"]）


class BacktestMetrics(TypedDict):
    """
    metricsCalculator が List[TradeLog] から算出する全指標。
    Phase 1 では DB 保存は行わず、API レスポンスとして返すのみ。

    定義:
    - profit_factor   = gross_profit_pips / gross_loss_pips（損失0時は inf）
    - expectancy_pips = (win_rate × avg_win_pips) − ((1−win_rate) × avg_loss_pips)
    - max_drawdown_pips = equity curve（pips累積）のピーク→谷の最大下落幅
    - avg_rr          = avg_win_pips / avg_loss_pips（損失0時は inf）
    """
    # --- 基本指標 ---
    total_trades: int
    wins: int
    losses: int
    win_rate: float                           # 0.0〜1.0
    gross_profit_pips: float
    gross_loss_pips: float                    # 正値（損失の絶対値合計）
    net_profit_pips: float
    profit_factor: float
    max_drawdown_pips: float
    avg_win_pips: float
    avg_loss_pips: float                      # 正値
    avg_rr: float                             # 平均リスクリワード比
    expectancy_pips: float

    # --- 追加指標 ---
    max_win_streak: int
    max_loss_streak: int
    avg_holding_bars: float
    long_trades: int
    short_trades: int
    long_wins: int
    short_wins: int
    long_win_rate: float                      # 0.0〜1.0（ロングトレードが0件なら 0.0）
    short_win_rate: float                     # 0.0〜1.0


# ---------------------------------------------------------------------------
# チャート表示層 (Chart Layer)
# ---------------------------------------------------------------------------

class TradeMarker(TypedDict):
    """
    Lightweight Charts の series.setMarkers() に渡す1マーカー分のデータ。
    tradeLogBuilder が TradeLog → TradeMarker に変換する。
    """
    time: str                                 # "YYYY-MM-DD HH:MM" (UTC)
    position: Literal["aboveBar", "belowBar"]
    color: str                                # CSS color string
    shape: Literal["arrowUp", "arrowDown", "circle", "square"]
    text: str                                 # ホバー表示テキスト
    trade_id: str                             # TradeLog.trade_id との紐付け用


class ConnectingLine(TypedDict):
    """
    エントリー〜決済を結ぶラインの座標。
    Lightweight Charts の ISeriesApi でカスタム描画に使用。
    """
    trade_id: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    direction: Literal["BUY", "SELL"]
    exit_reason: Literal["TP", "SL", "TRAILING_SL", "END_OF_DATA"]
    pnl_pips: float
