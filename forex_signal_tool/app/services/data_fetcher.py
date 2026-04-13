"""
為替データ取得サービス
- yfinance（Yahoo Finance）: 全タイムフレーム
  - 日足: period="max" で最長履歴（USDJPY=X は1990年代まで遡れる）
  - 短期足: start/end 日付指定（API制約に従った最大期間）
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import pandas as pd
import yfinance as yf

from app.config import Config

logger = logging.getLogger(__name__)

# yfinance 通貨ペアマッピング
YF_PAIR_MAP = {
    "USDJPY": "USDJPY=X",
    "GBPJPY": "GBPJPY=X",
    "EURJPY": "EURJPY=X",
}

# yfinance インターバルマッピング
YF_INTERVAL_MAP = {
    "5min":  "5m",
    "15min": "15m",
    "30min": "30m",
    "1hr":   "60m",
    "4hr":   "1h",   # 1hで取得後リサンプリング
    "daily": "1d",
}

# タイムフレームごとの取得設定
# 日足は period="max" で最長履歴、短期足は start/end 日付指定
YF_DAYS_BACK = {
    "5min":  7,    # yfinance制約: 5m は最大7日
    "15min": 60,   # yfinance制約: 15m は最大60日
    "30min": 60,   # yfinance制約: 30m は最大60日
    "1hr":   730,  # 1h は最大730日程度
}


def fetch_yfinance(pair: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Yahoo Finance からローソク足データを取得する。

    Parameters
    ----------
    pair      : 通貨ペア ("USDJPY" 等)
    timeframe : タイムフレーム ("5min"/"15min"/"30min"/"1hr"/"4hr"/"daily")
    """
    ticker_symbol = YF_PAIR_MAP.get(pair)
    if not ticker_symbol:
        logger.error("Unknown pair: %s", pair)
        return None

    # 4hrは1hで取得してリサンプリング
    fetch_tf = "1hr" if timeframe == "4hr" else timeframe
    interval = YF_INTERVAL_MAP.get(fetch_tf)

    if not interval:
        logger.error("Unknown timeframe: %s", timeframe)
        return None

    try:
        ticker = yf.Ticker(ticker_symbol)

        # 日足: period="max" で最長履歴を取得（USDJPY=X は1990年代まで遡れる）
        if fetch_tf == "daily":
            df = ticker.history(period="max", interval=interval, auto_adjust=True)
        else:
            # 短期足: start/end 日付指定（yfinance API制約に従った最大期間）
            days_back = YF_DAYS_BACK.get(fetch_tf, 60)
            end_dt   = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=days_back)
            df = ticker.history(
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                interval=interval, auto_adjust=True,
            )

        if df.empty:
            logger.warning("No data returned for %s %s", pair, timeframe)
            return None

        df = df.reset_index()

        # カラム名を統一
        col_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("datetime", "date", "timestamp"):
                col_map[col] = "timestamp"
            elif col_lower == "open":
                col_map[col] = "open"
            elif col_lower == "high":
                col_map[col] = "high"
            elif col_lower == "low":
                col_map[col] = "low"
            elif col_lower == "close":
                col_map[col] = "close"
            elif col_lower == "volume":
                col_map[col] = "volume"
        df = df.rename(columns=col_map)

        # 必要カラムのみ
        needed = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[needed]

        if "volume" not in df.columns:
            df["volume"] = 0

        # タイムスタンプをUTCのdatetimeに変換
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        # タイムゾーン情報を除去してnaiveなdatetimeに変換（MySQL用）
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        df = df.sort_values("timestamp").reset_index(drop=True)

        # yfinance forex の既知問題: O=H=L=C になる行を per-row で合成OHLC
        mask = (
            (df['open'] == df['close']) &
            (df['high'] == df['close']) &
            (df['low']  == df['close'])
        )
        if mask.any():
            logger.warning("O=H=L=C rows detected for %s %s (%d/%d) — synthesizing OHLC",
                           pair, timeframe, int(mask.sum()), len(df))
            df = df.copy()
            prev_close = df['close'].shift(1).fillna(df['close'].iloc[0])
            df.loc[mask, 'open'] = prev_close[mask]
            df.loc[mask, 'high'] = df.loc[mask, ['open', 'close']].max(axis=1)
            df.loc[mask, 'low']  = df.loc[mask, ['open', 'close']].min(axis=1)

        # 4hrリサンプリング
        if timeframe == "4hr":
            df = resample_to_4hr(df)

        return df

    except Exception as exc:
        logger.error("yfinance error for %s %s: %s", pair, timeframe, exc)
        return None


def resample_to_4hr(df_1hr: pd.DataFrame) -> pd.DataFrame:
    """1時間足データを4時間足にリサンプリング"""
    df = df_1hr.copy()
    df = df.set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index)

    ohlc = df[["open", "high", "low", "close"]].resample("4h", origin="epoch").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    }).dropna()
    ohlc["volume"] = 0
    ohlc = ohlc.reset_index()
    return ohlc


