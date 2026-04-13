"""
為替データ取得サービス
- yfinance（Yahoo Finance）を主として使用（無料・APIキー不要）
- Alpha Vantage はオプション（無料プランはFXデータ非対応のため現在は未使用）
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

# yfinance で取得できる期間の上限
YF_PERIOD_MAP = {
    "5min":  "7d",
    "15min": "60d",
    "30min": "60d",
    "1hr":   "730d",
    "4hr":   "730d",
    "daily": "2y",
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
    period = YF_PERIOD_MAP.get(fetch_tf)

    if not interval:
        logger.error("Unknown timeframe: %s", timeframe)
        return None

    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)

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


def fetch_and_store_all(pairs=None, timeframes=None) -> dict:
    """
    全通貨ペア・タイムフレームのデータを取得してDBに保存する。
    yfinance を使用（無料・APIキー不要）
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
