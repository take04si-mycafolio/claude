#!/usr/bin/env python3
"""
run_indicator_page_bt.py — テクニカルページ専用バックテスト CLI スクリプト

PHP admin/api.php の exec() から同期呼び出しされる。
引数: <params_json_file_path>
標準出力: JSON 結果（改行なし）

ランキング用 backtest_results とは独立した
indicator_page_bt_results / indicator_page_sim_trades テーブルに保存する。
"""

import sys
import os
import json
import warnings
import traceback

warnings.filterwarnings("ignore")   # pandas 警告が JSON 出力を汚染しないよう抑制

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

TRADE_LIMIT = 50  # 1通貨ペア・TF あたりの保存トレード数上限


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "使い方: run_indicator_page_bt.py <params_file>"}))
        return

    try:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            body = json.load(f)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"パラメータ読み込みエラー: {e}"}))
        return

    try:
        from app import create_app, db
        from sqlalchemy import text
        import pandas as pd

        app = create_app()
        with app.app_context():
            from app.services.data_fetcher import get_candles
            from app.services.backtester import run_backtest_for_indicator, _parse_trade_dt
            from app.services.indicators.oscillators import calculate_oscillators
            from app.services.indicators.trend import calculate_trend
            from app.services.indicators.lines import calculate_lines
            from app.services.indicators.volatility import calculate_volatility
            from app.services.indicators.patterns import calculate_patterns
            from app.services.indicators.composite import calculate_composite
            from app.config import Config

            indicator_name  = body.get("indicator_name", "").strip()
            pairs           = body.get("pairs")       or Config.CURRENCY_PAIRS
            # tf_ranges: {tf: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}
            # 足ごとに個別の日付範囲を指定できる。なければ start_date/end_date にフォールバック。
            tf_ranges       = body.get("tf_ranges")   or {}
            sl_pips         = float(body.get("sl_pips", 20))
            tp_pips         = float(body.get("tp_pips", 40))
            start_date      = body.get("start_date") or None   # グローバルフォールバック
            end_date        = body.get("end_date")   or None
            initial_capital = float(body.get("initial_capital", 1_000_000))

            # timeframes は tf_ranges キーから導出（後方互換: timeframes 直指定も許容）
            if tf_ranges:
                timeframes = [tf for tf in tf_ranges.keys() if tf in Config.TIMEFRAMES]
            else:
                timeframes = body.get("timeframes") or Config.TIMEFRAMES

            if not indicator_name:
                print(json.dumps({"ok": False, "error": "indicator_name が必要です"}))
                return

            # テーブルを初回作成（存在しなければ）
            _ensure_tables(db, text)

            # 指標名 → 計算関数マップ（全カテゴリ）
            FUNC_MAP = {}
            dummy = pd.DataFrame({c: [float(i) for i in range(1, 61)]
                                  for c in ["open", "high", "low", "close", "volume"]})
            for func in [calculate_oscillators, calculate_trend, calculate_lines,
                         calculate_volatility, calculate_patterns, calculate_composite]:
                try:
                    for k in func(dummy).keys():
                        FUNC_MAP[k] = func
                except Exception:
                    pass

            ind_func = FUNC_MAP.get(indicator_name)
            if ind_func is None:
                print(json.dumps({"ok": False,
                                  "error": f"指標 '{indicator_name}' が見つかりません"}))
                return

            # 通貨ペア × 時間足 でバックテスト実行
            summary = {}
            for pair in pairs:
                if pair not in Config.CURRENCY_PAIRS:
                    continue
                summary[pair] = {}
                for tf in timeframes:
                    if tf not in Config.TIMEFRAMES:
                        continue

                    # TF固有の日付範囲（なければグローバルフォールバック）
                    tf_range = tf_ranges.get(tf, {}) if tf_ranges else {}
                    tf_start = tf_range.get("start") or start_date
                    tf_end   = tf_range.get("end")   or end_date

                    df = get_candles(pair, tf, start_date=tf_start, end_date=tf_end)
                    if df is None or df.empty or len(df) < 30:
                        summary[pair][tf] = {"ok": False, "error": "データ不足"}
                        continue

                    res = run_backtest_for_indicator(
                        df=df,
                        indicator_name=indicator_name,
                        indicator_func=ind_func,
                        pair=pair,
                        timeframe=tf,
                        initial_capital=initial_capital,
                        sl_pips=sl_pips,
                        tp_pips=tp_pips,
                        backtest_hours=99999,
                    )
                    if not res:
                        summary[pair][tf] = {"ok": False, "error": "シグナルなし"}
                        continue

                    _save_result(db, text, res, indicator_name, pair, tf,
                                 sl_pips, tp_pips, tf_start, tf_end,
                                 len(df), initial_capital, _parse_trade_dt)

                    summary[pair][tf] = {
                        "ok":            True,
                        "total_trades":  res["total_trades"],
                        "win_rate":      round(float(res["win_rate"]), 1),
                        "profit_factor": round(float(res.get("profit_factor") or 0), 2),
                        "total_profit":  round(float(res["total_profit"]), 0),
                        "start_date":    tf_start or "",
                        "end_date":      tf_end   or "",
                    }

            print(json.dumps({
                "ok":             True,
                "indicator_name": indicator_name,
                "sl_pips":        sl_pips,
                "tp_pips":        tp_pips,
                "summary":        summary,
            }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "ok":     False,
            "error":  str(e),
            "detail": traceback.format_exc(),
        }, ensure_ascii=False))