def save_price_data(pair: str, timeframe: str, df: pd.DataFrame) -> int:
    """DataFrameをDBのprice_dataテーブルに保存。
    既存レコードは値が異なる場合に上書き更新（取得タイミングによる欠損値修正に対応）。
    新規レコードは INSERT。
    """
    from app import db
    from app.models.price_data import PriceData

    def _round(v: float) -> float:
        return round(float(v), 6)

    saved = 0
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)

        new_open   = _round(row["open"])
        new_high   = _round(row["high"])
        new_low    = _round(row["low"])
        new_close  = _round(row["close"])
        new_volume = int(row.get("volume", 0))

        existing = PriceData.query.filter_by(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=ts,
        ).first()

        if existing:
            # 値が異なる場合のみ上書き更新
            if (
                _round(existing.open)  != new_open  or
                _round(existing.high)  != new_high  or
                _round(existing.low)   != new_low   or
                _round(existing.close) != new_close
            ):
                existing.open   = new_open
                existing.high   = new_high
                existing.low    = new_low
                existing.close  = new_close
                existing.volume = new_volume
                saved += 1
            continue

        record = PriceData(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=ts,
            open=new_open,
            high=new_high,
            low=new_low,
            close=new_close,
            volume=new_volume,
        )
        db.session.add(record)
        saved += 1

    if saved:
        db.session.commit()
    return saved


def fetch_alphavantage_daily(pair: str) -> Optional[pd.DataFrame]:
    """
    Alpha Vantage FX_DAILY API から日足データを取得する。
    outputsize=full で 20 年以上の正確な OHLCV を返す。
    無料プラン: 25 リクエスト/日、5 リクエスト/分。
    """
    api_key = Config.ALPHA_VANTAGE_API_KEY
    if not api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY が未設定です")
        return None

    from_sym, to_sym = Config.AV_PAIR_MAP.get(pair, (None, None))
    if not from_sym:
        logger.error("Alpha Vantage: Unknown pair: %s", pair)
        return None

    url = Config.ALPHA_VANTAGE_BASE_URL
    params = {
        "function":    "FX_DAILY",
        "from_symbol": from_sym,
        "to_symbol":   to_sym,
        "outputsize":  "full",
        "apikey":      api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # エラーレスポンス検出
        if "Error Message" in data:
            logger.error("Alpha Vantage error: %s", data["Error Message"])
            return None
        if "Note" in data:
            logger.warning("Alpha Vantage rate limit: %s", data["Note"])
            return None
        if "Information" in data:
            logger.warning("Alpha Vantage info: %s", data["Information"])
            return None

        ts_data = data.get("Time Series FX (Daily)", {})
        if not ts_data:
            logger.warning("Alpha Vantage: no time series data for %s", pair)
            return None

        rows = []
        for date_str, values in ts_data.items():
            rows.append({
                "timestamp": date_str,
                "open":      float(values["1. open"]),
                "high":      float(values["2. high"]),
                "low":       float(values["3. low"]),
                "close":     float(values["4. close"]),
                "volume":    0,
            })

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # タイムゾーンなし（MySQL 用）
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

        logger.info("AlphaVantage: %s daily %d rows (%s〜%s)",
                    pair, len(df),
                    df["timestamp"].iloc[0].date(),
                    df["timestamp"].iloc[-1].date())
        return df

    except Exception as exc:
        logger.error("Alpha Vantage fetch error for %s: %s", pair, exc)
        return None


def fetch_and_store_all(pairs=None, timeframes=None) -> dict:
    """
    全通貨ペア・タイムフレームのデータを取得してDBに保存する。
    日足: Alpha Vantage（正確な OHLCV・長期履歴）
    その他: yfinance
    """
    if pairs is None:
        pairs = Config.CURRENCY_PAIRS
    if timeframes is None:
        timeframes = Config.TIMEFRAMES

    results = {}

    for pair in pairs:
        results[pair] = {}
        for tf in timeframes:
            logger.info("Fetching %s %s ...", pair, tf)

            if tf == "daily":
                # 日足は Alpha Vantage を優先（正確な OHLCV）
                df = fetch_alphavantage_daily(pair)
                if df is None or df.empty:
                    logger.warning("Alpha Vantage 失敗、yfinance にフォールバック: %s daily", pair)
                    df = fetch_yfinance(pair, tf)
                # Alpha Vantage は 5req/分制限 → ペア間で待機
                time.sleep(15)
            else:
                df = fetch_yfinance(pair, tf)

            if df is not None and not df.empty:
                saved = save_price_data(pair, tf, df)
                results[pair][tf] = saved
                logger.info("  %s %s: %d件保存", pair, tf, saved)
            else:
                results[pair][tf] = 0
                logger.warning("  %s %s: データなし", pair, tf)
            time.sleep(1)  # Yahoo Financeへの負荷軽減

    return results


def get_latest_price(pair: str) -> Optional[dict]:
    """DBから最新の価格（5分足ベース）を取得"""
    from app.models.price_data import PriceData

    record = (
        PriceData.query.filter_by(currency_pair=pair, timeframe="5min")
        .order_by(PriceData.timestamp.desc())
        .first()
    )
    if record:
        return record.to_dict()
    return None


def get_candles(pair: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """DBから指定通貨ペア・タイムフレームのローソク足を取得してDataFrameで返す"""
    from app.models.price_data import PriceData

    records = (
        PriceData.query.filter_by(currency_pair=pair, timeframe=timeframe)
        .order_by(PriceData.timestamp.desc())
        .limit(limit)
        .all()
    )
    if not records:
        return pd.DataFrame()

    rows = [r.to_dict() for r in records]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df
