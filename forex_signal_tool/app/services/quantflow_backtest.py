"""
QuantFlow 月次バックテスト（5分足スキャルピングシミュレーション）

1hr QuantFlowスコアを方向性フィルターとして使用し、スコアが方向転換した時に
5分足でエントリーする。SL/TP/シグナル終了のいずれかで決済。

エントリー条件: |スコア| >= SCORE_THRESHOLD かつ直前と異なる方向（シグナル転換）
エントリー価格: シグナル発生直後の5m足 open
エグジット    : TP / SL / シグナル終了（方向転換または|スコア|<閾値で前足close決済）
"""

import bisect
import logging
import math
import pandas as pd

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 30
PIP_VALUE       = 0.01   # JPY ペア: 1 pip = 0.01
WARMUP          = 200    # MA200 の計算に必要


def _load_macro_close(pair: str, limit: int) -> pd.Series:
    from app.services.data_fetcher import get_candles
    dm = get_candles(pair, "1hr", limit=limit)
    if dm.empty:
        return pd.Series(dtype=float)
    return dm.set_index("timestamp")["close"].astype(float).sort_index()


def _compute_scores(df: pd.DataFrame, limit: int) -> list:
    """全 1hr 足に対して QuantFlow スコアを遡及計算して返す。"""
    from app.services.score_backtest import (
        _hybrid_us10y_rising_series, _macro_rising_series,
    )
    from app.services.usdjpy_analysis import calculate_trend_score

    close = df["close"].astype(float)
    ma20  = close.rolling(20).mean()
    ma75  = close.rolling(75).mean()
    ma200 = close.rolling(200).mean()

    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))

    ts          = df["timestamp"]
    us10y_close = _load_macro_close("US10Y", limit)
    usbf_close  = _load_macro_close("USBF",  limit)
    dxy_close   = _load_macro_close("DXY",   limit)

    us10y_s = _hybrid_us10y_rising_series(us10y_close, usbf_close, ts)
    dxy_s   = _macro_rising_series(dxy_close, ts)

    scores = []
    for i in range(len(df)):
        if i < WARMUP or math.isnan(float(ma200.iloc[i])):
            scores.append(None)
            continue
        try:
            result = calculate_trend_score(
                price_5m  = float(close.iloc[i]),
                ma20_5m   = float(ma20.iloc[i])  if not math.isnan(float(ma20.iloc[i]))  else float(close.iloc[i]),
                price_1h  = float(close.iloc[i]),
                ma75_1h   = float(ma75.iloc[i])  if not math.isnan(float(ma75.iloc[i]))  else float(close.iloc[i]),
                ma20_1h   = float(ma20.iloc[i])  if not math.isnan(float(ma20.iloc[i]))  else float(close.iloc[i]),
                ma200_1h  = float(ma200.iloc[i]) if not math.isnan(float(ma200.iloc[i])) else float(close.iloc[i]),
                rsi_14    = float(rsi.iloc[i])   if not math.isnan(float(rsi.iloc[i]))   else 50.0,
                us10y_rising = bool(us10y_s.iloc[i]),
                dxy_rising   = bool(dxy_s.iloc[i]),
            )
            scores.append(result.get("score"))
        except Exception:
            scores.append(None)

    return scores


