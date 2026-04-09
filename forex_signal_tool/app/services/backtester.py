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
    sl_mode: str = "pips",
    tp_mode: str = "pips",
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
    sl_pips         : ストップロス（pips）※ sl_mode='pips' 時のみ使用
    tp_pips         : テイクプロフィット（pips）※ tp_mode='pips' 時のみ使用
    backtest_hours  : バックテスト期間（時間）
    lot_size        : ロット数（デフォルト1）
    sl_mode         : 'pips'（固定pips）または 'bb'（BBバンドタッチ）
    tp_mode         : 'pips'（固定pips）または 'bb'（BBバンドタッチ）

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

    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    capital = initial_capital
    peak_capital = initial_capital
    max_drawdown = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    trades_log = []

    # バックテスト期間内の各バーでシグナルを検出
    backtest_df = df[df["timestamp"] >= cutoff_ts].reset_index(drop=True)

    # BBバンドを事前計算（bb モード使用時）
    bb_upper_arr = bb_lower_arr = None
    if sl_mode == "bb" or tp_mode == "bb":
        _c = backtest_df["close"].astype(float)
        _m = _c.rolling(20).mean()
        _s = _c.rolling(20).std(ddof=1)
        bb_upper_arr = (_m + 2 * _s).values
        bb_lower_arr = (_m - 2 * _s).values

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
            if sl_mode == "bb" and bb_lower_arr is not None:
                bbl = bb_lower_arr[i]
                sl_price = float(bbl) if (not np.isnan(bbl) and bbl < entry_price) else entry_price - sl_pips * 0.01
            else:
                sl_price = entry_price - sl_pips * 0.01

            if tp_mode == "bb" and bb_upper_arr is not None:
                bbu = bb_upper_arr[i]
                tp_price = float(bbu) if (not np.isnan(bbu) and bbu > entry_price) else entry_price + tp_pips * 0.01
            else:
                tp_price = entry_price + tp_pips * 0.01
        else:  # SELL
            if sl_mode == "bb" and bb_upper_arr is not None:
                bbu = bb_upper_arr[i]
                sl_price = float(bbu) if (not np.isnan(bbu) and bbu > entry_price) else entry_price + sl_pips * 0.01
            else:
                sl_price = entry_price + sl_pips * 0.01

            if tp_mode == "bb" and bb_lower_arr is not None:
                bbl = bb_lower_arr[i]
                tp_price = float(bbl) if (not np.isnan(bbl) and bbl < entry_price) else entry_price - tp_pips * 0.01
            else:
                tp_price = entry_price - tp_pips * 0.01

        # トレードごとの損益額（BBモードは幅が変動するため個別計算）
        trade_sl_amount = abs(entry_price - sl_price) / 0.01 * pip_value
        trade_tp_amount = abs(tp_price - entry_price) / 0.01 * pip_value

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
            capital += trade_tp_amount
            gross_profit += trade_tp_amount
        else:
            losing_trades += 1
            capital -= trade_sl_amount
            gross_loss += trade_sl_amount

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
        "trades": trades_log,
    }


def run_all_backtests(pair: str, timeframe: str, df: pd.DataFrame,
                      initial_capital: float, sl_pips: float, tp_pips: float,
                      backtest_hours: int = 12) -> list:
    """
    全テクニカル指標のバックテストを実行し、結果リストを返す。

    実行内容:
      1. 通常バックテスト（固定 pips SL/TP） - 全指標 + 複合指標
      2. BB損切りバリアント（BBバンドタッチ SL/TP） - オシレーター + トレンド + 複合指標
         ※ 指標名に "_BBSL" サフィックスを付けて別エントリとして保存
    """
    from app.services.indicators.oscillators import calculate_oscillators
    from app.services.indicators.trend import calculate_trend
    from app.services.indicators.lines import calculate_lines
    from app.services.indicators.volatility import calculate_volatility
    from app.services.indicators.patterns import calculate_patterns
    from app.services.indicators.composite import calculate_composite

    # 通常バックテスト対象モジュール（全カテゴリ）
    indicator_modules = [
        (calculate_oscillators, "oscillator"),
        (calculate_trend, "trend"),
        (calculate_lines, "line"),
        (calculate_volatility, "volatility"),
        (calculate_patterns, "pattern"),
        (calculate_composite, "composite"),
    ]

    results = []

    # ---- 通常バックテスト（固定 pips SL/TP）----
    for func, category in indicator_modules:
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

    # ---- BB損切りバリアント（SL=BB下限, TP=BB上限）----
    bb_sl_modules = [
        (calculate_oscillators, "oscillator"),
        (calculate_trend, "trend"),
        (calculate_composite, "composite"),
    ]
    for func, category in bb_sl_modules:
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
                sl_mode="bb",
                tp_mode="bb",
            )
            if result:
                result["indicator_name"] = ind_name + "_BBSL"
                result["indicator_category"] = category + "_bbsl"
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
    from app.services.indicators.composite import calculate_composite

    indicator_map = {}
    for func in [calculate_oscillators, calculate_trend, calculate_lines,
                 calculate_volatility, calculate_patterns, calculate_composite]:
        try:
            sample = func(df.tail(50))
            for name in sample.keys():
                indicator_map[name] = func
        except Exception:
            pass

    # _BBSL サフィックスが付いている場合は BB モードで実行
    use_bb = indicator_name.endswith("_BBSL")
    lookup_name = indicator_name[:-5] if use_bb else indicator_name

    func = indicator_map.get(lookup_name)
    if func is None:
        return []

    result = run_backtest_for_indicator(
        df=df, indicator_name=lookup_name, indicator_func=func,
        pair=pair, timeframe=timeframe,
        initial_capital=initial_capital, sl_pips=sl_pips, tp_pips=tp_pips,
        backtest_hours=backtest_hours,
        sl_mode="bb" if use_bb else "pips",
        tp_mode="bb" if use_bb else "pips",
    )
    if not result:
        return []
    return result.get("trades", [])[-limit:]


