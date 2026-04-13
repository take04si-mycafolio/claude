#!/usr/bin/env python3
"""
run_optimize.py — グリッドサーチ最適化 CLI スクリプト

PHP admin/api.php の exec() から同期呼び出しされる。
引数: <params_json_file_path>
標準出力: JSON 結果（改行なし）

optimize_config 仕様:
  {
    "target_conditions": [
      {"condition_id": "c1", "param": "period", "range": [5, 30], "step": 5},
      {"condition_id": "c2", "param": "period", "range": [10, 100], "step": 10}
    ],
    "objective":  "profit_factor",   # profit_factor / win_rate / expectancy_pips / net_profit_pips
    "top_n":      20,
    "max_combos": 200                # 上限超過時はエラーで返す
  }
"""

import sys
import os
import json
import math
import copy
import itertools
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


def _sort_val(v):
    """ソート用スカラー変換（None/inf → 境界値）"""
    if v is None:
        return -9999.0
    if math.isinf(v):
        return 9999.0
    if math.isnan(v):
        return -9999.0
    return float(v)


def _make_range(r_min, r_max, step):
    """[r_min, r_max] を step 刻みでリスト化（両端含む）"""
    step = max(step, 1e-9)
    vals = []
    v = float(r_min)
    while v <= float(r_max) + 1e-9:
        vals.append(round(v, 8))
        v += step
    return vals


def _apply_param(strategy, condition_id, param_name, value):
    """strategy_config 内の condition を指定パラメータで更新（破壊的）"""
    for cond in strategy["entry_conditions"]["conditions"]:
        if cond["id"] == condition_id:
            cond["params"][param_name] = value
    if strategy.get("filters"):
        for cond in strategy["filters"]["conditions"]:
            if cond["id"] == condition_id:
                cond["params"][param_name] = value


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Usage: run_optimize.py <params_file>"}))
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
            from app.config import Config

            pair      = body.get("pair", "USDJPY")
            timeframe = body.get("timeframe", "1hr")
            limit     = int(body.get("limit", 500))
            strategy  = body.get("strategy_config")
            sim_raw   = body.get("sim_params") or {}
            opt_cfg   = body.get("optimize_config") or {}

            # バリデーション
            if pair not in Config.CURRENCY_PAIRS:
                print(json.dumps({"ok": False, "error": f"無効な通貨ペア: {pair}"}))
                return
            if not strategy:
                print(json.dumps({"ok": False, "error": "strategy_config が必要です"}))
                return
            if strategy.get("strategy_version", "") != "1.0":
                print(json.dumps({"ok": False, "error": "strategy_version は '1.0' にしてください"}))
                return

            targets   = opt_cfg.get("target_conditions", [])
            objective = opt_cfg.get("objective", "profit_factor")
            top_n     = int(opt_cfg.get("top_n", 20))
            max_combos = int(opt_cfg.get("max_combos", 200))

            if not targets:
                print(json.dumps({"ok": False, "error": "optimize_config.target_conditions が必要です"}))
                return

            sim_params = {
                "pair":              pair,
                "timeframe":         timeframe,
                "initial_capital":   float(sim_raw.get("initial_capital", 1_000_000)),
                "lot_size":          float(sim_raw.get("lot_size",         1.0)),
                "pip_value":         float(sim_raw.get("pip_value",        1_000.0)),
                "max_bars_to_exit":  int(sim_raw.get("max_bars_to_exit",   200)),
            }

            # グリッド構築
            axes = []
            for t in targets:
                r = t.get("range", [5, 30])
                vals = _make_range(float(r[0]), float(r[1]), float(t.get("step", 1)))
                axes.append((t["condition_id"], t["param"], vals))

            total = 1
            for _, _, vals in axes:
                total *= len(vals)

            if total > max_combos:
                print(json.dumps({
                    "ok": False,
                    "error": f"組み合わせ数が多すぎます ({total} 件)。"
                             f"レンジを絞るか step を大きくしてください（上限 {max_combos} 件）",
                }))
                return

            # データ取得（1回のみ）
            df = get_candles(pair, timeframe, limit=limit)
            if df is None or df.empty:
                print(json.dumps({"ok": False, "error": "OHLCVデータが取得できません"}))
                return

            # グリッドサーチ
            results = []
            for combo in itertools.product(*[v for _, _, v in axes]):
                strat = copy.deepcopy(strategy)
                combo_desc = {}
                for (cond_id, param_name, _), val in zip(axes, combo):
                    label = f"{cond_id}.{param_name}"
                    combo_desc[label] = int(val) if float(val) == int(val) else val
                    _apply_param(strat, cond_id, param_name, val)

                try:
                    trades  = run_backtest(df, strat, sim_params)
                    metrics = calculate_metrics(trades)
                except Exception:
                    continue

                obj_raw = metrics.get(objective)
                results.append({
                    "params":          combo_desc,
                    "total_trades":    metrics.get("total_trades", 0),
                    "win_rate":        _safe(metrics.get("win_rate")),
                    "profit_factor":   _safe(metrics.get("profit_factor")),
                    "expectancy_pips": _safe(metrics.get("expectancy_pips")),
                    "net_profit_pips": _safe(metrics.get("net_profit_pips")),
                    "max_drawdown_pips": _safe(metrics.get("max_drawdown_pips")),
                    "_sv": _sort_val(obj_raw),
                })

            results.sort(key=lambda x: x["_sv"], reverse=True)
            for r in results:
                del r["_sv"]

            print(json.dumps({
                "ok":                True,
                "pair":              pair,
                "timeframe":         timeframe,
                "bars_used":         len(df),
                "objective":         objective,
                "total_combinations": total,
                "results":           results[:top_n],
            }, ensure_ascii=False, default=str))

    except Exception as e:
        print(json.dumps({
            "ok":     False,
            "error":  str(e),
            "detail": traceback.format_exc(),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