def run_quantflow_backtest(
    pair:       str   = "USDJPY",
    sl_pips:    float = 10.0,
    tp_pips:    float = 20.0,
    limit:      int   = 5000,
    start_date: str   = "2026-01-01",
) -> dict:
    """
    5分足スキャルピングシミュレーションを実行してDBに保存する。
    既存データは保持し、最新 entry_ts より後のシグナルだけを追加する（差分実行）。

    ロジック:
    - 1hr QuantFlowスコアが閾値を超えて方向転換 → シグナル発生
    - 次の5m足openでエントリー（SL=sl_pips / TP=tp_pips）
    - TP/SLヒット または シグナル終了（方向転換・閾値割れ）で決済
    - シグナル終了時は前足closeで決済、損益をWIN/LOSSに判定
    """
    from app import db
    from app.models.quantflow_trade import QuantFlowTrade
    from app.services.data_fetcher import get_candles
    from datetime import datetime
    from sqlalchemy import func

    logger.info("QuantFlow BT (5m scalping) 開始: %s  SL=%.1f TP=%.1f  開始日=%s",
                pair, sl_pips, tp_pips, start_date)

    # 1hr足データとスコア計算
    df_1h = get_candles(pair, "1hr", limit=limit)
    if df_1h.empty or len(df_1h) < WARMUP + 10:
        return {"error": f"1hr データ不足 ({len(df_1h)} 本)"}
    df_1h = df_1h.reset_index(drop=True)

    # 5m足データ取得（1hrの約14倍で余裕を確保）
    df_5m = get_candles(pair, "5min", limit=limit * 14)
    if df_5m.empty:
        return {"error": "5分足データなし。データ取得を先に実行してください。"}
    df_5m = df_5m.reset_index(drop=True)

    def _to_naive(ts):
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        return ts

    ts_1h = [_to_naive(df_1h["timestamp"].iloc[i]) for i in range(len(df_1h))]
    ts_5m = [_to_naive(df_5m["timestamp"].iloc[i]) for i in range(len(df_5m))]

    try:
        entry_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        entry_start_dt = None

    scores = _compute_scores(df_1h, limit)

    # 既存トレードの最新 entry_ts を取得（差分実行の基準点）
    latest_entry = db.session.query(
        func.max(QuantFlowTrade.entry_ts)
    ).filter_by(currency_pair=pair).scalar()

    if latest_entry:
        logger.info("既存トレードあり（最新 entry_ts: %s UTC）。以降の差分のみ追加します。", latest_entry)
    else:
        logger.info("既存トレードなし。全件バックテストを実行します。")

    trades_to_add = []
    prev_dir = None  # 直前のシグナル方向: None / "BUY" / "SELL"

    for i in range(WARMUP, len(df_1h)):
        score = scores[i]

        # 現在の方向を判定
        if score is None or abs(score) < SCORE_THRESHOLD:
            curr_dir = None
        else:
            curr_dir = "BUY" if score > 0 else "SELL"

        # 転換なし（継続 or シグナルなし）はスキップ
        if curr_dir is None or curr_dir == prev_dir:
            prev_dir = curr_dir
            continue

        prev_dir  = curr_dir
        direction = curr_dir
        signal_start_ts = ts_1h[i]

        # start_date 以前はスキップ（スコア計算の prev_dir は更新済み）
        if entry_start_dt and signal_start_ts < entry_start_dt:
            continue

        # シグナル終了時刻を先読み（方向が変わる / スコアが閾値以下になる 1hr 足）
        signal_end_ts = None
        for j in range(i + 1, len(df_1h)):
            s = scores[j]
            if s is None or abs(s) < SCORE_THRESHOLD:
                next_dir = None
            else:
                next_dir = "BUY" if s > 0 else "SELL"
            if next_dir != direction:
                signal_end_ts = ts_1h[j]
                break

        # signal_start_ts 直後の最初の5m足でエントリー
        entry_5m_idx = bisect.bisect_right(ts_5m, signal_start_ts)
        if entry_5m_idx >= len(df_5m):
            continue

        entry_price = float(df_5m["open"].iloc[entry_5m_idx])
        entry_ts    = ts_5m[entry_5m_idx]

        # 既存DBの最新 entry_ts 以前はスキップ（prev_dir は更新済みなので状態は正しく引き継がれる）
        if latest_entry and entry_ts <= latest_entry:
            continue

        pip = PIP_VALUE
        if direction == "BUY":
            tp_price = entry_price + tp_pips * pip
            sl_price = entry_price - sl_pips * pip
        else:
            tp_price = entry_price - tp_pips * pip
            sl_price = entry_price + sl_pips * pip

        outcome     = None
        exit_price  = None
        exit_ts     = None
        profit_pips = None

        for k in range(entry_5m_idx + 1, len(df_5m)):
            ts_k = ts_5m[k]

            # シグナル終了 → 前足closeで決済
            if signal_end_ts and ts_k >= signal_end_ts:
                exit_price = float(df_5m["close"].iloc[k - 1])
                exit_ts    = ts_k
                if direction == "BUY":
                    profit_pips = round((exit_price - entry_price) / pip, 2)
                else:
                    profit_pips = round((entry_price - exit_price) / pip, 2)
                outcome = "WIN" if profit_pips > 0 else "LOSS"
                break

            high = float(df_5m["high"].iloc[k])
            low  = float(df_5m["low"].iloc[k])

            if direction == "BUY":
                hit_tp = high >= tp_price
                hit_sl = low  <= sl_price
            else:
                hit_tp = low  <= tp_price
                hit_sl = high >= sl_price

            if hit_tp and hit_sl:
                outcome = "LOSS"; exit_price = sl_price; exit_ts = ts_k
                profit_pips = -sl_pips
                break
            elif hit_tp:
                outcome = "WIN";  exit_price = tp_price; exit_ts = ts_k
                profit_pips = tp_pips
                break
            elif hit_sl:
                outcome = "LOSS"; exit_price = sl_price; exit_ts = ts_k
                profit_pips = -sl_pips
                break

        # 5m足が尽きた場合は最終足closeで決済
        if outcome is None:
            exit_price = float(df_5m["close"].iloc[-1])
            exit_ts    = ts_5m[-1]
            if direction == "BUY":
                profit_pips = round((exit_price - entry_price) / pip, 2)
            else:
                profit_pips = round((entry_price - exit_price) / pip, 2)
            outcome = "WIN" if profit_pips > 0 else "LOSS"

        year_month = entry_ts.strftime("%Y-%m")

        trades_to_add.append(QuantFlowTrade(
            currency_pair  = pair,
            year_month     = year_month,
            entry_ts       = entry_ts,
            exit_ts        = exit_ts,
            direction      = direction,
            score_at_entry = int(score),
            entry_price    = entry_price,
            exit_price     = exit_price,
            outcome        = outcome,
            profit_pips    = profit_pips,
            sl_pips        = sl_pips,
            tp_pips        = tp_pips,
        ))

    if trades_to_add:
        db.session.bulk_save_objects(trades_to_add)
        db.session.commit()

    logger.info("QuantFlow BT (5m) 完了: %d トレード追加", len(trades_to_add))
    return {"total_trades": len(trades_to_add), "pair": pair}


