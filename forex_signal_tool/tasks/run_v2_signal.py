#!/usr/bin/env python3
"""
run_v2_signal.py — v2戦略でリアルタイムシグナルを生成・DBに保存する

PHP admin/api.php の exec() から呼び出される（同期）。
引数: <params_json_file_path>
標準出力: JSON 結果（改行なし）

params_json 仕様:
  {
    "pair":            "USDJPY",
    "timeframe":       "1hr",
    "limit":           200,
    "strategy_config": {...},    # 直接渡す場合
    "strategy_id":     null,     # saved_strategies.id（strategy_config がない場合）
    "strategy_name":   "My Strategy",  # indicator_name に使用
    "win_rate":        0.55,     # バックテスト勝率 0-1（confidence_score 算出用）
    "total_trades":    42,       # バックテストのトレード数
  }

シグナル生成ロジック:
  - 最新確定足（len(df)-2）で entry_conditions + filters を評価
  - 条件成立 → trading_signals に BUY/SELL を upsert
  - 条件不成立 → 同名の既存アクティブシグナルを無効化
"""

import sys
import os
import json
import traceback
from datetime import datetime, timezone, timedelta

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# タイムフレーム別シグナル有効期限（時間）
TF_EXPIRY_HOURS = {
    "5min":  1,
    "15min": 2,
    "1hr":   6,
    "4hr":  24,
    "daily": 72,
}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Usage: run_v2_signal.py <params_file>"}))
        return

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
            import pandas as pd
            from app import db
            from app.services.data_fetcher import get_candles
            from app.services.condition_evaluator import evaluate_group
            from app.services.risk_manager import compute_risk_levels
            from app.models.signal import TradingSignal
            from app.config import Config

            pair           = body.get("pair", "USDJPY")
            timeframe      = body.get("timeframe", "1hr")
            limit          = int(body.get("limit", 200))
            strategy       = body.get("strategy_config")
            strategy_id    = body.get("strategy_id")
            strategy_name  = body.get("strategy_name") or "v2_strategy"
            win_rate_bt    = body.get("win_rate")       # float 0-1
            total_trades_bt= int(body.get("total_trades", 0))

            # strategy_id 指定時は DB から config を読み込む
            if strategy is None and strategy_id:
                from sqlalchemy import text
                row = db.session.execute(
                    text("SELECT name, config_json FROM saved_strategies WHERE id = :id"),
                    {"id": int(strategy_id)}
                ).fetchone()
                if row is None:
                    print(json.dumps({"ok": False, "error": f"戦略 id={strategy_id} が見つかりません"}))
                    return
                strategy_name = row[0]
                strategy      = json.loads(row[1])

            if not strategy:
                print(json.dumps({"ok": False, "error": "strategy_config または strategy_id が必要です"}))
                return
            if strategy.get("strategy_version", "") != "1.0":
                print(json.dumps({"ok": False, "error": "strategy_version は '1.0' にしてください"}))
                return
            if pair not in Config.CURRENCY_PAIRS:
                print(json.dumps({"ok": False, "error": f"無効な通貨ペア: {pair}"}))
                return

            # ローソク足取得
            df = get_candles(pair, timeframe, limit=limit)
            if df is None or df.empty or len(df) < 5:
                print(json.dumps({"ok": False, "error": "OHLCVデータが取得できません"}))
                return

            # 確定足インデックス = 最後から2番目（最後のバーは未確定）
            confirmed_idx = len(df) - 2

            # エントリー条件評価
            entry_group = strategy.get("entry_conditions")
            if not entry_group:
                print(json.dumps({"ok": False, "error": "strategy_config.entry_conditions が必要です"}))
                return

            passed, matched_ids = evaluate_group(entry_group, df, confirmed_idx)

            # フィルター評価
            filter_group  = strategy.get("filters")
            filter_passed = True
            if filter_group:
                filter_passed, _ = evaluate_group(filter_group, df, confirmed_idx)

            direction = strategy.get("direction", "BOTH")

            signal_type = None  # "BUY" / "SELL" / None
            if passed and filter_passed:
                if direction == "BUY":
                    signal_type = "BUY"
                elif direction == "SELL":
                    signal_type = "SELL"
                else:
                    # BOTH: 条件が AND 成立した場合は BUY として登録
                    # （実際は条件内に方向性が内包されていることが多い）
                    signal_type = "BUY"

            # 現在価格 = 最新確定足の終値
            current_price = float(df["close"].iloc[confirmed_idx])

            # signal_time = 最新確定足のタイムスタンプ（UTC）
            if "timestamp" in df.columns:
                sig_ts = df["timestamp"].iloc[confirmed_idx]
            else:
                sig_ts = df.index[confirmed_idx]

            if isinstance(sig_ts, pd.Timestamp):
                if sig_ts.tzinfo is None:
                    sig_ts = sig_ts.tz_localize("UTC")
                else:
                    sig_ts = sig_ts.tz_convert("UTC")
                sig_ts = sig_ts.to_pydatetime()
            else:
                sig_ts = datetime.now(timezone.utc)

            # SL/TP 計算（失敗しても続行）
            sl_price = tp_price = sl_pips = tp_pips = None
            try:
                sl_cfg  = strategy.get("sl_config") or {"type": "atr", "atr_period": 14, "atr_multiplier": 1.5}
                tp_cfg  = strategy.get("tp_config") or {"type": "rr", "rr_ratio": 2.0}
                risk = compute_risk_levels(
                    sl_cfg, tp_cfg,
                    signal_type or "BUY",
                    current_price,
                    df,
                    confirmed_idx + 1,  # entry_bar_index = 確定足の次（約定想定足）
                )
                sl_price = float(risk["sl"]) if risk.get("sl") else None
                tp_price = float(risk["tp"]) if risk.get("tp") else None
                sl_pips  = float(risk["sl_pips"]) if risk.get("sl_pips") else None
                tp_pips  = float(risk["tp_pips"]) if risk.get("tp_pips") else None
            except Exception:
                pass  # SL/TP 計算失敗でも登録は続行

            # 信頼度スコア計算（バックテスト勝率ベース）
            confidence = None
            if win_rate_bt is not None:
                wr_pct    = float(win_rate_bt) * 100
                base      = max(0.0, (wr_pct - 50.0) * 2)   # 50%=0, 100%=100
                sample    = min(10.0, float(total_trades_bt)) # 取引数ボーナス最大10
                confidence = round(min(100.0, base + sample), 1)

            expiry_hours = TF_EXPIRY_HOURS.get(timeframe, 6)
            expired_at   = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

            signal_id = None
            is_new    = False

            if signal_type:
                # 既存アクティブシグナルを確認
                existing = TradingSignal.query.filter_by(
                    currency_pair  = pair,
                    timeframe      = timeframe,
                    indicator_name = strategy_name,
                    signal_type    = signal_type,
                    is_active      = True,
                ).first()

                if existing:
                    # 継続シグナル: 価格・信頼度・有効期限を更新
                    existing.entry_price      = current_price
                    existing.sl_price         = sl_price
                    existing.tp_price         = tp_price
                    existing.sl_pips          = sl_pips
                    existing.tp_pips          = tp_pips
                    existing.confidence_score = confidence
                    existing.expired_at       = expired_at
                    db.session.commit()
                    signal_id = existing.id
                    is_new    = False
                else:
                    # 新規シグナル
                    win_rate_pct = round(float(win_rate_bt) * 100, 2) if win_rate_bt is not None else None
                    record = TradingSignal(
                        currency_pair     = pair,
                        timeframe         = timeframe,
                        signal_type       = signal_type,
                        indicator_name    = strategy_name,
                        indicator_category= "v2_strategy",
                        entry_price       = current_price,
                        sl_price          = sl_price,
                        tp_price          = tp_price,
                        sl_pips           = sl_pips,
                        tp_pips           = tp_pips,
                        win_rate          = win_rate_pct,
                        confidence_score  = confidence,
                        is_active         = True,
                        signal_time       = sig_ts,
                        expired_at        = expired_at,
                    )
                    db.session.add(record)
                    db.session.commit()
                    signal_id = record.id
                    is_new    = True
            else:
                # 条件不成立 → 同名の既存シグナルを無効化
                deactivated = TradingSignal.query.filter_by(
                    currency_pair  = pair,
                    timeframe      = timeframe,
                    indicator_name = strategy_name,
                    is_active      = True,
                ).update({"is_active": False})
                db.session.commit()

            print(json.dumps({
                "ok":                True,
                "pair":              pair,
                "timeframe":         timeframe,
                "strategy_name":     strategy_name,
                "signal_type":       signal_type,      # "BUY" / "SELL" / null
                "signal_fired":      signal_type is not None,
                "filter_passed":     filter_passed,
                "conditions_passed": passed,
                "conditions_matched": matched_ids,
                "current_price":     current_price,
                "sl_price":          sl_price,
                "tp_price":          tp_price,
                "sl_pips":           sl_pips,
                "tp_pips":           tp_pips,
                "confidence":        confidence,
                "signal_id":         signal_id,
                "is_new":            is_new,
            }, ensure_ascii=False, default=str))

    except Exception as e:
        print(json.dumps({
            "ok":     False,
            "error":  str(e),
            "detail": traceback.format_exc(),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