def _parse_trade_dt(val):
    """entry_ts / exit_ts を datetime に変換（str / datetime 両対応）"""
    if val is None:
        return None
    if isinstance(val, str):
        for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(val[:16], fmt[:len(val[:16])])
            except ValueError:
                continue
        return None
    return val  # すでに datetime


def save_backtest_results(results: list) -> int:
    """
    バックテスト結果をDBに保存。

    - BacktestResult（集計）: 既存レコードがあれば在籍更新（ID保持）。なければ新規作成。
    - SimulationTrade（個別）: 既存トレードは保持。新規分のみ追記。重複はスキップ。
    """
    from app import db
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade

    saved = 0
    for r in results:
        pair      = r["currency_pair"]
        timeframe = r["timeframe"]
        ind_name  = r["indicator_name"]

        # ---- BacktestResult: 在籍更新（ID を変えない → FK が切れない） ----
        existing = BacktestResult.query.filter_by(
            currency_pair=pair,
            timeframe=timeframe,
            indicator_name=ind_name,
        ).all()

        if existing:
            record = existing[0]
            # 万が一重複があれば余分を削除
            for dup in existing[1:]:
                SimulationTrade.query.filter_by(backtest_result_id=dup.id).delete()
                db.session.delete(dup)
        else:
            record = BacktestResult(
                currency_pair=pair,
                timeframe=timeframe,
                indicator_name=ind_name,
            )
            db.session.add(record)

        # 集計値を最新に更新
        record.indicator_category = r.get("indicator_category")
        record.signal_direction   = "BOTH"
        record.win_rate           = r["win_rate"]
        record.total_trades       = r["total_trades"]
        record.winning_trades     = r["winning_trades"]
        record.losing_trades      = r["losing_trades"]
        record.total_profit       = r["total_profit"]
        record.initial_capital    = r["initial_capital"]
        record.final_capital      = r["final_capital"]
        record.sl_pips            = r["sl_pips"]
        record.tp_pips            = r["tp_pips"]
        record.backtest_hours     = r["backtest_hours"]
        record.max_drawdown       = r.get("max_drawdown")
        record.profit_factor      = r.get("profit_factor")
        record.calculated_at      = r["calculated_at"]

        db.session.flush()  # record.id を確定させる

        # ---- SimulationTrade: 既存キーを取得して新規分のみ挿入 ----
        existing_keys = set(
            db.session.query(SimulationTrade.entry_at, SimulationTrade.direction)
            .filter_by(currency_pair=pair, timeframe=timeframe, indicator_name=ind_name)
            .all()
        )

        sl_pips_val  = r["sl_pips"]
        tp_pips_val  = r["tp_pips"]
        prev_capital = float(r["initial_capital"])

        for t in r.get("trades", []):
            entry_ts = _parse_trade_dt(t.get("entry_ts"))
            exit_ts  = _parse_trade_dt(t.get("exit_ts"))
            direction = t.get("signal", "")

            # 既存トレードはスキップ（重複排除）
            if (entry_ts, direction) in existing_keys:
                prev_capital = float(t.get("capital_after", prev_capital))
                continue

            capital_after = float(t.get("capital_after", prev_capital))
            profit_loss   = round(capital_after - prev_capital, 2)
            prev_capital  = capital_after

            db.session.add(SimulationTrade(
                backtest_result_id=record.id,
                currency_pair=pair,
                timeframe=timeframe,
                indicator_name=ind_name,
                entry_at=entry_ts,
                exit_at=exit_ts,
                direction=direction,
                entry_price=t.get("entry_price"),
                exit_price=t.get("exit_price"),
                tp_price=t.get("tp_price"),
                sl_price=t.get("sl_price"),
                sl_pips=sl_pips_val,
                tp_pips=tp_pips_val,
                outcome=t.get("outcome"),
                profit_loss=profit_loss,
                capital_after=capital_after,
            ))
            existing_keys.add((entry_ts, direction))  # ループ内の重複も防ぐ

        saved += 1

    db.session.commit()
    return saved
