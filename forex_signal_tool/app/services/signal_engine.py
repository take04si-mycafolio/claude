"""
シグナルエンジン

バックテスト結果を参照して勝率の高い指標を特定し、
リアルタイムのシグナルを生成してDBに保存する。
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

# タイムフレーム別シグナル有効期限（時間）
TF_EXPIRY_HOURS = {
    "15min": 2,
    "1hr":   6,
    "4hr":  24,
    "daily": 72,
}

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


_CATEGORY_BASE_SCORE: dict = {
    "composite": 50, "custom": 50,
    "pattern":   45,
    "trend":     40,
    "line":      35, "oscillator": 35,
    "volatility": 15,
}


def calculate_confidence_score_nobt(indicator_category: str) -> float:
    """BT未実施指標の暫定信頼度スコア（カテゴリ基準, 0-100）。
    BTが蓄積されると run_signal_engine() が BT結果で上書きする。"""
    return float(_CATEGORY_BASE_SCORE.get(indicator_category or "unknown", 25))


def generate_signals_for_pair_tf(pair: str, timeframe: str, df: pd.DataFrame,
                                   settings: dict) -> list:
    """
    特定の通貨ペア・タイムフレームの現在シグナルを生成する。

    Parameters
    ----------
    settings : get_effective_settings() の結果（呼び出し側で1回だけ取得する）

    Returns
    -------
    list of dict: 生成されたシグナルのリスト
    """
    from app.services.indicators import calculate_all
    if df.empty or len(df) < 30:
        return []

    # シグナル発生時刻 = 最新ローソク足の確定時刻
    latest_candle_ts = df["timestamp"].iloc[-1]
    if hasattr(latest_candle_ts, "to_pydatetime"):
        latest_candle_ts = latest_candle_ts.to_pydatetime()
    if latest_candle_ts.tzinfo is None:
        latest_candle_ts = latest_candle_ts.replace(tzinfo=timezone.utc)

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

        # バックテスト結果で勝率を補完（なくても通す）
        bt_result = bt_map.get(ind_name)
        if bt_result is not None:
            win_rate   = float(bt_result.win_rate)
            confidence = calculate_confidence_score(win_rate, bt_result.total_trades)
        else:
            win_rate   = None   # BT未実施（表示は「-」）
            confidence = calculate_confidence_score_nobt(ind_data.get("category", "unknown"))

        # TP/SL価格計算
        if signal_type == "BUY":
            tp_price = current_price + tp_pips * 0.01
            sl_price = current_price - sl_pips * 0.01
        else:
            tp_price = current_price - tp_pips * 0.01
            sl_price = current_price + sl_pips * 0.01

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
            "signal_time": latest_candle_ts,  # シグナル発生ローソク足の確定時刻
        })

    return signals


def run_signal_engine() -> dict:
    """
    全通貨ペア・タイムフレームのシグナルを生成してDBに保存する。

    - 同じ指標・方向のシグナルが継続中なら signal_time を保持（更新しない）
    - 消えたシグナルのみ is_active=False に変更

    最適化:
    - settings は最初に1回だけ取得（15回 → 1回）
    - 既存アクティブシグナルは pair/TF ごとに1クエリで一括取得して dict 検索
      （シグナル1件ごとの SELECT → pair/TF ごとに1回のみ）

    Returns
    -------
    dict: 通貨ペアごとの生成シグナル数
    """
    from app import db
    from app.models.signal import TradingSignal
    from app.services.data_fetcher import get_candles

    # settings は1回だけ取得（ループ内で繰り返し呼ばない）
    settings = get_effective_settings()

    results = {}
    kept_ids = set()  # 今回も有効なシグナルのID

    for pair in Config.CURRENCY_PAIRS:
        results[pair] = {}
        for tf in Config.TIMEFRAMES:
            df = get_candles(pair, tf, limit=200)
            if df.empty:
                logger.warning("No data for %s %s", pair, tf)
                results[pair][tf] = 0
                continue

            signals = generate_signals_for_pair_tf(pair, tf, df, settings)
            if not signals:
                results[pair][tf] = 0
                continue

            expiry_hours = TF_EXPIRY_HOURS.get(tf, 6)
            expired_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

            # ---- pair/TF のアクティブシグナルを1クエリで一括取得 ----
            existing_list = TradingSignal.query.filter_by(
                currency_pair=pair, timeframe=tf, is_active=True
            ).all()
            # (indicator_name, signal_type) → TradingSignal のマップ
            existing_map = {(e.indicator_name, e.signal_type): e for e in existing_list}

            new_records = []
            for s in signals:
                key = (s["indicator_name"], s["signal_type"])
                existing = existing_map.get(key)

                if existing:
                    # 継続シグナル: 価格・信頼度のみ更新、signal_time は保持
                    existing.entry_price      = s["entry_price"]
                    existing.tp_price         = s["tp_price"]
                    existing.sl_price         = s["sl_price"]
                    existing.confidence_score = s["confidence_score"]
                    existing.expired_at       = expired_at
                    kept_ids.add(existing.id)
                else:
                    # 新規シグナル: signal_time = 最新ローソク足の確定時刻
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
                        expired_at=expired_at,
                    )
                    db.session.add(record)
                    new_records.append(record)

            # flush で新規レコードの ID を確定してから kept_ids に追加
            db.session.flush()
            for record in new_records:
                kept_ids.add(record.id)

            db.session.commit()
            results[pair][tf] = len(signals)
            logger.info("%s %s: %d signals generated", pair, tf, len(signals))

    # 今回生成されなかった古いシグナルを無効化
    if kept_ids:
        TradingSignal.query.filter(
            TradingSignal.is_active == True,
            TradingSignal.id.notin_(list(kept_ids)),
        ).update({"is_active": False}, synchronize_session=False)
    else:
        TradingSignal.query.filter_by(is_active=True).update({"is_active": False})
    db.session.commit()

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