# ---------------------------------------------------------------------------
# DB ヘルパー
# ---------------------------------------------------------------------------

def _ensure_tables(db, text):
    """indicator_page 専用テーブルを初回作成"""
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS indicator_page_bt_results (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            indicator_name  VARCHAR(80)  NOT NULL,
            currency_pair   VARCHAR(10)  NOT NULL,
            timeframe       VARCHAR(10)  NOT NULL,
            signal_direction VARCHAR(10) DEFAULT 'BOTH',
            win_rate        DECIMAL(5,2) NOT NULL DEFAULT 0,
            total_trades    INT          NOT NULL DEFAULT 0,
            winning_trades  INT          NOT NULL DEFAULT 0,
            losing_trades   INT          NOT NULL DEFAULT 0,
            total_profit    DECIMAL(15,2) NOT NULL DEFAULT 0,
            initial_capital DECIMAL(15,2) NOT NULL DEFAULT 1000000,
            final_capital   DECIMAL(15,2) NOT NULL DEFAULT 1000000,
            sl_pips         DECIMAL(8,2)  NOT NULL DEFAULT 20,
            tp_pips         DECIMAL(8,2)  NOT NULL DEFAULT 40,
            max_drawdown    DECIMAL(15,2) DEFAULT 0,
            profit_factor   DECIMAL(8,4)  DEFAULT 0,
            start_date      DATE NULL,
            end_date        DATE NULL,
            bars_used       INT DEFAULT 0,
            calculated_at   DATETIME NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_ind_page_bt (indicator_name, currency_pair, timeframe)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS indicator_page_sim_trades (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            bt_result_id    BIGINT DEFAULT NULL,
            currency_pair   VARCHAR(10) NOT NULL,
            timeframe       VARCHAR(10) NOT NULL,
            indicator_name  VARCHAR(80) NOT NULL,
            entry_at        DATETIME NOT NULL,
            direction       VARCHAR(4)  NOT NULL,
            entry_price     DECIMAL(12,5),
            exit_at         DATETIME,
            exit_price      DECIMAL(12,5),
            tp_price        DECIMAL(12,5),
            sl_price        DECIMAL(12,5),
            sl_pips         DECIMAL(8,2),
            tp_pips         DECIMAL(8,2),
            outcome         VARCHAR(4),
            profit_loss     DECIMAL(15,2),
            capital_after   DECIMAL(15,2),
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_ibt_trade (currency_pair, timeframe, indicator_name, entry_at, direction)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))
    db.session.commit()


