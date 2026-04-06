"""
シグナルエンジン

バックテスト結果を参照して勝率の高い指標を特定し、
リアルタイムのシグナルを生成してDBに保存する。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from app.config import Config

logger = logging.getLogger(__name__)


def get_effective_settings() -> dict:
    """DBから設定値を取得（なければデフォルト）"""
    from app.models.settings import Setting
    return {
        "initial_capital": Setting.get_float("initial_capital", Config.DEFAULT_INITIAL_CAPITAL),
        "sl_pips": Setting.get_float("sl_pips", Config.DEFAULT_SL_PIPS),
        "tp_pips": Setting.get_float("tp_pips", Config.DEFAULT_TP_PIPS),
        "backtest_hours": Setting.get_int("backtest_hours", Config.DEFAULT_BACKTEST_HOURS),
        "min_win_rate": Setting.get_float("min_win_rate", Config.MIN_WIN_RATE),
        "min_trades": Setting.get_int("min_trades", Config.MIN_TRADES_COUNT),
    }


def get_active_backtest_results(pair: str, timeframe: str, min_win_rate: float, min_trades: int) -> list:
    """勝率が閾値以上のバックテスト結果を取得"""
    from app.models.backtest import BacktestResult
    results = (
        BacktestResult.query
        .filter(
            BacktestResult.currency_pair == pair,
            BacktestResult.timeframe == timeframe,
            BacktestResult.win_rate >= min_win_rate,
            BacktestResult.total_trades >= min_trades,
        )
        .order_by(BacktestResult.win_rate.desc())
        .all()
    )
    return results


def calculate_confidence_score(win_rate: float, total_trades: int,
                                mtf_agreement: int = 0) -> float:
    """
    シグナルの信頼度スコアを計算 (0-100)

    win_rate        : 勝率
    total_trades    : バックテストでのトレード数（サンプルサイズ）
    mtf_agreement   : 同方向の上位タイムフレーム数（マルチタイムフレーム一致）
    """
    # 基本スコア = 勝率ベース
    base_score = max(0.0, (win_rate - 50.0) * 2)  # 50%=0, 100%=100

    # サンプルサイズボーナス
    sample_bonus = min(10.0, total_trades * 1.0)

    # MTFボーナス
    mtf_bonus = mtf_agreement * 5.0

    score = min(100.0, base_score + sample_bonus + mtf_bonus)
    return round(score, 1)


def generate_signals_for_pair_tf(pair: str, timeframe: str, df: pd.DataFrame) -> list:
    """
    特定の通貨ペア・タイムフレームの現在シグナルを生成する。

    Returns
    -------
    list of dict: 生成されたシグナルのリスト
    """
    from app.services.indicators import calculate_all

    settings = get_effective_settings()

    if df.empty or len(df) < 30:
        return []

    # 全テクニカル指標を計算
    try:
        all_indicators = calculate_all(df)
    except Exception as exc:
        logger.error("Indicator calculation failed for %s %s: %s", pair, timeframe, exc)
        return []

    # 勝率の高い指標を取得
    active_bt = get_active_backtest_results(
        pair, timeframe,
        min_win_rate=settings["min_win_rate"],
        min_trades=settings["min_trades"],
    )

    # バックテスト結果をインデックス化
    bt_map = {r.indicator_name: r for r in active_bt}

    current_price = float(df["close"].iloc[-1])
    sl_pips = settings["sl_pips"]
    tp_pips = settings["tp_pips"]

    signals = []

    for ind_name, ind_data in all_indicators.items():
        signal_type = ind_data.get("signal", "NEUTRAL")
        if signal_type == "NEUTRAL":
            continue

        # バックテスト結果で検証
        bt_result = bt_map.get(ind_name)
        if bt_result is None:
            # バックテスト未実施 or 勝率不足 → スキップ
            continue

        win_rate = float(bt_result.win_rate)

        # TP/SL価格計算
        if signal_type == "BUY":
            tp_price = current_price + tp_pips * 0.01
            sl_price = current_price - sl_pips * 0.01
        else:
            tp_price = current_price - tp_pips * 0.01
            sl_price = current_price + sl_pips * 0.01

        confidence = calculate_confidence_score(win_rate, bt_result.total_trades)

        signals.append({
            "currency_pair": pair,
            "timeframe": timeframe,
            "signal_type": signal_type,
            "indicator_name": ind_name,
            "indicator_category": ind_data.get("category", "unknown"),
            "entry_price": current_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_pips": sl_pips,
            "tp_pips": tp_pips,
            "win_rate": win_rate,
            "confidence_score": confidence,
            "signal_time": datetime.now(timezone.utc),
        })

    return signals


def run_signal_engine() -> dict:
    """
    全通貨ペア・タイムフレームのシグナルを生成してDBに保存する。

    Returns
    -------
    dict: 通貨ペアごとの生成シグナル数
    """
    from app import db
    from app.models.signal import TradingSignal
    from app.services.data_fetcher import get_candles

    # 既存のアクティブシグナルを無効化
    TradingSignal.query.filter_by(is_active=True).update({"is_active": False})
    db.session.commit()

    results = {}

    for pair in Config.CURRENCY_PAIRS:
        results[pair] = {}
        for tf in Config.TIMEFRAMES:
            df = get_candles(pair, tf, limit=200)
            if df.empty:
                logger.warning("No data for %s %s", pair, tf)
                continue

            signals = generate_signals_for_pair_tf(pair, tf, df)

            for s in signals:
                record = TradingSignal(
                    currency_pair=s["currency_pair"],
                    timeframe=s["timeframe"],
                    signal_type=s["signal_type"],
                    indicator_name=s["indicator_name"],
                    indicator_category=s.get("indicator_category"),
                    entry_price=s["entry_price"],
                    sl_price=s["sl_price"],
                    tp_price=s["tp_price"],
                    sl_pips=s["sl_pips"],
                    tp_pips=s["tp_pips"],
                    win_rate=s["win_rate"],
                    confidence_score=s["confidence_score"],
                    is_active=True,
                    signal_time=s["signal_time"],
                )
                db.session.add(record)

            db.session.commit()
            results[pair][tf] = len(signals)
            logger.info("%s %s: %d signals generated", pair, tf, len(signals))

    return results


def get_summary_signals() -> dict:
    """
    全通貨ペアのアクティブシグナルをサマリー形式で取得する。
    ダッシュボード表示用。
    """
    from app.models.signal import TradingSignal

    summary = {}
    for pair in Config.CURRENCY_PAIRS:
        signals = (
            TradingSignal.query
            .filter_by(currency_pair=pair, is_active=True)
            .order_by(TradingSignal.confidence_score.desc())
            .all()
        )

        buy_count = sum(1 for s in signals if s.signal_type == "BUY")
        sell_count = sum(1 for s in signals if s.signal_type == "SELL")

        if buy_count > sell_count:
            overall = "BUY"
            strength = buy_count / max(buy_count + sell_count, 1) * 100
        elif sell_count > buy_count:
            overall = "SELL"
            strength = sell_count / max(buy_count + sell_count, 1) * 100
        else:
            overall = "NEUTRAL"
            strength = 50.0

        summary[pair] = {
            "overall_signal": overall,
            "signal_strength": round(strength, 1),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "total_signals": len(signals),
            "top_signals": [s.to_dict() for s in signals[:5]],
        }

    return summary
