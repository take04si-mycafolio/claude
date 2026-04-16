"""
USD/JPY 多角的シグナル判定エンジン

マルチタイムフレームMA合流 + 外部マクロ要因 + モメンタム を
100点満点でスコア化し、Strong Buy / Buy / Neutral / Warning レベルを返す。
"""

import math
import time
from datetime import datetime, timezone, timedelta


# モジュールレベルの簡易 TTL キャッシュ（外部依存なし）
_cache: dict = {"result": None, "ts": 0.0}
CACHE_TTL = 60  # 秒


def calculate_trend_score(
    price_5m: float,
    ma20_5m: float,
    price_1h: float,
    ma75_1h: float,
    ma20_1h: float,
    ma200_1h: float,
    rsi_14: float,
    us10y_rising: bool,
    dxy_rising: bool,
) -> dict:
    """
    純粋関数: 入力値からトレンドスコアを計算して返す（副作用なし・テスト可能）

    スコア内訳:
        ① トレンド合流（最大 50 点）
            - 5分足終値 > MA20(5min)       : +10
            - 1時間足終値 > MA75(1hr)       : +20
            - パーフェクトオーダー(1hr)      : +20
        ② 外部要因（最大 30 点）
            - US10Y が MA(5) より上          : +15
            - DXY が MA(5) より上            : +15
        ③ モメンタム（最大 +20 / 最小 -10）
            - 50 ≤ RSI ≤ 65               : +20（順張りの勢い）
            - RSI ≥ 75                     : -10（過熱警戒）
            - RSI ≤ 30                     : +5 （売られすぎからの反発初動）
    """
    # ① トレンド合流
    above_5m_ma20 = price_5m > ma20_5m
    above_1h_ma75 = price_1h > ma75_1h
    perfect_order = (ma20_1h > ma75_1h) and (ma75_1h > ma200_1h)

    trend_score = (
        (10 if above_5m_ma20 else 0)
        + (20 if above_1h_ma75 else 0)
        + (20 if perfect_order else 0)
    )

    # ② 外部要因
    external_score = (15 if us10y_rising else 0) + (15 if dxy_rising else 0)

    # ③ モメンタム
    if 50 <= rsi_14 <= 65:
        momentum_score, rsi_status = 20, "momentum"
    elif rsi_14 >= 75:
        momentum_score, rsi_status = -10, "overheated"
    elif rsi_14 <= 30:
        momentum_score, rsi_status = 5, "oversold_rebound"
    else:
        momentum_score, rsi_status = 0, "neutral"

    score = trend_score + external_score + momentum_score

    if score >= 90:
        level = "Strong Buy"
        message = "パーフェクトオーダー＆金利同期。絶好の押し目買い局面。"
    elif score >= 70:
        level = "Buy"
        message = "上昇トレンド継続中。順張りを推奨。"
    elif score >= 40:
        level = "Neutral"
        message = "方向感模索中。重要ラインの突破待ち。"
    else:
        level = "Warning"
        message = "トレンド転換の兆し、または逆風。"

    return {
        "score": score,
        "level": level,
        "message": message,
        "breakdown": {
            "trend_score": trend_score,
            "external_score": external_score,
            "momentum_score": momentum_score,
        },
        "detail": {
            "5m_above_ma20": above_5m_ma20,
            "1h_above_ma75": above_1h_ma75,
            "perfect_order": perfect_order,
            "us10y_rising": us10y_rising,
            "dxy_rising": dxy_rising,
            "rsi": round(rsi_14, 2),
            "rsi_status": rsi_status,
        },
    }


def get_usdjpy_trend_score() -> dict:
    """
    USD/JPY のトレンドスコアを計算して返す。
    60秒 TTL のモジュールキャッシュを使用し、頻繁な呼び出しに対応。
    """
    # キャッシュヒット判定
    if _cache["result"] is not None and time.time() - _cache["ts"] < CACHE_TTL:
        return _cache["result"]

    from app.services.data_fetcher import get_candles
    import yfinance as yf

    # --- USD/JPY キャンドル取得 ---
    df_5m = get_candles("USDJPY", "5min", limit=210)
    df_1h = get_candles("USDJPY", "1hr", limit=210)
    if df_5m.empty or df_1h.empty:
        return {"error": "価格データが取得できませんでした"}

    close_5m = df_5m["close"].astype(float)
    close_1h = df_1h["close"].astype(float)

    # --- MA 計算 ---
    price_5m = float(close_5m.iloc[-1])
    ma20_5m = float(close_5m.rolling(20).mean().iloc[-1])
    price_1h = float(close_1h.iloc[-1])
    ma20_1h = float(close_1h.rolling(20).mean().iloc[-1])
    ma75_1h = float(close_1h.rolling(75).mean().iloc[-1])
    ma200_1h = float(close_1h.rolling(200).mean().iloc[-1])

    if any(math.isnan(v) for v in [ma20_5m, ma20_1h, ma75_1h, ma200_1h]):
        return {"error": "MA計算に必要なデータが不足しています（200本以上必要）"}

    # --- RSI(14) 計算（Wilder平滑化: EWM com=13）---
    delta = close_1h.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi_series = 100 - 100 / (1 + rs)
    rsi_14 = float(rsi_series.iloc[-1])
    if math.isnan(rsi_14):
        return {"error": "RSI計算に失敗しました"}

    # --- US10Y / DXY 方向判定（MA5 ベース・ノイズ除去）---
    def _is_rising(ticker_sym: str) -> bool:
        """直近5本の MA と現在値を比較。タイムアウト時は False（保守的デフォルト）。"""
        try:
            df = yf.Ticker(ticker_sym).history(period="5d", interval="1h", auto_adjust=True)
            if df is None or len(df) < 5:
                return False
            close = df["Close"].astype(float)
            return float(close.iloc[-1]) > float(close.iloc[-5:].mean())
        except Exception:
            return False

    us10y_rising = _is_rising("^TNX")
    dxy_rising = _is_rising("DX-Y.NYB")

    result = calculate_trend_score(
        price_5m=price_5m,
        ma20_5m=ma20_5m,
        price_1h=price_1h,
        ma75_1h=ma75_1h,
        ma20_1h=ma20_1h,
        ma200_1h=ma200_1h,
        rsi_14=rsi_14,
        us10y_rising=us10y_rising,
        dxy_rising=dxy_rising,
    )

    # --- データ鮮度チェック（市場閉場時・土日対策）---
    latest_ts = df_1h["timestamp"].iloc[-1]
    if hasattr(latest_ts, "to_pydatetime"):
        latest_ts = latest_ts.to_pydatetime()
    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
    data_age_hours = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 3600
    result["data_stale"] = data_age_hours > 4
    result["data_age_hours"] = round(data_age_hours, 1)

    jst = timezone(timedelta(hours=9))
    result["updated_at"] = datetime.now(jst).strftime("%Y/%m/%d %H:%M JST")

    # キャッシュ更新
    _cache["result"] = result
    _cache["ts"] = time.time()
    return result
