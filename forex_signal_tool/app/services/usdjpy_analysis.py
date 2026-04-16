"""
USD/JPY 多角的シグナル判定エンジン

マルチタイムフレームMA合流 + 外部マクロ要因 + モメンタム を
-100〜+100 のスコアで方向性を判定する。
  正スコア: 買い優勢
  負スコア: 売り優勢
  ±30以内: レンジ（様子見）
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
    rsi_prev: float = None,
) -> dict:
    """
    純粋関数: 入力値からトレンドスコアを計算して返す（副作用なし・テスト可能）

    スコア範囲: -100〜+100（正=買い優勢 / 負=売り優勢 / ±30内=レンジ）

    ① トレンド合流（-50〜+50）
        - 5m終値 vs MA20   : 上抜け +10 / 下抜け -10
        - 1h終値 vs MA75   : 上抜け +20 / 下抜け -20
        - 1h パーフェクトオーダー上向き: +20
        - 1h パーフェクトオーダー下向き: -20
        - 崩れ: 0

    ② 外部要因（-30〜+30）
        - US10Y MA(5) 上抜け: +15 / 下抜け: -15
        - DXY   MA(5) 上抜け: +15 / 下抜け: -15

    ③ 乖離率ペナルティ（0 or -30）
        - price_1h が ma20_1h から 0.5% 以上乖離: -30

    ④ モメンタム（-20〜+20）
        - RSI 50-65        : +10（順張り勢い）
        - RSI 65-75        : -5 （過熱警戒）
        - RSI ≥ 75         : -20（買われすぎ）
        - RSI ≤ 30 かつ上向き（rsi_prev指定時）: +15（反発初動）
        - RSI ≤ 30 かつ横ばい/下向き: 0
        - その他           : 0

    レベル定義:
        ≥ +70 : Strong Buy  / +30〜+69 : Buy
        -30〜+29: Neutral   / -70〜-31 : Sell  / ≤ -70 : Strong Sell
    """
    # ① トレンド合流
    above_5m_ma20      = price_5m > ma20_5m
    above_1h_ma75      = price_1h > ma75_1h
    perfect_order_up   = (ma20_1h > ma75_1h) and (ma75_1h > ma200_1h)
    perfect_order_down = (ma20_1h < ma75_1h) and (ma75_1h < ma200_1h)

    trend_score = (
        (10 if above_5m_ma20 else -10)
        + (20 if above_1h_ma75 else -20)
        + (20 if perfect_order_up else (-20 if perfect_order_down else 0))
    )

    # ② 外部要因
    external_score = (
        (15 if us10y_rising else -15)
        + (15 if dxy_rising else -15)
    )

    # ③ 乖離率調整（双方向）
    # 買い過熱（価格 > MA20 + 0.5%）: -30 で買いシグナルを抑制
    # 売り過熱（価格 < MA20 - 0.5%）: +30 で売りシグナルを緩和（底値売りを避ける）
    deviation_up = (price_1h - ma20_1h) / ma20_1h if ma20_1h else 0
    if deviation_up > 0.005:
        deviation_penalty = -30
    elif deviation_up < -0.005:
        deviation_penalty = +30
    else:
        deviation_penalty = 0

    # ④ モメンタム
    oversold_bounce = (
        rsi_prev is not None
        and not math.isnan(rsi_prev)
        and rsi_14 <= 30
        and rsi_14 > rsi_prev
    )

    if 50 <= rsi_14 <= 65:
        momentum_score, rsi_status = 10, "momentum"
    elif rsi_14 >= 75:
        momentum_score, rsi_status = -20, "overbought"
    elif rsi_14 >= 65:
        momentum_score, rsi_status = -5, "warning"
    elif oversold_bounce:
        momentum_score, rsi_status = 15, "oversold_bounce"
    elif rsi_14 <= 30:
        momentum_score, rsi_status = 0, "oversold"
    else:
        momentum_score, rsi_status = 0, "neutral"

    score = trend_score + external_score + deviation_penalty + momentum_score

    if score >= 70:
        level = "Strong Buy"
        message = "トレンド・金利・モメンタムが揃った強い買いシグナル。"
    elif score >= 30:
        level = "Buy"
        message = "上昇優勢。押し目を狙った順張りが有効。"
    elif score >= -30:
        level = "Neutral"
        message = "方向感なし。レンジ継続の可能性が高い。"
    elif score >= -70:
        level = "Sell"
        message = "下落優勢。戻り売りまたはショートを検討。"
    else:
        level = "Strong Sell"
        message = "複数要因が下落を示唆。売り圧力が強い局面。"

    return {
        "score": score,
        "level": level,
        "message": message,
        "breakdown": {
            "trend_score":      trend_score,
            "external_score":   external_score,
            "momentum_score":   momentum_score,
            "deviation_penalty": deviation_penalty,
        },
        "detail": {
            "5m_above_ma20":      above_5m_ma20,
            "1h_above_ma75":      above_1h_ma75,
            "perfect_order_up":   perfect_order_up,
            "perfect_order_down": perfect_order_down,
            "us10y_rising":       us10y_rising,
            "dxy_rising":         dxy_rising,
            "rsi":                round(rsi_14, 2),
            "rsi_status":         rsi_status,
            "deviation_pct":      round(deviation_up * 100, 3),
            "deviation_penalty":  deviation_penalty,
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

    # --- USD/JPY キャンドル取得 ---
    df_5m = get_candles("USDJPY", "5min", limit=210)
    df_1h = get_candles("USDJPY", "1hr", limit=210)
    if df_5m.empty or df_1h.empty:
        return {"error": "価格データが取得できませんでした"}

    close_5m = df_5m["close"].astype(float)
    close_1h = df_1h["close"].astype(float)

    # --- MA 計算 ---
    price_5m  = float(close_5m.iloc[-1])
    ma20_5m   = float(close_5m.rolling(20).mean().iloc[-1])
    price_1h  = float(close_1h.iloc[-1])
    ma20_1h   = float(close_1h.rolling(20).mean().iloc[-1])
    ma75_1h   = float(close_1h.rolling(75).mean().iloc[-1])
    ma200_1h  = float(close_1h.rolling(200).mean().iloc[-1])

    if any(math.isnan(v) for v in [ma20_5m, ma20_1h, ma75_1h, ma200_1h]):
        return {"error": "MA計算に必要なデータが不足しています（200本以上必要）"}

    # --- RSI(14) 計算（Wilder平滑化: EWM com=13）---
    delta = close_1h.diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rs    = gain / loss.replace(0, float("nan"))
    rsi_series = 100 - 100 / (1 + rs)
    rsi_14 = float(rsi_series.iloc[-1])
    if math.isnan(rsi_14):
        return {"error": "RSI計算に失敗しました"}
    rsi_prev = float(rsi_series.iloc[-2]) if len(rsi_series) >= 2 else None
    if rsi_prev is not None and math.isnan(rsi_prev):
        rsi_prev = None

    # --- US10Y / DXY 方向判定（DB参照・MA5 ベース・ノイズ除去）---
    def _is_rising(pair_key: str) -> bool:
        """DB から直近5本の 1hr 終値を取得し MA と現在値を比較。データ不足時は False。"""
        try:
            df_macro = get_candles(pair_key, "1hr", limit=10)
            if df_macro.empty or len(df_macro) < 5:
                return False
            close = df_macro["close"].astype(float)
            return float(close.iloc[-1]) > float(close.iloc[-5:].mean())
        except Exception:
            return False

    us10y_rising = _is_rising("US10Y")
    dxy_rising   = _is_rising("DXY")

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
        rsi_prev=rsi_prev,
    )

    # --- データ鮮度チェック（市場閉場時・土日対策）---
    latest_ts = df_1h["timestamp"].iloc[-1]
    if hasattr(latest_ts, "to_pydatetime"):
        latest_ts = latest_ts.to_pydatetime()
    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
    data_age_hours = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 3600
    result["data_stale"]     = data_age_hours > 4
    result["data_age_hours"] = round(data_age_hours, 1)

    jst = timezone(timedelta(hours=9))
    result["updated_at"] = datetime.now(jst).strftime("%Y/%m/%d %H:%M JST")

    # キャッシュ更新
    _cache["result"] = result
    _cache["ts"]     = time.time()
    return result