def get_quantflow_monthly_summary(pair: str = "USDJPY") -> list:
    """
    quantflow_trades から月別・方向別集計を返す（新しい月順）。
    各月に buy / sell / total の内訳を含む。
    """
    from app import db
    from sqlalchemy import text

    sql = text("""
        SELECT
            `year_month`,
            direction,
            COUNT(*)                                         AS total,
            SUM(outcome = 'WIN')                             AS wins,
            SUM(outcome = 'LOSS')                            AS losses,
            ROUND(SUM(outcome = 'WIN') / COUNT(*) * 100, 1) AS win_rate,
            ROUND(SUM(profit_pips), 2)                       AS total_pips,
            ROUND(AVG(profit_pips), 2)                       AS avg_pips
        FROM quantflow_trades
        WHERE currency_pair = :pair
        GROUP BY `year_month`, direction
        ORDER BY `year_month` DESC, direction ASC
    """)
    rows = db.session.execute(sql, {"pair": pair}).fetchall()

    # 月ごとにグループ化
    months: dict = {}
    for r in rows:
        ym        = r[0]
        direction = r[1]   # "BUY" or "SELL"
        stats = {
            "total":      int(r[2]),
            "wins":       int(r[3] or 0),
            "losses":     int(r[4] or 0),
            "win_rate":   float(r[5] or 0),
            "total_pips": float(r[6] or 0),
            "avg_pips":   float(r[7] or 0),
        }
        if ym not in months:
            y, m = ym.split("-")
            months[ym] = {
                "year_month": ym,
                "label":      f"{y}年{int(m):d}月",
                "buy":        None,
                "sell":       None,
            }
        if direction == "BUY":
            months[ym]["buy"] = stats
        else:
            months[ym]["sell"] = stats

    # 月合計を追加
    result = []
    for ym, d in months.items():
        buy  = d["buy"]  or {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pips": 0, "avg_pips": 0}
        sell = d["sell"] or {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pips": 0, "avg_pips": 0}
        total_t = buy["total"]  + sell["total"]
        total_w = buy["wins"]   + sell["wins"]
        total_p = round(buy["total_pips"] + sell["total_pips"], 2)
        d["total"]      = total_t
        d["wins"]       = total_w
        d["losses"]     = buy["losses"] + sell["losses"]
        d["win_rate"]   = round(total_w / total_t * 100, 1) if total_t else 0
        d["total_pips"] = total_p
        d["avg_pips"]   = round(total_p / total_t, 2) if total_t else 0
        result.append(d)

    return result
