#!/usr/bin/env python3
"""
run_backtest_v2.py — Phase 1 マルチ条件バックテスト CLI スクリプト

PHP admin/api.php の exec() から同期呼び出しされる。
引数: <params_json_file_path>
標準出力: JSON 結果（改行なし）
"""

import sys
import os
import json
import math
import traceback

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def _safe(v):
    """float の inf/nan を None に変換（JSON シリアライズ用）"""
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return None
    return v


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "使い方: run_backtest_v2.py <params_file>"}))
        return

    # パラメータ読み込み
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            body = json.load(f)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"パラメータ読み込みエラー: {e}"}))
        return

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from app.services.data_fetcher import get_candles
            from app.services.backtest_engine import run_backtest
            from app.services.metrics_calculator import calculate_metrics
            from app.services.trade_log_builder import build_chart_data
            from app.config import Config

            pair      = body.get("pair", "USDJPY")
            timeframe = body.get("timeframe", "1hr")
            limit     = int(body.get("limit", 500))
            strategy  = body.get("strategy_config")
            sim_raw   = body.get("sim_params") or {}

            # バリデーション
            if pair not in Config.CURRENCY_PAIRS:
                print(json.dumps({"ok": False, "error": f"無効な通貨ペア: {pair}"}))
                return
            if timeframe not in Config.TIMEFRAMES:
                print(json.dumps({"ok": False, "error": f"無効なタイムフレーム: {timeframe}"}))
                return
            if not strategy:
                print(json.dumps({"ok": False, "error": "strategy_config が必要です"}))
                return
            if strategy.get("strategy_version", "") != "1.0":
                print(json.dumps({"ok": False, "error": "strategy_version は '1.0' にしてください"}))
                return

            sim_params = {
                "pair":              pair,
                "timeframe":         timeframe,
                "initial_capital":   float(sim_raw.get("initial_capital", 1_000_000)),
                "lot_size":          float(sim_raw.get("lot_size",         1.0)),
                "pip_value":         float(sim_raw.get("pip_value",        1_000.0)),
                "max_bars_to_exit":  int(sim_raw.get("max_bars_to_exit",   200)),
            }

            # データ取得
            df = get_candles(pair, timeframe, limit=limit)
            if df is None or df.empty:
                print(json.dumps({"ok": False, "error": "OHLCVデータが取得できません"}))
                return

            # チャート用 OHLCV リスト（datetime index → ISO 文字列）
            ohlcv = []
            for i, ts in enumerate(df.index):
                t = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                ohlcv.append({
                    "timestamp": t,
                    "open":  float(df["open"].iloc[i]),
                    "high":  float(df["high"].iloc[i]),
                    "low":   float(df["low"].iloc[i]),
                    "close": float(df["close"].iloc[i]),
                })

            # バックテスト実行
            trades   = run_backtest(df, strategy, sim_params)
            metrics  = calculate_metrics(trades)
            chart_data = build_chart_data(trades)

            metrics_safe = {k: _safe(v) for k, v in metrics.items()}

            result = {
                "ok":         True,
                "pair":       pair,
                "timeframe":  timeframe,
                "bars_used":  len(df),
                "metrics":    metrics_safe,
                "trades":     trades,
                "chart_data": chart_data,
                "ohlcv":      ohlcv,
            }
            print(json.dumps(result, ensure_ascii=False, default=str))

    except Exception as e:
        print(json.dumps({
            "ok":     False,
            "error":  str(e),
            "detail": traceback.format_exc(),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
