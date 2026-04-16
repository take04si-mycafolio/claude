"""
バックテストエンジン (v1 — 単一テクニカル指標専用)

ロジック:
  1. 直近N時間のローソク足データを取得
  2. 各テクニカル指標のシグナル発生タイミングを特定
  3. シグナル発生後にTP/SLのどちらを先に達成したかを判定
  4. 勝率・損益・ドローダウンを計算してDBに保存

NOTE (Phase 1):
  マルチ条件バックテストは backtest_engine.py / backtest_v2.py を使用すること。
  このモジュール (v1) はランキングシステム専用のまま維持する。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import numpy as np

from app.config import Config

logger = logging.getLogger(__name__)

# SimulationTrade の指標あたり最大保存件数
TRADE_LIMIT_PER_INDICATOR = 300


def _calc_score(win_rate: float, profit_factor: float, total_trades: int,
                sl_pips: float, tp_pips: float, max_drawdown: float) -> int:
    """
    100点満点スコア計算（フロントエンドJS / run_ranking_bt.py と同一ロジック）
    将来の「今日の勝率」「ランキング変動」表示に利用する。
    """
    dd_pct = (abs(max_drawdown) / 1_000_000) * 100
    ev = (win_rate / 100) * tp_pips - (1 - win_rate / 100) * sl_pips

    if   win_rate >= 60: wr_s = 30
    elif win_rate >= 58: wr_s = 27
    elif win_rate >= 56: wr_s = 24
    elif win_rate >= 54: wr_s = 20
    elif win_rate >= 52: wr_s = 16
    elif win_rate >= 50: wr_s = 12
    else:                wr_s = max(0, int(win_rate / 50 * 8))

    if   profit_factor >= 1.50: pf_s = 25
    elif profit_factor >= 1.40: pf_s = 22
    elif profit_factor >= 1.30: pf_s = 18
    elif profit_factor >= 1.20: pf_s = 14
    elif profit_factor >= 1.10: pf_s = 10
    elif profit_factor >= 1.00: pf_s = 6
    else:                       pf_s = 0

    if   dd_pct <  5: dd_s = 20
    elif dd_pct <  8: dd_s = 17
    elif dd_pct < 12: dd_s = 14
    elif dd_pct < 16: dd_s = 10
    elif dd_pct < 20: dd_s = 6
    else:             dd_s = 2

    if   total_trades >= 500: n_s = 15
    elif total_trades >= 300: n_s = 12
    elif total_trades >= 150: n_s = 9
    elif total_trades >= 80:  n_s = 6
    elif total_trades >= 30:  n_s = 3
    else:                     n_s = 0

    if   ev >  5: ev_s = 10
    elif ev >  2: ev_s = 8
    elif ev >  0: ev_s = 6
    elif ev > -2: ev_s = 3
    else:         ev_s = 0

    return wr_s + pf_s + dd_s + n_s + ev_s


def _get_pip_value(pair: str) -> float:
    """JPYペアの1pip値 (標準ロット1本あたり)"""
    return Config.JPY_PAIR_PIP_VALUE


def _price_to_pips(price_diff: float, pair: str = "USDJPY") -> float:
    """価格差をpipsに変換 (JPYペア: 1pip=0.01)"""
    return price_diff / 0.01


def _precompute_all_signals(df: pd.DataFrame) -> dict:
    """
    全指標の全バーシグナルをベクトル計算で一括取得。
    バーごとに indicator_func を呼ぶ O(n²) を O(n) に削減する。

    Returns: {indicator_name: np.ndarray of "BUY"/"SELL"/"NEUTRAL" strings}
    """
    if len(df) < 50:
        return {}

    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    open_  = df["open"].astype(float)
    n      = len(df)

    def _arr(buy_mask, sell_mask, nan_mask=None):
        s = np.full(n, "NEUTRAL", dtype=object)
        bm = buy_mask.values  if hasattr(buy_mask,  "values") else np.asarray(buy_mask)
        sm = sell_mask.values if hasattr(sell_mask, "values") else np.asarray(sell_mask)
        s[np.nan_to_num(bm.astype(float), nan=0).astype(bool)] = "BUY"
        s[np.nan_to_num(sm.astype(float), nan=0).astype(bool)] = "SELL"
        if nan_mask is not None:
            nm = nan_mask.values if hasattr(nan_mask, "values") else np.asarray(nan_mask)
            s[np.nan_to_num(nm.astype(float), nan=1).astype(bool)] = "NEUTRAL"
        return s

    result = {}

    # ===== OSCILLATORS =====
    delta    = close.diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rsi      = 100 - 100 / (1 + avg_gain / avg_loss.replace(0, np.nan))
    result["RSI_14"] = _arr(rsi < 30, rsi > 70, rsi.isna())

    ema12     = close.ewm(span=12, adjust=False).mean()
    ema26     = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sig_line  = macd_line.ewm(span=9, adjust=False).mean()
    hist      = macd_line - sig_line
    prev_hist = hist.shift(1).fillna(0)
    cx_buy    = (hist > 0) & (prev_hist <= 0)
    cx_sell   = (hist < 0) & (prev_hist >= 0)
    result["MACD_12_26_9"] = _arr(
        cx_buy  | ((macd_line > sig_line) & ~cx_sell),
        cx_sell | ((macd_line < sig_line) & ~cx_buy),
        macd_line.isna() | sig_line.isna(),
    )

    lo14    = low.rolling(14).min()
    hi14    = high.rolling(14).max()
    sk_raw  = 100 * (close - lo14) / (hi14 - lo14).replace(0, np.nan)
    stoch_k = sk_raw.rolling(3).mean()
    stoch_d = stoch_k.rolling(3).mean()
    result["Stochastic_14_3"] = _arr(
        (stoch_k < 20) & (stoch_d < 20) & (stoch_k > stoch_d),
        (stoch_k > 80) & (stoch_d > 80) & (stoch_k < stoch_d),
        stoch_k.isna() | stoch_d.isna(),
    )

    tp_s  = (high + low + close) / 3
    sma_tp = tp_s.rolling(20).mean()
    mad    = tp_s.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci    = (tp_s - sma_tp) / (0.015 * mad)
    pc     = cci.shift(1).fillna(0)
    e_buy  = cci < -100;  e_sell = cci > 100
    z_buy  = (cci > 0) & (pc <= 0) & ~e_buy & ~e_sell
    z_sell = (cci < 0) & (pc >= 0) & ~e_buy & ~e_sell
    result["CCI_20"] = _arr(e_buy | z_buy, e_sell | z_sell, cci.isna())

    hi14w = high.rolling(14).max(); lo14w = low.rolling(14).min()
    wr = -100 * (hi14w - close) / (hi14w - lo14w).replace(0, np.nan)
    result["Williams_R_14"] = _arr(wr < -80, wr > -20, wr.isna())

    # ===== TREND =====
    sma20 = close.rolling(20).mean(); sma50 = close.rolling(50).mean()
    ema9  = close.ewm(span=9,  adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std(ddof=1)
    bb_upper = bb_mid + 2 * bb_std; bb_lower = bb_mid - 2 * bb_std

    s20 = np.full(n, "NEUTRAL", dtype=object)
    s20[close > sma20] = "BUY"; s20[close < sma20] = "SELL"
    s20[sma20.isna()] = "NEUTRAL"
    result["SMA_20"] = s20

    s50 = np.full(n, "NEUTRAL", dtype=object)
    s50[close > sma50] = "BUY"; s50[close < sma50] = "SELL"
    s50[sma50.isna()] = "NEUTRAL"
    result["SMA_50"] = s50

    p20 = sma20.shift(1); p50 = sma50.shift(1)
    sc  = np.full(n, "NEUTRAL", dtype=object)
    sc[sma20 > sma50] = "BUY"; sc[sma20 < sma50] = "SELL"
    sc[(sma20 > sma50) & (p20 <= p50)] = "BUY"
    sc[(sma20 < sma50) & (p20 >= p50)] = "SELL"
    sc[sma20.isna() | sma50.isna()] = "NEUTRAL"
    result["SMA_Cross_20_50"] = sc

    ec = np.full(n, "NEUTRAL", dtype=object)
    ec[ema9 > ema21] = "BUY"; ec[ema9 < ema21] = "SELL"
    result["EMA_Cross_9_21"] = ec

    e21 = np.full(n, "NEUTRAL", dtype=object)
    e21[close > ema21] = "BUY"; e21[close < ema21] = "SELL"
    result["EMA_21"] = e21

    bb_s = np.full(n, "NEUTRAL", dtype=object)
    bb_s[close < bb_mid] = "BUY"; bb_s[close > bb_mid] = "SELL"
    bb_s[close <= bb_lower] = "BUY"; bb_s[close >= bb_upper] = "SELL"
    bb_s[bb_mid.isna()] = "NEUTRAL"
    result["BollingerBands_20_2"] = bb_s

    bb_w   = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
    w_sma  = bb_w.rolling(20).mean()
    sq     = bb_w < (w_sma * 0.8)
    sq_s   = np.full(n, "NEUTRAL", dtype=object)
    sq_s[(sq) & (close > bb_mid)] = "BUY"
    sq_s[(sq) & (close < bb_mid)] = "SELL"
    sq_s[w_sma.isna()] = "NEUTRAL"
    result["BB_Squeeze"] = sq_s

    tenkan  = (high.rolling(9).max()  + low.rolling(9).min())  / 2
    kijun   = (high.rolling(26).max() + low.rolling(26).min()) / 2
    sa      = ((tenkan + kijun) / 2).shift(26)
    sb      = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    ctop    = pd.concat([sa, sb], axis=1).max(axis=1)
    cbot    = pd.concat([sa, sb], axis=1).min(axis=1)
    ichi    = np.full(n, "NEUTRAL", dtype=object)
    ichi[(close > ctop) & (tenkan >= kijun)] = "BUY"
    ichi[(close < cbot) & (tenkan <  kijun)] = "SELL"
    ichi[ctop.isna()] = "NEUTRAL"
    result["Ichimoku_Cloud"] = ichi

    # ===== VOLATILITY =====
    pc2  = close.shift(1)
    tr   = pd.concat([high - low, (high - pc2).abs(), (low - pc2).abs()], axis=1).max(axis=1)
    atr  = tr.ewm(span=14, adjust=False).mean()
    asma = atr.rolling(20).mean()
    s10  = close.rolling(10).mean()
    av_s = np.full(n, "NEUTRAL", dtype=object)
    hv   = atr > asma * 1.2
    av_s[hv & (close > s10)] = "BUY"
    av_s[hv & (close < s10)] = "SELL"
    av_s[asma.isna()] = "NEUTRAL"
    result["ATR_14"] = av_s

    vi_s = np.full(n, "NEUTRAL", dtype=object)
    lv   = bb_w < (w_sma * 0.7)
    vi_s[lv & (close > bb_mid)] = "BUY"
    vi_s[lv & (close < bb_mid)] = "SELL"
    vi_s[w_sma.isna()] = "NEUTRAL"
    result["Volatility_Index"] = vi_s

    # ===== LINES =====
    ph = high.shift(1); pl = low.shift(1); pclose = close.shift(1)
    piv = (ph + pl + pclose) / 3
    r1  = 2 * piv - pl;  s1 = 2 * piv - ph
    piv_s = np.full(n, "NEUTRAL", dtype=object)
    piv_s[close > r1] = "BUY"; piv_s[close < s1] = "SELL"
    mid_m = (close <= r1) & (close >= s1)
    piv_s[mid_m & (close >= piv)] = "BUY"
    piv_s[mid_m & (close <  piv)] = "SELL"
    piv_s[piv.isna()] = "NEUTRAL"
    result["Pivot_Classic"] = piv_s

    rh20 = high.rolling(20).max(); rl20 = low.rolling(20).min()
    rng20 = rh20 - rl20
    fib5  = rh20 - rng20 * 0.5
    fib_s = np.full(n, "NEUTRAL", dtype=object)
    fib_s[close > fib5] = "BUY"; fib_s[close < fib5] = "SELL"
    fib_s[rng20.isna() | (rng20 == 0)] = "NEUTRAL"
    result["Fibonacci_Retracement"] = fib_s

    rh = high.rolling(20).max(); rl = low.rolling(20).min()
    rng_sr = (rh - rl).replace(0, np.nan)
    d_h = (rh - close) / rng_sr; d_l = (close - rl) / rng_sr
    sr_s = np.full(n, "NEUTRAL", dtype=object)
    sr_s[d_l < d_h] = "BUY"; sr_s[d_h < d_l] = "SELL"
    sr_s[rng_sr.isna()] = "NEUTRAL"
    result["Support_Resistance"] = sr_s

    # ===== PATTERNS =====
    body  = (close - open_).abs()
    upper = high  - pd.concat([open_, close], axis=1).max(axis=1)
    lower = pd.concat([open_, close], axis=1).min(axis=1) - low
    rng   = high - low
    tup   = close > close.shift(10)   # 10本前より上 = 上昇トレンド

    result["Hammer"]           = _arr(
        (body > 0) & (lower >= body * 2) & (upper <= body * 0.3) & ~tup, pd.Series(False, index=df.index))
    result["Inverted_Hammer"]  = _arr(
        pd.Series(False, index=df.index),
        (body > 0) & (upper >= body * 2) & (lower <= body * 0.3) & tup)
    is_doji = (rng > 0) & (body / rng.replace(0, np.nan) < 0.1)
    result["Doji"]             = _arr(is_doji & ~tup, is_doji & tup)

    po2 = open_.shift(1); pc2b = close.shift(1)
    bull_e = (pc2b < po2) & (close > open_) & (open_ < pc2b) & (close > po2)
    bear_e = (pc2b > po2) & (close < open_) & (open_ > pc2b) & (close < po2)
    result["Bullish_Engulfing"] = _arr(bull_e.fillna(False), pd.Series(False, index=df.index))
    result["Bearish_Engulfing"] = _arr(pd.Series(False, index=df.index), bear_e.fillna(False))

    str_bull = (close > open_) & (rng > 0) & ((close - open_) / rng.replace(0, np.nan) >= 0.6)
    str_bear = (close < open_) & (rng > 0) & ((open_ - close) / rng.replace(0, np.nan) >= 0.6)
    rising   = (close > close.shift(1)) & (close.shift(1) > close.shift(2))
    falling  = (close < close.shift(1)) & (close.shift(1) < close.shift(2))
    tws = str_bull & str_bull.shift(1).fillna(False) & str_bull.shift(2).fillna(False) & rising.fillna(False)
    tbc = str_bear & str_bear.shift(1).fillna(False) & str_bear.shift(2).fillna(False) & falling.fillna(False)
    result["Three_White_Soldiers"] = _arr(tws.fillna(False), pd.Series(False, index=df.index))
    result["Three_Black_Crows"]    = _arr(pd.Series(False, index=df.index), tbc.fillna(False))

    is_bp = (rng > 0) & (lower >= rng * 0.6) & (body <= rng * 0.3)
    is_sp = (rng > 0) & (upper >= rng * 0.6) & (body <= rng * 0.3)
    result["Pin_Bar"] = _arr(is_bp & ~is_sp, is_sp & ~is_bp)

    # ===== COMPOSITE =====
    rsi_s   = result["RSI_14"]
    macd_s  = result["MACD_12_26_9"]
    stoch_s = result["Stochastic_14_3"]

    result["RSI_MACD_Combo"]   = _arr((rsi_s == "BUY") & (macd_s == "BUY"),
                                      (rsi_s == "SELL") & (macd_s == "SELL"))
    result["RSI_Stoch_Combo"]  = _arr((rsi_s == "BUY") & (stoch_s == "BUY"),
                                      (rsi_s == "SELL") & (stoch_s == "SELL"))
    result["MACD_Stoch_Combo"] = _arr((macd_s == "BUY") & (stoch_s == "BUY"),
                                      (macd_s == "SELL") & (stoch_s == "SELL"))
    result["Triple_OSC_Combo"] = _arr(
        (rsi_s == "BUY") & (macd_s == "BUY") & (stoch_s == "BUY"),
        (rsi_s == "SELL") & (macd_s == "SELL") & (stoch_s == "SELL"),
    )

    consensus_inds = [rsi_s, macd_s, stoch_s,
                      result["CCI_20"], result["Williams_R_14"],
                      result["SMA_20"], result["EMA_Cross_9_21"],
                      result["BollingerBands_20_2"]]
    buy_cnt  = sum((s == "BUY").astype(int)  for s in consensus_inds)
    sell_cnt = sum((s == "SELL").astype(int) for s in consensus_inds)
    result["All_AND_Consensus"] = _arr(buy_cnt >= 5, sell_cnt >= 5)

    return result


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
    precomputed_signals: Optional[np.ndarray] = None,
    incremental_from_ts=None,
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

    prev_signal = "NEUTRAL"  # 前バーのシグナル（重複エントリー防止）
    skip_until  = -1          # トレード中はこのバーインデックスまでスキップ

    for i in range(30, len(backtest_df)):
        # トレード保有中のバーはスキップ（決済バーの次から再判断）
        if i <= skip_until:
            prev_signal = "NEUTRAL"
            continue

        # シグナル取得: 事前計算済み配列 (O(1)) or バーごと計算 (O(window))
        if precomputed_signals is not None:
            signal = precomputed_signals[i] if i < len(precomputed_signals) else "NEUTRAL"
        else:
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
            prev_signal = "NEUTRAL"
            continue

        # 前バーと同じシグナルが継続している場合はエントリーしない
        # （NEUTRAL→BUY/SELL へ転換した最初のバーのみエントリー）
        if signal == prev_signal:
            continue
        prev_signal = signal

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
        exit_bar_idx = min(i + 200, len(backtest_df)) - 1  # 未決済時の最大スキップ先
        for j in range(i + 1, min(i + 200, len(backtest_df))):
            future_bar = backtest_df.iloc[j]
            fh = float(future_bar["high"])
            fl = float(future_bar["low"])

            if signal == "BUY":
                sl_hit = fl <= sl_price
                tp_hit = fh >= tp_price
                if sl_hit and tp_hit:
                    # 同一バーで両到達 → SL優先（v2エンジンと統一・保守的評価）
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break
                elif tp_hit:
                    outcome = "WIN"
                    exit_price = tp_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break
                elif sl_hit:
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break
            else:  # SELL
                sl_hit = fh >= sl_price
                tp_hit = fl <= tp_price
                if sl_hit and tp_hit:
                    # 同一バーで両到達 → SL優先（v2エンジンと統一・保守的評価）
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break
                elif tp_hit:
                    outcome = "WIN"
                    exit_price = tp_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break
                elif sl_hit:
                    outcome = "LOSS"
                    exit_price = sl_price
                    exit_ts = future_bar["timestamp"]
                    exit_bar_idx = j
                    break

        # 決済バーまでの間は新規エントリーしない（未決済でも同様）
        skip_until = exit_bar_idx

        if outcome is None:
            continue  # 未決済は除外

        total_trades += 1
        if outcome == "WIN":
            winning_trades += 1
            trade_pl = trade_tp_amount
            capital += trade_pl
            gross_profit += trade_pl
        else:
            losing_trades += 1
            trade_pl = -trade_sl_amount
            capital -= trade_sl_amount
            gross_loss += trade_sl_amount

        # ドローダウン計算
        peak_capital = max(peak_capital, capital)
        drawdown = peak_capital - capital
        max_drawdown = max(max_drawdown, drawdown)

        # インクリメンタルモード: incremental_from_ts 以降のトレードのみ記録
        # 全バーの統計（total_trades 等）は引き続き計算することで capital_after の精度を保つ
        entry_ts_dt = entry_ts.to_pydatetime() if hasattr(entry_ts, "to_pydatetime") else entry_ts
        if incremental_from_ts is None or entry_ts_dt > incremental_from_ts:
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
                "profit_loss": trade_pl,
            })

    if total_trades == 0:
        return None

    # インクリメンタルモード: 新規トレードがなければスキップ
    if incremental_from_ts is not None and not trades_log:
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
                      backtest_hours: int = 12,
                      incremental_from_ts=None) -> list:
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

    # 全指標のシグナルを一括事前計算（O(n) × 指標数）
    # これにより run_backtest_for_indicator 内のバーごと計算（O(n²)）を回避する
    try:
        precomputed = _precompute_all_signals(df)
        logger.debug("シグナル事前計算完了: %d指標", len(precomputed))
    except Exception as e:
        logger.warning("シグナル事前計算失敗（フォールバック）: %s", e)
        precomputed = {}

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
                precomputed_signals=precomputed.get(ind_name),
                incremental_from_ts=incremental_from_ts,
            )
            if result:
                result["indicator_category"] = category
                results.append(result)

    # ---- BB損切りバリアント（SL=BB下限, TP=BB上限）----
    # BBSLはシグナルロジックは通常と同じ（SL/TP計算のみ異なる）→ 同じ事前計算を再利用
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
                precomputed_signals=precomputed.get(ind_name),
                incremental_from_ts=incremental_from_ts,
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


def _recompute_stats_from_db(pair: str, tf: str, ind_name: str, initial_capital: float) -> Optional[dict]:
    """
    simulation_trades テーブルの全データから集計統計を再計算する。
    インクリメンタルバックテスト後に BacktestResult を全履歴ベースで更新するために使用。
    """
    from app.models.simulation_trade import SimulationTrade

    trades = (SimulationTrade.query
              .filter_by(currency_pair=pair, timeframe=tf, indicator_name=ind_name)
              .order_by(SimulationTrade.entry_at)
              .all())

    if not trades:
        return None

    total  = len(trades)
    wins   = sum(1 for t in trades if t.outcome == "WIN")
    losses = total - wins

    gross_profit = sum(float(t.profit_loss) for t in trades if t.profit_loss and float(t.profit_loss) > 0)
    gross_loss   = abs(sum(float(t.profit_loss) for t in trades if t.profit_loss and float(t.profit_loss) < 0))
    win_rate      = (wins / total) * 100
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
    total_profit  = sum(float(t.profit_loss) for t in trades if t.profit_loss)

    peak  = initial_capital
    max_dd = 0.0
    for t in trades:
        if t.capital_after is not None:
            c = float(t.capital_after)
            peak   = max(peak, c)
            max_dd = max(max_dd, peak - c)

    last_cap = (float(trades[-1].capital_after) if trades[-1].capital_after is not None
                else initial_capital + total_profit)

    return {
        "total_trades":   total,
        "winning_trades": wins,
        "losing_trades":  losses,
        "win_rate":       round(win_rate, 2),
        "profit_factor":  round(profit_factor, 4),
        "total_profit":   round(total_profit, 0),
        "max_drawdown":   round(max_dd, 0),
        "final_capital":  round(last_cap, 0),
    }


def save_backtest_results(results: list, recompute_stats: bool = False) -> int:
    """
    バックテスト結果をDBに保存。

    - BacktestResult（集計）: 既存レコードがあれば在籍更新（ID保持）。なければ新規作成。
    - SimulationTrade（個別）: 既存トレードは保持。新規分のみ追記。重複はスキップ。
    - recompute_stats=True の場合、保存後に DB 全データから統計を再計算（インクリメンタル用）。
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

        sl_pips_preset = r["sl_pips"]
        tp_pips_preset = r["tp_pips"]
        prev_capital   = float(r["initial_capital"])

        for t in r.get("trades", []):
            entry_ts = _parse_trade_dt(t.get("entry_ts"))
            exit_ts  = _parse_trade_dt(t.get("exit_ts"))
            direction = t.get("signal", "")

            # 既存トレードはスキップ（重複排除）
            if (entry_ts, direction) in existing_keys:
                prev_capital = float(t.get("capital_after", prev_capital))
                continue

            capital_after = float(t.get("capital_after", prev_capital))
            # profit_loss が直接提供されている場合（インクリメンタルモード）はそれを使用
            if t.get("profit_loss") is not None:
                profit_loss = round(float(t["profit_loss"]), 2)
            else:
                profit_loss = round(capital_after - prev_capital, 2)
            prev_capital  = capital_after

            # 実際の価格差からpipsを計算（BBモードで変動するケースに対応）
            _ep  = float(t.get("entry_price") or 0)
            _tpp = t.get("tp_price")
            _slp = t.get("sl_price")
            actual_tp_pips = round(abs(float(_tpp) - _ep) / 0.01, 2) if _tpp and _ep else tp_pips_preset
            actual_sl_pips = round(abs(_ep - float(_slp)) / 0.01, 2) if _slp and _ep else sl_pips_preset

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
                sl_pips=actual_sl_pips,
                tp_pips=actual_tp_pips,
                outcome=t.get("outcome"),
                profit_loss=profit_loss,
                capital_after=capital_after,
            ))
            existing_keys.add((entry_ts, direction))  # ループ内の重複も防ぐ

        saved += 1

    db.session.commit()

    # ---- SimulationTrade を TRADE_LIMIT_PER_INDICATOR 件以内に制限 ----
    from sqlalchemy import func as sa_func
    for r in results:
        pair      = r["currency_pair"]
        tf        = r["timeframe"]
        ind_name  = r["indicator_name"]

        total = db.session.query(sa_func.count(SimulationTrade.id)).filter_by(
            currency_pair=pair, timeframe=tf, indicator_name=ind_name
        ).scalar() or 0

        if total > TRADE_LIMIT_PER_INDICATOR:
            keep_ids = [
                row[0] for row in
                db.session.query(SimulationTrade.id).filter_by(
                    currency_pair=pair, timeframe=tf, indicator_name=ind_name
                ).order_by(SimulationTrade.entry_at.desc())
                .limit(TRADE_LIMIT_PER_INDICATOR).all()
            ]
            db.session.query(SimulationTrade).filter(
                SimulationTrade.currency_pair  == pair,
                SimulationTrade.timeframe      == tf,
                SimulationTrade.indicator_name == ind_name,
                SimulationTrade.id.notin_(keep_ids),
            ).delete(synchronize_session=False)
            logger.debug("Trimmed SimulationTrade: %s %s %s → %d件",
                         pair, tf, ind_name, TRADE_LIMIT_PER_INDICATOR)

    db.session.commit()

    # ---- インクリメンタルモード: DB全データから統計を再計算 ----
    # トリム後の最新状態で BacktestResult を更新するため、trim commit の後に実行する
    if recompute_stats and results:
        from app.models.backtest import BacktestResult
        for r in results:
            stats = _recompute_stats_from_db(
                r["currency_pair"], r["timeframe"], r["indicator_name"],
                float(r["initial_capital"])
            )
            if stats is None:
                continue
            record = BacktestResult.query.filter_by(
                currency_pair  = r["currency_pair"],
                timeframe      = r["timeframe"],
                indicator_name = r["indicator_name"],
            ).first()
            if record is None:
                continue
            record.win_rate       = stats["win_rate"]
            record.total_trades   = stats["total_trades"]
            record.winning_trades = stats["winning_trades"]
            record.losing_trades  = stats["losing_trades"]
            record.total_profit   = stats["total_profit"]
            record.final_capital  = stats["final_capital"]
            record.max_drawdown   = stats["max_drawdown"]
            record.profit_factor  = stats["profit_factor"]
        db.session.commit()
        logger.debug("DB再集計完了: %d指標", len(results))

    return saved


