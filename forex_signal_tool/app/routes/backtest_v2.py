"""
backtest_v2.py — Phase 1 マルチ条件バックテスト API Blueprint

エンドポイント:
  POST /api/v2/backtest

リクエスト JSON:
  {
    "pair":            "USDJPY",           // Config.CURRENCY_PAIRS のいずれか
    "timeframe":       "1hr",              // Config.TIMEFRAMES のいずれか
    "limit":           500,                // 取得バー数（デフォルト 500）
    "strategy_config": { ... },            // StrategyConfig (data_structures.py)
    "sim_params": {
      "initial_capital": 1000000,
      "lot_size":        1.0,
      "pip_value":       1000,
      "max_bars_to_exit": 200
    }
  }

レスポンス JSON:
  {
    "ok":         true,
    "pair":       "USDJPY",
    "timeframe":  "1hr",
    "bars_used":  480,
    "metrics":    { ... BacktestMetrics ... },
    "trades":     [ ... List[TradeLog] ... ],
    "chart_data": {
      "markers": [ ... List[TradeMarker] ... ],
      "lines":   [ ... List[ConnectingLine] ... ]
    }
  }
"""

from __future__ import annotations

import math
from flask import Blueprint, jsonify, request

from app.config import Config

bp = Blueprint("backtest_v2", __name__)


@bp.route("/v2/backtest", methods=["POST"])
def run_backtest_v2():
    """Phase 1 マルチ条件バックテストを実行して結果を返す。"""
    try:
        return _run_backtest_v2_inner()
    except Exception as exc:
        import traceback
        return jsonify({"ok": False, "error": str(exc),
                        "detail": traceback.format_exc()}), 500


def _run_backtest_v2_inner():
    from app.services.data_fetcher import get_candles
    from app.services.backtest_engine import run_backtest
    from app.services.metrics_calculator import calculate_metrics
    from app.services.trade_log_builder import build_chart_data

    body = request.get_json(silent=True) or {}

    # ---- 入力バリデーション ----
    pair = body.get("pair", "")
    timeframe = body.get("timeframe", "")
    limit = int(body.get("limit", 500))
    strategy_config = body.get("strategy_config")
    sim_params_raw = body.get("sim_params", {})

    if pair not in Config.CURRENCY_PAIRS:
        return jsonify({"ok": False, "error": f"Invalid pair: {pair!r}"}), 400
    if timeframe not in Config.TIMEFRAMES:
        return jsonify({"ok": False, "error": f"Invalid timeframe: {timeframe!r}"}), 400
    if not strategy_config:
        return jsonify({"ok": False, "error": "strategy_config is required"}), 400

    # strategy_version チェック
    if strategy_config.get("strategy_version", "") != "1.0":
        return jsonify({
            "ok": False,
            "error": "strategy_config.strategy_version must be '1.0'"
        }), 400

    # sim_params の組み立て（デフォルト値付き）
    sim_params = {
        "pair":              pair,
        "timeframe":         timeframe,
        "initial_capital":   float(sim_params_raw.get("initial_capital", 1_000_000)),
        "lot_size":          float(sim_params_raw.get("lot_size",         1.0)),
        "pip_value":         float(sim_params_raw.get("pip_value",        1_000.0)),
        "max_bars_to_exit":  int(sim_params_raw.get("max_bars_to_exit",   200)),
    }

    # ---- データ取得 ----
    df = get_candles(pair, timeframe, limit=limit)
    if df is None or df.empty:
        return jsonify({"ok": False, "error": "No OHLCV data available"}), 500

    # ---- バックテスト実行 ----
    try:
        trades = run_backtest(df, strategy_config, sim_params)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    # ---- メトリクス計算 ----
    metrics = calculate_metrics(trades)

    # ---- チャートデータ生成 ----
    chart_data = build_chart_data(trades)

    # ---- JSON シリアライズ (inf → null) ----
    def _safe(v):
        if isinstance(v, float) and math.isinf(v):
            return None
        return v

    metrics_out = {k: _safe(v) for k, v in metrics.items()}

    return jsonify({
        "ok":         True,
        "pair":       pair,
        "timeframe":  timeframe,
        "bars_used":  len(df),
        "metrics":    metrics_out,
        "trades":     trades,
        "chart_data": chart_data,
    })
