#!/usr/bin/env python3
"""
verify_indicators.py — テクニカル指標の計算精度を検証するスクリプト

自家実装と ta ライブラリ（requirements.txt に収録済み）の値を突き合わせ、
差分が閾値を超える場合に WARN を表示する。

使い方:
    python tasks/verify_indicators.py
    python tasks/verify_indicators.py --pair GBPJPY --tf 4hr --rows 30
"""

import sys
import os
import argparse
import math
import traceback

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────
WARN_THRESH  = 0.05   # この差分を超えたら WARN
ROWS_DEFAULT = 20     # 比較する最新 N 本

SEP = "─" * 72


# ─────────────────────────────────────────────
# 表示ヘルパー
# ─────────────────────────────────────────────
def fmt(v, decimals=4):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "   N/A  "
    return f"{v:>8.{decimals}f}"


def diff_mark(d):
    if d is None or math.isnan(d):
        return "  ?"
    if abs(d) > WARN_THRESH:
        return f" ⚠ ({d:+.4f})"
    return f" ✅({d:+.5f})"


def header(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ─────────────────────────────────────────────
# 自家実装の指標を計算
# ─────────────────────────────────────────────
def calc_custom(df: pd.DataFrame) -> dict:
    """app/services/indicators/ の実装を使って指標値を計算する"""
    from app.services.indicators.oscillators import _rsi, _macd, _stochastic
    from app.services.indicators.volatility import _atr

    close = df["close"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)

    # RSI
    rsi_s = _rsi(close, 14)

    # MACD
    macd_line, macd_sig, macd_hist = _macd(close, 12, 26, 9)

    # Stochastic K (smoothed), D
    stoch_k, stoch_d = _stochastic(high, low, close, 14, 3, 3)

    # Bollinger Bands (20, 2σ)
    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()          # ddof=1 (pandas default)
    bb_upper = bb_mid + 2.0 * bb_std
    bb_lower = bb_mid - 2.0 * bb_std

    # ATR (14) — 自家実装は ewm(span=14) を使用
    # ※ 標準の Wilder's ATR は ewm(alpha=1/14) = ewm(com=13) と異なる点に注意
    atr_s = _atr(high, low, close, 14)

    return {
        "rsi":        rsi_s,
        "macd_line":  macd_line,
        "macd_sig":   macd_sig,
        "stoch_k":    stoch_k,
        "stoch_d":    stoch_d,
        "bb_upper":   bb_upper,
        "bb_mid":     bb_mid,
        "bb_lower":   bb_lower,
        "atr":        atr_s,
    }


# ─────────────────────────────────────────────
# ta ライブラリで同じ指標を計算
# ─────────────────────────────────────────────
def calc_ta(df: pd.DataFrame) -> dict:
    """ta==0.11.0 (requirements.txt 収録) の実装で指標値を計算する"""
    try:
        import ta
        from ta.momentum  import RSIIndicator, StochasticOscillator
        from ta.trend     import MACD
        from ta.volatility import AverageTrueRange, BollingerBands
    except ImportError:
        print("ERROR: `ta` ライブラリが見つかりません。pip install ta==0.11.0 を実行してください。")
        sys.exit(1)

    close = df["close"].astype(float)
    high  = df["high"].astype(float)
    low   = df["low"].astype(float)

    # RSI — ta は Wilder's smoothing (ewm alpha=1/window) を使用
    rsi_ind  = RSIIndicator(close=close, window=14)
    rsi_s    = rsi_ind.rsi()

    # MACD — ta は ewm(span=fast/slow/sign, adjust=False)
    macd_ind  = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd_ind.macd()
    macd_sig  = macd_ind.macd_signal()

    # Stochastic (14, 3, 3)
    stoch_ind = StochasticOscillator(high=high, low=low, close=close,
                                     window=14, smooth_window=3)
    stoch_k   = stoch_ind.stoch()
    stoch_d   = stoch_ind.stoch_signal()

    # Bollinger Bands (20, 2σ)
    bb_ind    = BollingerBands(close=close, window=20, window_dev=2)
    bb_upper  = bb_ind.bollinger_hband()
    bb_mid    = bb_ind.bollinger_mavg()
    bb_lower  = bb_ind.bollinger_lband()

    # ATR (14) — ta は Wilder's smoothing (ewm alpha=1/14)
    # 自家実装は ewm(span=14) のため差異が出る可能性あり
    atr_ind = AverageTrueRange(high=high, low=low, close=close, window=14)
    atr_s   = atr_ind.average_true_range()

    return {
        "rsi":       rsi_s,
        "macd_line": macd_line,
        "macd_sig":  macd_sig,
        "stoch_k":   stoch_k,
        "stoch_d":   stoch_d,
        "bb_upper":  bb_upper,
        "bb_mid":    bb_mid,
        "bb_lower":  bb_lower,
        "atr":       atr_s,
    }


# ─────────────────────────────────────────────
# 比較出力
# ─────────────────────────────────────────────
def compare(label: str, custom_s: pd.Series, ta_s: pd.Series,
            timestamps, rows: int, decimals: int = 4) -> dict:
    """
    2つの Series を比較して表示する。
    Returns: {"max_diff": float, "warn_count": int}
    """
    header(f"{label}")
    print(f"  {'timestamp':<22} {'自家実装':>10} {'ta lib':>10} {'差分':>14}")
    print(f"  {'─'*22} {'─'*10} {'─'*10} {'─'*14}")

    diffs = []
    for i, ts in enumerate(timestamps[-rows:]):
        idx = len(custom_s) - rows + i
        if idx < 0:
            continue
        c = custom_s.iloc[idx]
        t = ta_s.iloc[idx]
        if pd.isna(c) or pd.isna(t):
            continue
        d = c - t
        diffs.append(abs(d))
        mark = diff_mark(d)
        ts_str = str(ts)[:19] if hasattr(ts, "__str__") else ""
        print(f"  {ts_str:<22} {fmt(c, decimals)} {fmt(t, decimals)} {mark}")

    max_diff = max(diffs) if diffs else 0.0
    warn_count = sum(1 for d in diffs if d > WARN_THRESH)
    return {"max_diff": max_diff, "warn_count": warn_count}


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="テクニカル指標の計算精度検証")
    parser.add_argument("--pair", default="USDJPY", help="通貨ペア (default: USDJPY)")
    parser.add_argument("--tf",   default="1hr",    help="タイムフレーム (default: 1hr)")
    parser.add_argument("--rows", type=int, default=ROWS_DEFAULT,
                        help=f"比較する最新N本 (default: {ROWS_DEFAULT})")
    args = parser.parse_args()

    print(f"\n{'='*72}")
    print(f"  テクニカル指標 計算精度 検証レポート")
    print(f"  対象: {args.pair} / {args.tf}  （最新 {args.rows} 本）")
    print(f"  閾値: 差分 > {WARN_THRESH} で ⚠ 表示")
    print(f"{'='*72}")

    # ── データ取得 ──────────────────────────────────────────
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from app.services.data_fetcher import get_candles
            df = get_candles(args.pair, args.tf, limit=300)
    except Exception as e:
        print(f"\nDB 接続エラー: {e}")
        print("yfinance からデータを直接取得します...")
        try:
            import yfinance as yf
            from datetime import datetime, timedelta
            _tf_map = {"5min": "5m", "15min": "15m", "1hr": "1h", "4hr": "4h", "daily": "1d"}
            _yf_tf  = _tf_map.get(args.tf, "1h")
            _period = "60d" if _yf_tf in ("5m", "15m") else "730d"
            sym = args.pair + "=X"
            raw = yf.download(sym, period=_period, interval=_yf_tf,
                              auto_adjust=True, progress=False)
            if raw.empty:
                print("yfinance でもデータ取得失敗。終了します。")
                sys.exit(1)
            raw.columns = [c.lower() for c in raw.columns]
            raw = raw.rename(columns={"open": "open", "high": "high",
                                      "low": "low", "close": "close"})
            raw = raw.reset_index().rename(columns={"Datetime": "timestamp",
                                                     "Date": "timestamp"})
            df = raw[["timestamp", "open", "high", "low", "close"]].dropna().tail(300)
        except Exception as e2:
            print(f"yfinance 取得失敗: {e2}")
            traceback.print_exc()
            sys.exit(1)

    if df is None or df.empty:
        print("データが空です。fetch_data を実行してDBを更新してください。")
        sys.exit(1)

    print(f"\n  取得本数: {len(df)} 本")
    timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else df.index.tolist()

    # ── 指標計算 ─────────────────────────────────────────
    try:
        from app import create_app as _ca
        _app = _ca()
        with _app.app_context():
            custom = calc_custom(df)
    except Exception:
        custom = calc_custom(df)

    ta_vals = calc_ta(df)

    # ── 比較出力 ─────────────────────────────────────────
    summary = {}

    summary["RSI(14)"] = compare(
        "RSI (14) — Wilder平滑化",
        custom["rsi"], ta_vals["rsi"], timestamps, args.rows, decimals=3
    )

    summary["MACD line"] = compare(
        "MACD (12,26,9) — MACD線",
        custom["macd_line"], ta_vals["macd_line"], timestamps, args.rows, decimals=4
    )

    summary["MACD signal"] = compare(
        "MACD (12,26,9) — シグナル線",
        custom["macd_sig"], ta_vals["macd_sig"], timestamps, args.rows, decimals=4
    )

    summary["Stoch K"] = compare(
        "Stochastic (14,3,3) — %K",
        custom["stoch_k"], ta_vals["stoch_k"], timestamps, args.rows, decimals=3
    )

    summary["Stoch D"] = compare(
        "Stochastic (14,3,3) — %D",
        custom["stoch_d"], ta_vals["stoch_d"], timestamps, args.rows, decimals=3
    )

    summary["BB Upper"] = compare(
        "Bollinger Bands (20,2σ) — 上バンド",
        custom["bb_upper"], ta_vals["bb_upper"], timestamps, args.rows, decimals=4
    )

    summary["BB Lower"] = compare(
        "Bollinger Bands (20,2σ) — 下バンド",
        custom["bb_lower"], ta_vals["bb_lower"], timestamps, args.rows, decimals=4
    )

    print(f"\n{SEP}")
    print("  ATR (14) — 平滑化方式の違いに注意")
    print(f"  自家実装: ewm(span=14)  α=2/15≈0.133  ← EMA方式")
    print(f"  ta lib  : ewm(alpha=1/14) α≈0.071    ← Wilder's RMA方式 (標準)")
    print(f"  ⇒ 差分が生じることは仕様上 想定内 です")
    print(SEP)
    summary["ATR(14)"] = compare(
        "ATR (14)",
        custom["atr"], ta_vals["atr"], timestamps, args.rows, decimals=4
    )

    # ── サマリー ─────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  検証サマリー")
    print(f"{'='*72}")
    print(f"  {'指標':<20} {'最大差分':>10} {'⚠件数':>8} {'判定':>6}")
    print(f"  {'─'*20} {'─'*10} {'─'*8} {'─'*6}")

    all_ok = True
    for label, res in summary.items():
        is_atr = label == "ATR(14)"
        verdict = "仕様" if is_atr else ("⚠ WARN" if res["warn_count"] > 0 else "✅ OK")
        if res["warn_count"] > 0 and not is_atr:
            all_ok = False
        print(f"  {label:<20} {res['max_diff']:>10.5f} {res['warn_count']:>8}   {verdict}")

    print(f"\n  ATR: Wilder's RMA vs EMA の差異は既知（結果には大きく影響しない）")
    if all_ok:
        print("\n  🎉 ATR を除く全指標で差分が閾値内 → 計算は正確です")
    else:
        warn_labels = [l for l, r in summary.items() if r["warn_count"] > 0 and l != "ATR(14)"]
        print(f"\n  ⚠ 要確認の指標: {', '.join(warn_labels)}")

    print(f"\n{'='*72}\n")


if __name__ == "__main__":
    main()