def save_daily_snapshot() -> int:
    """
    現在の backtest_results から日次スナップショットを保存する。
    同日に複数回実行した場合は最新値で上書き（upsert）。

    呼び出しタイミング:
      - run_analysis.py（Cron 30分ごと）で日1回分だけ記録
      - run_ranking_bt.py（手動バックテスト）実行後
      - tasks/save_daily_snapshot.py（独立した日次Cronとしても実行可能）
    """
    from app.models.backtest import BacktestResult
    from app.models.backtest_snapshot import BacktestDailySnapshot
    from app import db
    from datetime import date
    from collections import defaultdict

    today   = date.today()
    results = BacktestResult.query.all()
    if not results:
        return 0

    # pair × TF でグループ化してスコア順にランキング付け
    by_pair_tf: dict = defaultdict(list)
    for r in results:
        score = _calc_score(
            float(r.win_rate      or 0),
            float(r.profit_factor or 0),
            int(r.total_trades    or 0),
            float(r.sl_pips       or 0),
            float(r.tp_pips       or 0),
            abs(float(r.max_drawdown or 0)),
        )
        by_pair_tf[(r.currency_pair, r.timeframe)].append((score, r))

    saved = 0
    for (pair, tf), items in by_pair_tf.items():
        items.sort(key=lambda x: x[0], reverse=True)
        for rank, (score, r) in enumerate(items, 1):
            snap = BacktestDailySnapshot.query.filter_by(
                snapshot_date  = today,
                currency_pair  = pair,
                timeframe      = tf,
                indicator_name = r.indicator_name,
            ).first()
            if snap is None:
                snap = BacktestDailySnapshot(
                    snapshot_date  = today,
                    currency_pair  = pair,
                    timeframe      = tf,
                    indicator_name = r.indicator_name,
                )
                db.session.add(snap)

            snap.win_rate       = r.win_rate
            snap.profit_factor  = r.profit_factor
            snap.total_trades   = r.total_trades
            snap.winning_trades = r.winning_trades
            snap.losing_trades  = r.losing_trades
            snap.final_capital  = r.final_capital
            snap.max_drawdown   = r.max_drawdown
            snap.sl_pips        = r.sl_pips
            snap.tp_pips        = r.tp_pips
            snap.rank_position  = rank
            snap.score          = score
            saved += 1

    db.session.commit()
    logger.info("日次スナップショット保存: %d件 (date=%s)", saved, today)
    return saved
