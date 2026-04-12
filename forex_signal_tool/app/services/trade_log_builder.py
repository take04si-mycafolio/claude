"""
trade_log_builder.py — Phase 1 チャート表示データ生成

List[TradeLog] → TradeMarker / ConnectingLine に変換する。
Lightweight Charts の series.setMarkers() / カスタム描画で使用。
"""

from __future__ import annotations

from typing import List

from app.services.data_structures import TradeLog, TradeMarker, ConnectingLine


# ---------------------------------------------------------------------------
# カラーパレット
# ---------------------------------------------------------------------------

_COLOR_TP    = "#22c55e"   # green  — TP 決済
_COLOR_SL    = "#ef4444"   # red    — SL / TRAILING_SL 決済
_COLOR_EOD   = "#94a3b8"   # gray   — END_OF_DATA

_COLOR_BUY_ENTRY  = "#3b82f6"  # blue
_COLOR_SELL_ENTRY = "#f97316"  # orange


def _exit_color(exit_reason: str) -> str:
    if exit_reason == "TP":
        return _COLOR_TP
    if exit_reason in ("SL", "TRAILING_SL"):
        return _COLOR_SL
    return _COLOR_EOD


def _exit_text(trade: TradeLog) -> str:
    reason_label = {
        "TP":          "TP",
        "SL":          "SL",
        "TRAILING_SL": "TSL",
        "END_OF_DATA": "EOD",
    }.get(trade["exit_reason"], trade["exit_reason"])

    pnl_sign = "+" if trade["pnl_pips"] >= 0 else ""
    return f"{reason_label} {pnl_sign}{trade['pnl_pips']:.1f}p"


# ---------------------------------------------------------------------------
# TradeMarker 生成
# ---------------------------------------------------------------------------

def build_trade_markers(trades: List[TradeLog]) -> List[TradeMarker]:
    """
    各トレードに対してエントリー・エグジットのマーカーを生成する。
    END_OF_DATA トレードも含める（グレー表示）。

    Returns
    -------
    List[TradeMarker] — entry marker → exit marker の順で並ぶ
    """
    markers: List[TradeMarker] = []

    for trade in trades:
        # --- エントリーマーカー ---
        if trade["direction"] == "BUY":
            entry_marker = TradeMarker(
                time=trade["entry_time"],
                position="belowBar",
                color=_COLOR_BUY_ENTRY,
                shape="arrowUp",
                text=f"BUY {trade['entry_price']:.3f}",
                trade_id=trade["trade_id"],
            )
        else:
            entry_marker = TradeMarker(
                time=trade["entry_time"],
                position="aboveBar",
                color=_COLOR_SELL_ENTRY,
                shape="arrowDown",
                text=f"SELL {trade['entry_price']:.3f}",
                trade_id=trade["trade_id"],
            )
        markers.append(entry_marker)

        # --- エグジットマーカー ---
        exit_color = _exit_color(trade["exit_reason"])
        if trade["direction"] == "BUY":
            exit_marker = TradeMarker(
                time=trade["exit_time"],
                position="aboveBar",
                color=exit_color,
                shape="circle",
                text=_exit_text(trade),
                trade_id=trade["trade_id"],
            )
        else:
            exit_marker = TradeMarker(
                time=trade["exit_time"],
                position="belowBar",
                color=exit_color,
                shape="circle",
                text=_exit_text(trade),
                trade_id=trade["trade_id"],
            )
        markers.append(exit_marker)

    return markers


# ---------------------------------------------------------------------------
# ConnectingLine 生成
# ---------------------------------------------------------------------------

def build_connecting_lines(trades: List[TradeLog]) -> List[ConnectingLine]:
    """
    各トレードのエントリー〜エグジットを結ぶ ConnectingLine を生成する。

    Returns
    -------
    List[ConnectingLine]
    """
    return [
        ConnectingLine(
            trade_id=trade["trade_id"],
            entry_time=trade["entry_time"],
            exit_time=trade["exit_time"],
            entry_price=trade["entry_price"],
            exit_price=trade["exit_price"],
            direction=trade["direction"],
            exit_reason=trade["exit_reason"],
            pnl_pips=trade["pnl_pips"],
        )
        for trade in trades
    ]


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def build_chart_data(trades: List[TradeLog]) -> dict:
    """
    バックテスト結果をチャート表示用の辞書にまとめて返す。

    Returns
    -------
    {
        "markers": List[TradeMarker],
        "lines":   List[ConnectingLine],
    }
    """
    return {
        "markers": build_trade_markers(trades),
        "lines":   build_connecting_lines(trades),
    }
