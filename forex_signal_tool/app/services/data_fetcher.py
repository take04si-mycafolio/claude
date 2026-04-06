"""
Alpha Vantage API を使用した為替データ取得サービス。

制限事項:
  - 無料プラン: 25リクエスト/日
  - 取得間隔を適切に設定し、キャッシュを活用すること
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import pandas as pd

from app.config import Config

logger = logging.getLogger(__name__)

AV_BASE = Config.ALPHA_VANTAGE_BASE_URL


def _av_request(params: dict, retries: int = 3) -> Optional[dict]:
    """Alpha Vantage APIへのリクエスト（リトライ付き）"""
    params["apikey"] = Config.ALPHA_VANTAGE_API_KEY
    for attempt in range(retries):
        try:
            resp = requests.get(AV_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "Note" in data:
                logger.warning("Alpha Vantage rate limit reached: %s", data["Note"])
                return None
            if "Information" in data:
                logger.warning("Alpha Vantage info: %s", data["Information"])
                return None
            return data
        except requests.RequestException as exc:
            logger.error("AV request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def fetch_intraday(pair: str, interval: str, output_size: str = "compact") -> Optional[pd.DataFrame]:
    """
    分足データ取得 (5min/15min/30min/60min)

    Parameters
    ----------
    pair       : 通貨ペア文字列 ("USDJPY" 等)
    interval   : Alpha Vantage インターバル ("5min"/"15min"/"30min"/"60min")
    output_size: "compact"(直近100本) / "full"(直近20年分)
    """
    from_cur, to_cur = Config.AV_PAIR_MAP.get(pair, (None, None))
    if not from_cur:
        logger.error("Unknown pair: %s", pair)
        return None

    data = _av_request({
        "function": "FX_INTRADAY",
        "from_symbol": from_cur,
        "to_symbol": to_cur,
        "interval": interval,
        "outputsize": output_size,
    })
    if not data:
        return None

    key = f"Time Series FX ({interval})"
    if key not in data:
        logger.error("Unexpected AV response keys: %s", list(data.keys()))
        return None

    rows = []
    for ts_str, ohlc in data[key].items():
        rows.append({
            "timestamp": pd.Timestamp(ts_str, tz="UTC"),
            "open": float(ohlc["1. open"]),
            "high": float(ohlc["2. high"]),
            "low": float(ohlc["3. low"]),
            "close": float(ohlc["4. close"]),
            "volume": 0,
        })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


def fetch_daily(pair: str, output_size: str = "compact") -> Optional[pd.DataFrame]:
    """日足データ取得"""
    from_cur, to_cur = Config.AV_PAIR_MAP.get(pair, (None, None))
    if not from_cur:
        return None

    data = _av_request({
        "function": "FX_DAILY",
        "from_symbol": from_cur,
        "to_symbol": to_cur,
        "outputsize": output_size,
    })
    if not data:
        return None

    key = "Time Series FX (Daily)"
    if key not in data:
        return None

    rows = []
    for ts_str, ohlc in data[key].items():
        rows.append({
            "timestamp": pd.Timestamp(ts_str + " 00:00:00", tz="UTC"),
            "open": float(ohlc["1. open"]),
            "high": float(ohlc["2. high"]),
            "low": float(ohlc["3. low"]),
            "close": float(ohlc["4. close"]),
            "volume": 0,
        })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


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
    """DataFrameをDBのprice_dataテーブルに保存（重複は無視）"""
    from app import db
    from app.models.price_data import PriceData

    saved = 0
    for _, row in df.iterrows():
        existing = PriceData.query.filter_by(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=row["timestamp"].to_pydatetime(),
        ).first()
        if existing:
            continue
        record = PriceData(
            currency_pair=pair,
            timeframe=timeframe,
            timestamp=row["timestamp"].to_pydatetime(),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
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

    Alpha Vantage 無料プランの25リクエスト/日制限に注意:
    - 1hr/4hr/dailyは同一APIコールで4hr をリサンプリング
    - 1リクエストあたり100本のデータを取得
    """
    if pairs is None:
        pairs = Config.CURRENCY_PAIRS
    if timeframes is None:
        timeframes = Config.TIMEFRAMES

    results = {}
    req_count = 0

    for pair in pairs:
        results[pair] = {}

        # --- intraday timeframes ---
        intraday_map = {
            "5min": "5min",
            "15min": "15min",
            "30min": "30min",
            "1hr": "60min",
        }
        df_1hr = None
        for tf, av_interval in intraday_map.items():
            if tf not in timeframes:
                continue
            logger.info("Fetching %s %s ...", pair, tf)
            df = fetch_intraday(pair, av_interval)
            req_count += 1
            if df is not None:
                saved = save_price_data(pair, tf, df)
                results[pair][tf] = saved
                if tf == "1hr":
                    df_1hr = df
            time.sleep(12)  # 無料プランのレート制限対策

        # --- 4hr (1hrからリサンプリング) ---
        if "4hr" in timeframes and df_1hr is not None:
            df_4hr = resample_to_4hr(df_1hr)
            saved = save_price_data(pair, "4hr", df_4hr)
            results[pair]["4hr"] = saved

        # --- daily ---
        if "daily" in timeframes:
            logger.info("Fetching %s daily ...", pair)
            df = fetch_daily(pair)
            req_count += 1
            if df is not None:
                saved = save_price_data(pair, "daily", df)
                results[pair]["daily"] = saved
            time.sleep(12)

    logger.info("Total AV requests used: %d", req_count)
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
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df
