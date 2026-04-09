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

        # yfinance forex の既知問題: O=H=L=C になる場合、前足closeをopenとして合成OHLC
        if len(df) > 1 and (df['open'] == df['close']).all():
            logger.warning("O=H=L=C detected for %s %s — synthesizing OHLC", pair, timeframe)
            prev = df['close'].shift(1).fillna(df['close'].iloc[0])
            df = df.copy()
            df['open'] = prev.values
            df['high'] = df[['open', 'close']].max(axis=1)
            df['low']  = df[['open', 'close']].min(axis=1)

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
    最新足（まだ完成していない可能性）は上書き更新、それ以外は重複スキップ。
    """
    from app import db
    from app.models.price_data import PriceData
    from datetime import datetime, timedelta

    # タイムフレームごとの足の長さ（分）
    tf_minutes = {"5min": 5, "15min": 15, "30min": 30, "1hr": 60, "4hr": 240, "daily": 1440}
    bar_minutes = tf_minutes.get(timeframe, 15)
    # 現在時刻より bar_minutes 以内のタイムスタンプは「未完成の可能性あり」→ 上書き
    now_utc = datetime.utcnow()
    incomplete_cutoff = now_utc - timedelta(minutes=bar_minutes)

    saved = 0
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)

        existing = PriceData.query.filter_by(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=ts,
        ).first()

        if existing:
            # 未完成の可能性がある最新足のみ上書き更新
            if ts >= incomplete_cutoff:
                existing.open   = float(row["open"])
                existing.high   = float(row["high"])
                existing.low    = float(row["low"])
                existing.close  = float(row["close"])
                existing.volume = int(row.get("volume", 0))
                saved += 1
            continue

        record = PriceData(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row.get("volume", 0)),
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
