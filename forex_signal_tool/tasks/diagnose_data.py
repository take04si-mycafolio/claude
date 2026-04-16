#!/usr/bin/env python3
"""
データ・シグナル診断スクリプト

シグナルが更新されなくなった原因を特定するためのチェックリスト。

使い方:
    python tasks/diagnose_data.py

チェック内容:
  1. DBの最新キャンドル日時（ペア・TFごと）
  2. yfinanceから実際にデータが取得できるか
  3. DBとyfinanceのデータ差分（最新キャンドルのズレ）
  4. アクティブシグナルの最終更新日時
  5. バックテスト結果の件数（シグナル生成の前提条件）
"""

import sys
import os
import logging
from datetime import datetime, timezone, timedelta

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

logging.basicConfig(level=logging.WARNING, format="%(message)s")

PAIRS = ["USDJPY", "GBPJPY", "EURJPY"]
TFS   = ["5min", "15min", "1hr", "4hr"]   # daily はシグナル生成に使わない
JST   = timedelta(hours=9)


def jst(dt_utc_naive) -> str:
    if dt_utc_naive is None:
        return "N/A"
    jst_dt = dt_utc_naive + JST
    return jst_dt.strftime("%Y-%m-%d %H:%M JST")


def check_db_latest(app):
    """DBの最新キャンドルタイムスタンプを確認"""
    from app.models.price_data import PriceData

    print("\n" + "=" * 60)
    print("① DB最新キャンドル（UTC naive, JST表示）")
    print("=" * 60)
    print(f"{'ペア':<10} {'TF':<8} {'DB最新キャンドル':<25} {'件数':>7}")
    print("-" * 60)

    results = {}
    with app.app_context():
        for pair in PAIRS:
            for tf in TFS:
                from app.models.price_data import PriceData as _P
                rec = (
                    _P.query
                    .filter_by(currency_pair=pair, timeframe=tf)
                    .order_by(_P.timestamp.desc())
                    .first()
                )
                cnt = _P.query.filter_by(currency_pair=pair, timeframe=tf).count()
                latest = rec.timestamp if rec else None
                results[(pair, tf)] = latest
                age_str = ""
                if latest:
                    age = datetime.utcnow() - latest
                    h = int(age.total_seconds() // 3600)
                    age_str = f"（{h}時間前）"
                print(f"{pair:<10} {tf:<8} {jst(latest):<25} {cnt:>7}件  {age_str}")

    return results


def check_yfinance():
    """yfinanceから最新データが取得できるか確認"""
    import yfinance as yf

    print("\n" + "=" * 60)
    print("② yfinance 接続テスト（最新キャンドル）")
    print("=" * 60)

    YF_MAP = {"USDJPY": "USDJPY=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X"}
    YF_IV  = {"5min": "5m", "15min": "15m", "1hr": "60m"}
    DAYS   = {"5min": 7, "15min": 55, "1hr": 90}

    print(f"{'ペア':<10} {'TF':<8} {'yfinance最新':<25} {'行数':>6}")
    print("-" * 60)

    yf_results = {}
    for pair in PAIRS:
        sym = YF_MAP[pair]
        ticker = yf.Ticker(sym)
        for tf in ["5min", "15min", "1hr"]:
            interval  = YF_IV[tf]
            days_back = DAYS[tf]
            end_dt    = datetime.now(timezone.utc)
            start_dt  = end_dt - timedelta(days=days_back)
            try:
                df = ticker.history(
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d"),
                    interval=interval,
                    auto_adjust=True,
                )
                if df.empty:
                    print(f"{pair:<10} {tf:<8} {'⚠️ データなし':<25} {'0':>6}")
                    yf_results[(pair, tf)] = None
                else:
                    import pandas as pd
                    latest_ts = pd.to_datetime(df.index[-1], utc=True).to_pydatetime()
                    latest_ts_naive = latest_ts.replace(tzinfo=None)
                    latest_jst = latest_ts_naive + JST
                    age = datetime.utcnow() - latest_ts_naive
                    h = int(age.total_seconds() // 3600)
                    print(f"{pair:<10} {tf:<8} {latest_jst.strftime('%Y-%m-%d %H:%M JST'):<25} {len(df):>6}行  ({h}時間前)")
                    yf_results[(pair, tf)] = latest_ts_naive
            except Exception as e:
                print(f"{pair:<10} {tf:<8} {'❌ エラー: ' + str(e)[:30]:<25}")
                yf_results[(pair, tf)] = None

    return yf_results


def check_gap(db_results, yf_results):
    """DBとyfinanceの最新キャンドルのズレを確認"""
    print("\n" + "=" * 60)
    print("③ DB vs yfinance ズレ確認")
    print("=" * 60)
    print(f"{'ペア':<10} {'TF':<8} {'DBとのズレ':>20}")
    print("-" * 60)

    for pair in PAIRS:
        for tf in ["5min", "15min", "1hr"]:
            db_latest = db_results.get((pair, tf))
            yf_latest = yf_results.get((pair, tf))
            if db_latest is None:
                print(f"{pair:<10} {tf:<8} {'⚠️ DB にデータなし':>20}")
            elif yf_latest is None:
                print(f"{pair:<10} {tf:<8} {'⚠️ yfinance からデータ取得不可':>20}")
            else:
                diff = yf_latest - db_latest
                hours = diff.total_seconds() / 3600
                if hours < 0.5:
                    status = "✅ 最新"
                elif hours < 4:
                    status = f"⚠️ {hours:.1f}時間遅れ"
                else:
                    status = f"❌ {hours:.1f}時間遅れ"
                print(f"{pair:<10} {tf:<8} {status:>20}")


def check_signals(app):
    """アクティブシグナルの最終更新を確認"""
    from app.models.signal import TradingSignal

    print("\n" + "=" * 60)
    print("④ アクティブシグナル状況")
    print("=" * 60)

    with app.app_context():
        active = TradingSignal.query.filter_by(is_active=True).all()
        print(f"アクティブシグナル総数: {len(active)}件")
        if active:
            # signal_time の最新を確認
            latest_st = max(s.signal_time for s in active if s.signal_time)
            oldest_st = min(s.signal_time for s in active if s.signal_time)
            print(f"signal_time 最新: {jst(latest_st)}")
            print(f"signal_time 最古: {jst(oldest_st)}")

            # created_at の最新を確認（実際の生成日時）
            if hasattr(active[0], 'created_at') and active[0].created_at:
                latest_ca = max(s.created_at for s in active if getattr(s, 'created_at', None))
                print(f"created_at  最新: {jst(latest_ca)}  ← シグナルが実際に更新された日時")

        # 最近7日間のシグナル件数（アクティブ・非アクティブ含む）
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent = TradingSignal.query.filter(TradingSignal.signal_time >= cutoff).count()
        print(f"直近7日のシグナル総数（アクティブ含む全件）: {recent}件")


def check_backtest_results(app):
    """シグナル生成の前提となるバックテスト結果件数を確認"""
    print("\n" + "=" * 60)
    print("⑤ バックテスト結果（シグナル生成の前提条件）")
    print("=" * 60)
    print("  ※ win_rate >= 55% かつ total_trades >= 3 の組み合わせのみシグナル生成")

    with app.app_context():
        try:
            from app.models.backtest_result import BacktestResult
            total = BacktestResult.query.count()
            eligible = BacktestResult.query.filter(
                BacktestResult.win_rate >= 55,
                BacktestResult.total_trades >= 3,
            ).count()
            print(f"バックテスト結果総数: {total}件")
            print(f"うちシグナル生成対象: {eligible}件")
            if eligible == 0:
                print("  ❌ バックテスト結果が0件 → シグナルは生成されません")
                print("     run_ranking_bt.py を実行してください")
        except Exception as e:
            print(f"  ⚠️ バックテスト結果テーブル確認エラー: {e}")


def check_settings(app):
    """最後のデータ取得・シグナル更新日時を確認"""
    print("\n" + "=" * 60)
    print("⑥ Cron最終実行記録（Settingsテーブル）")
    print("=" * 60)

    with app.app_context():
        try:
            from app.models.settings import Setting
            keys = [
                ("last_data_fetch_at", "データ取得"),
                ("fetch_status",       "取得ステータス"),
                ("last_signal_update_at", "シグナル更新"),
                ("signal_status",      "シグナルステータス"),
            ]
            for k, label in keys:
                v = Setting.get(k, default="(未設定)")
                print(f"  {label}: {v}")
        except Exception as e:
            print(f"  ⚠️ Settings確認エラー: {e}")


def main():
    print("=" * 60)
    print("データ・シグナル診断レポート")
    print(f"実行日時: {(datetime.utcnow() + JST).strftime('%Y-%m-%d %H:%M JST')}")
    print("=" * 60)

    from app import create_app
    app = create_app()

    # ① DB最新キャンドル
    db_results = check_db_latest(app)

    # ② yfinance接続テスト
    print("\nyfinance に接続中...")
    try:
        yf_results = check_yfinance()
    except ImportError:
        print("  ⚠️ yfinance がインストールされていません")
        yf_results = {}

    # ③ ズレ確認
    if yf_results:
        check_gap(db_results, yf_results)

    # ④ アクティブシグナル
    check_signals(app)

    # ⑤ バックテスト結果
    check_backtest_results(app)

    # ⑥ Settings
    check_settings(app)

    print("\n" + "=" * 60)
    print("診断完了")
    print("=" * 60)
    print()
    print("【対処法の目安】")
    print("  ③ でズレが大きい → yfinance 問題: pip install -U yfinance を試す")
    print("  ② でデータなし  → Yahoo Finance API 障害の可能性。時間をおいて再実行")
    print("  ⑤ で対象0件    → run_ranking_bt.py でバックテストを再実行")
    print("  ⑥ で未設定      → Cronが実行されていない可能性")


if __name__ == "__main__":
    main()
