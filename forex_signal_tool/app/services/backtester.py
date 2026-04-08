"""
バックテストエンジン

ロジック:
  1. 直近N時間のローソク足データを取得
  2. 各テクニカル指標のシグナル発生タイミングを特定
  3. シグナル発生後にTP/SLのどちらを先に達成したかを判定
  4. 勝率・損益・ドローダウンを計算してDBに保存
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import numpy as np

from app.config import Config

logger = logging.getLogger(__name__)


def _get_pip_value(pair: str) -> float:
    """JPYペアの1pip値 (標準ロット1本あたり)"""
    return Config.JPY_PAIR_PIP_VALUE


def _price_to_pips(price_diff: float, pair: str = "USDJPY") -> float:
    """価格差をpipsに変換 (JPYペア: 1pip=0.01)"""
    return price_diff / 0.01


def run_backtest_for_indicator(
    df: pd.DataFrame,
    indicator_name: str,
    indicator_func,
    pair: str,
    timeframe: str,
    initial_capital: float,
    sl_pips: float,
    tp_pips: float,
    backtest_hours: int = 12,
    lot_size: int = 1,
) -> Optional[dict]:
    """
    単一指標のバックテストを実行する。

    Parameters
    ----------
    df              : 全ローソク足データ（時系列順）
    indicator_name  : 指標名
    indicator_func  : 指標計算関数 (df -> dict)
    pair            : 通貨ペア
    timeframe       : タイムフレーム
    initial_capital : 初期資金（円）
    sl_pips         : ストップロス（pips）
    tp_pips         : テイクプロフィット（pips）
    backtest_hours  : バックテスト期間（時間）
    lot_size        : ロット数（デフォルト1）

    Returns
    -------
    dict: バックテスト結果
    """
    if df.empty or len(df) < 30:
        return None

    # バックテスト期間を計算（DBはtz-naiveで保存されているためnaiveで統一）
    latest_ts = df["timestamp"].max()
    if hasattr(latest_ts, "to_pydatetime"):
        latest_ts = latest_ts.to_pydatetime()
    if latest_ts.tzinfo is not None:
        latest_ts = latest_ts.replace(tzinfo=None)
    cutoff_ts = latest_ts - timedelta(hours=backtest_hours)

    pip_value = _get_pip_value(pair) * lot_size
    sl_amount = sl_pips * pip_value   # 1トレードあたりの損失額
    tp_amount = tp_pips * pip_value   # 1トレードあたりの利益額

    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    capital = initial_capital
    peak_capital = initial_capital
    max_drawdown = 0.0
    trades_log = []

    buy_signals = []
    sell_signals = []

    # バックテスト期間内の各バーでシグナルを検出
    backtest_df = df[df["timestamp"] >= cutoff_ts].reset_index(drop=True)

    for i in range(30, len(backtest_df)):
        # 過去30本でシグナル計算
        window = backtest_df.iloc[max(0, i - 100):i].copy()
        if len(window) < 30:
            continue

        try:
            indicator_result = indicator_func(window)
        except Exception as exc:
            logger.debug("Indicator error at %d: %s", i, exc)
            continue

        ind_data = indicator_result.get(indicator_name, {})
        signal = ind_data.get("signal", "NEUTRAL")

        if signal == "NEUTRAL":
            continue

        # シグナル発生バーの情報
        entry_bar = backtest_df.iloc[i]
        entry_price = float(entry_bar["close"])
        entry_ts = entry_bar["timestamp"]

        # TP/SL価格を計算
        if signal == "BUY":
            tp_price = entry_price + tp_pips * 0.01
            sl_price = entry_price - sl_pips * 0.01
        else:  # SELL
            tp_price = entry_price - tp_pips * 0.01
            sl_price = entry_price + sl_pips * 0.01

        # 以降のバーでTP/SL到達を確認
        outcome = None
        exit_price = None
        exit_ts = None
        for j in range(i + 1, min(i + 200, len(backtest_df))):
            future_bar = backtest_df.iloc[j]
            fh = float(future_bar["high"])
            fl = float(future_bar["low"])

            if signal == "BUY":
                if fh >= tp_price:
                    outcome = "WIN"
                    exit_price = tp_price
                    exit_ts = future_bar["timestamp"]
                    break
                if fl <= sl_price:
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    break
            else:  # SELL
                if fl <= tp_price:
                    outcome = "WIN"
                    exit_price = tp_price
                    exit_ts = future_bar["timestamp"]
                    break
                if fh >= sl_price:
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    break

        if outcome is None:
            continue  # 未決済は除外

        total_trades += 1
        if outcome == "WIN":
            winning_trades += 1
            capital += tp_amount
        else:
            losing_trades += 1
            capital -= sl_amount

        # ドローダウン計算
        peak_capital = max(peak_capital, capital)
        drawdown = peak_capital - capital
        max_drawdown = max(max_drawdown, drawdown)

        trades_log.append({
            "entry_ts": entry_ts,
            "exit_ts": exit_ts,
            "signal": signal,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "outcome": outcome,
            "capital_after": capital,
        })

    if total_trades == 0:
        return None

    win_rate = (winning_trades / total_trades) * 100
    total_profit = capital - initial_capital

    # プロフィットファクター
    gross_profit = winning_trades * tp_amount
    gross_loss = losing_trades * sl_amount
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    return {
        "currency_pair": pair,
        "timeframe": timeframe,
        "indicator_name": indicator_name,
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_profit": round(total_profit, 0),
        "initial_capital": initial_capital,
        "final_capital": round(capital, 0),
        "sl_pips": sl_pips,
        "tp_pips": tp_pips,
        "backtest_hours": backtest_hours,
        "max_drawdown": round(max_drawdown, 0),
        "profit_factor": round(profit_factor, 4),
        "calculated_at": datetime.now(timezone.utc),
        "trades": trades_log,   # チャート表示用
    }


def run_all_backtests(pair: str, timeframe: str, df: pd.DataFrame,
                      initial_capital: float, sl_pips: float, tp_pips: float,
                      backtest_hours: int = 12) -> list:
    """
    全テクニカル指標のバックテストを実行し、結果リストを返す。
    """
    from app.services.indicators.oscillators import calculate_oscillators
    from app.services.indicators.trend import calculate_trend
    from app.services.indicators.lines import calculate_lines
    from app.services.indicators.volatility import calculate_volatility
    from app.services.indicators.patterns import calculate_patterns

    # 各カテゴリの計算関数
    indicator_modules = [
        (calculate_oscillators, "oscillator"),
        (calculate_trend, "trend"),
        (calculate_lines, "line"),
        (calculate_volatility, "volatility"),
        (calculate_patterns, "pattern"),
    ]

    results = []

    for func, category in indicator_modules:
        # このモジュールがサポートする指標名を取得
        try:
            sample = func(df.tail(50))
        except Exception:
            continue

        for ind_name in sample.keys():
            result = run_backtest_for_indicator(
                df=df,
                indicator_name=ind_name,
                indicator_func=func,
                pair=pair,
                timeframe=timeframe,
                initial_capital=initial_capital,
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                backtest_hours=backtest_hours,
            )
            if result:
                result["indicator_category"] = category
                results.append(result)

    return results


def get_recent_trades(pair: str, timeframe: str, df: pd.DataFrame,
                      indicator_name: str, initial_capital: float,
                      sl_pips: float, tp_pips: float,
                      backtest_hours: int = 12, limit: int = 30) -> list:
    """
    指定インジケーターの直近取引ログを返す（チャート表示用）。
    """
    from app.services.indicators.oscillators import calculate_oscillators
    from app.services.indicators.trend import calculate_trend
    from app.services.indicators.lines import calculate_lines
    from app.services.indicators.volatility import calculate_volatility
    from app.services.indicators.patterns import calculate_patterns

    indicator_map = {}
    for func in [calculate_oscillators, calculate_trend, calculate_lines,
                 calculate_volatility, calculate_patterns]:
        try:
            sample = func(df.tail(50))
            for name in sample.keys():
                indicator_map[name] = func
        except Exception:
            pass

    func = indicator_map.get(indicator_name)
    if func is None:
        return []

    result = run_backtest_for_indicator(
        df=df, indicator_name=indicator_name, indicator_func=func,
        pair=pair, timeframe=timeframe,
        initial_capital=initial_capital, sl_pips=sl_pips, tp_pips=tp_pips,
        backtest_hours=backtest_hours,
    )
    if not result:
        return []
    return result.get("trades", [])[-limit:]


def save_backtest_results(results: list) -> int:
    """バックテスト結果をDBに保存（同一指標の古い結果は上書き）。個別トレードも保存する。"""
    from app import db
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade

    saved = 0
    for r in results:
        pair     = r["currency_pair"]
        timeframe = r["timeframe"]
        ind_name  = r["indicator_name"]

        # 既存レコードをすべて削除（重複していても一括削除）
        old_records = BacktestResult.query.filter_by(
            currency_pair=pair,
            timeframe=timeframe,
            indicator_name=ind_name,
        ).all()
        for old in old_records:
            SimulationTrade.query.filter_by(backtest_result_id=old.id).delete()
            db.session.delete(old)

        record = BacktestResult(
            currency_pair=pair,
            timeframe=timeframe,
            indicator_name=ind_name,
            indicator_category=r.get("indicator_category"),
            signal_direction="BOTH",
            win_rate=r["win_rate"],
            total_trades=r["total_trades"],
            winning_trades=r["winning_trades"],
            losing_trades=r["losing_trades"],
            total_profit=r["total_profit"],
            initial_capital=r["initial_capital"],
            final_capital=r["final_capital"],
            sl_pips=r["sl_pips"],
            tp_pips=r["tp_pips"],
            backtest_hours=r["backtest_hours"],
            max_drawdown=r.get("max_drawdown"),
            profit_factor=r.get("profit_factor"),
            calculated_at=r["calculated_at"],
        )
        db.session.add(record)
        db.session.flush()  # record.id を確定させる

        # 個別トレードを保存
        sl_pips_val = r["sl_pips"]
        tp_pips_val = r["tp_pips"]
        initial_cap = r["initial_capital"]
        prev_capital = initial_cap

        for t in r.get("trades", []):
            entry_ts = t.get("entry_ts")
            exit_ts  = t.get("exit_ts")

            # datetime でない場合は変換
            if isinstance(entry_ts, str):
                try:
                    entry_ts = datetime.strptime(entry_ts[:16], "%Y/%m/%d %H:%M")
                except ValueError:
                    entry_ts = None
            if isinstance(exit_ts, str):
                try:
                    exit_ts = datetime.strptime(exit_ts[:16], "%Y/%m/%d %H:%M")
                except ValueError:
                    exit_ts = None

            capital_after = float(t.get("capital_after", prev_capital))
            profit_loss   = round(capital_after - prev_capital, 2)
            prev_capital  = capital_after

            trade = SimulationTrade(
                backtest_result_id=record.id,
                currency_pair=pair,
                timeframe=timeframe,
                indicator_name=ind_name,
                entry_at=entry_ts,
                exit_at=exit_ts,
                direction=t.get("signal", ""),
                entry_price=t.get("entry_price"),
                exit_price=t.get("exit_price"),
                tp_price=t.get("tp_price"),
                sl_price=t.get("sl_price"),
                sl_pips=sl_pips_val,
                tp_pips=tp_pips_val,
                outcome=t.get("outcome"),
                profit_loss=profit_loss,
                capital_after=capital_after,
            )
            db.session.add(trade)

        saved += 1

    db.session.commit()
    return saved