def _save_result(db, text, res, indicator_name, pair, tf,
                 sl_pips, tp_pips, start_date, end_date,
                 bars_used, initial_capital, _parse_dt):
    """バックテスト結果を indicator_page 専用テーブルに保存（Upsert）"""

    # サマリー Upsert
    db.session.execute(text("""
        INSERT INTO indicator_page_bt_results
            (indicator_name, currency_pair, timeframe, signal_direction,
             win_rate, total_trades, winning_trades, losing_trades,
             total_profit, initial_capital, final_capital,
             sl_pips, tp_pips, max_drawdown, profit_factor,
             start_date, end_date, bars_used, calculated_at)
        VALUES
            (:ind, :pair, :tf, 'BOTH',
             :wr, :tt, :wt, :lt,
             :profit, :ic, :fc,
             :sl, :tp, :md, :pf,
             :sd, :ed, :bu, NOW())
        ON DUPLICATE KEY UPDATE
            win_rate=VALUES(win_rate),
            total_trades=VALUES(total_trades),
            winning_trades=VALUES(winning_trades),
            losing_trades=VALUES(losing_trades),
            total_profit=VALUES(total_profit),
            initial_capital=VALUES(initial_capital),
            final_capital=VALUES(final_capital),
            sl_pips=VALUES(sl_pips),
            tp_pips=VALUES(tp_pips),
            max_drawdown=VALUES(max_drawdown),
            profit_factor=VALUES(profit_factor),
            start_date=VALUES(start_date),
            end_date=VALUES(end_date),
            bars_used=VALUES(bars_used),
            calculated_at=NOW()
    """), {
        "ind": indicator_name, "pair": pair, "tf": tf,
        "wr":  float(res["win_rate"]),
        "tt":  int(res["total_trades"]),
        "wt":  int(res["winning_trades"]),
        "lt":  int(res["losing_trades"]),
        "profit": float(res["total_profit"]),
        "ic":  float(res["initial_capital"]),
        "fc":  float(res["final_capital"]),
        "sl":  sl_pips, "tp": tp_pips,
        "md":  float(res.get("max_drawdown") or 0),
        "pf":  float(res.get("profit_factor") or 0),
        "sd":  start_date, "ed": end_date,
        "bu":  bars_used,
    })
    db.session.commit()

    # レコード ID を取得
    row = db.session.execute(text("""
        SELECT id FROM indicator_page_bt_results
        WHERE indicator_name=:ind AND currency_pair=:pair AND timeframe=:tf
    """), {"ind": indicator_name, "pair": pair, "tf": tf}).fetchone()
    bt_id = row.id if row else None

    # トレード: 全削除して最新 TRADE_LIMIT 件を再挿入
    db.session.execute(text("""
        DELETE FROM indicator_page_sim_trades
        WHERE indicator_name=:ind AND currency_pair=:pair AND timeframe=:tf
    """), {"ind": indicator_name, "pair": pair, "tf": tf})

    trades_all = res.get("trades", [])
    trades = trades_all[-TRADE_LIMIT:]
    # TRADE_LIMIT 件に切り詰めた場合、先頭トレードの損益が「全累積損益」になるバグを修正:
    # 保存ウィンドウの直前トレードの capital_after を基点にする
    if len(trades_all) > TRADE_LIMIT:
        prev_cap = float(trades_all[-(TRADE_LIMIT + 1)]["capital_after"])
    else:
        prev_cap = float(initial_capital)
    for t in trades:
        entry_ts = _parse_dt(t.get("entry_ts"))
        exit_ts  = _parse_dt(t.get("exit_ts"))
        _ep  = float(t.get("entry_price") or 0)
        _tpp = t.get("tp_price")
        _slp = t.get("sl_price")
        actual_tp = round(abs(float(_tpp) - _ep) / 0.01, 2) if _tpp and _ep else tp_pips
        actual_sl = round(abs(_ep - float(_slp)) / 0.01, 2) if _slp and _ep else sl_pips
        cap_after = float(t.get("capital_after", prev_cap))
        pnl       = round(cap_after - prev_cap, 2)
        prev_cap  = cap_after
        try:
            db.session.execute(text("""
                INSERT IGNORE INTO indicator_page_sim_trades
                    (bt_result_id, currency_pair, timeframe, indicator_name,
                     entry_at, direction, entry_price, exit_at, exit_price,
                     tp_price, sl_price, sl_pips, tp_pips,
                     outcome, profit_loss, capital_after)
                VALUES
                    (:bid, :pair, :tf, :ind,
                     :ea, :dir, :ep, :xa, :xp,
                     :tpp, :slp, :sl, :tp,
                     :oc, :pnl, :ca)
            """), {
                "bid": bt_id, "pair": pair, "tf": tf, "ind": indicator_name,
                "ea": entry_ts, "dir": t.get("signal", ""),
                "ep": t.get("entry_price"),
                "xa": exit_ts,  "xp": t.get("exit_price"),
                "tpp": t.get("tp_price"),   "slp": t.get("sl_price"),
                "sl": actual_sl, "tp": actual_tp,
                "oc": t.get("outcome"), "pnl": pnl, "ca": cap_after,
            })
        except Exception:
            pass
    db.session.commit()


if __name__ == "__main__":
    main()
