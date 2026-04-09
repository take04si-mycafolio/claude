"""
複合テクニカル指標

複数の指標が同方向を示した場合のみシグナルを発生させる複合条件指標。

  - RSI_MACD_Combo     : RSI + MACD 両方一致
  - RSI_Stoch_Combo    : RSI + Stochastic 両方一致
  - MACD_Stoch_Combo   : MACD + Stochastic 両方一致
  - Triple_OSC_Combo   : RSI + MACD + Stochastic 全一致
  - All_AND_Consensus  : オシレーター + トレンド全指標が同方向に一致（5つ以上）
"""

import pandas as pd


def _sig(d: dict, name: str) -> str:
    return d.get(name, {}).get("signal", "NEUTRAL")


def calculate_composite(df: pd.DataFrame) -> dict:
    """
    複合条件指標を計算する。
    内部で oscillators / trend を呼び出し、シグナルの組み合わせを判定する。
    """
    if df.empty or len(df) < 30:
        return {}

    from .oscillators import calculate_oscillators
    from .trend import calculate_trend

    osc   = calculate_oscillators(df)
    trend = calculate_trend(df)

    rsi_s   = _sig(osc, "RSI_14")
    macd_s  = _sig(osc, "MACD_12_26_9")
    stoch_s = _sig(osc, "Stochastic_14_3")

    results = {}

    # --- RSI + MACD ---
    if rsi_s != "NEUTRAL" and rsi_s == macd_s:
        signal = rsi_s
    else:
        signal = "NEUTRAL"
    results["RSI_MACD_Combo"] = {
        "value": None, "signal": signal, "category": "composite",
        "details": {"rsi": rsi_s, "macd": macd_s},
    }

    # --- RSI + Stochastic ---
    if rsi_s != "NEUTRAL" and rsi_s == stoch_s:
        signal = rsi_s
    else:
        signal = "NEUTRAL"
    results["RSI_Stoch_Combo"] = {
        "value": None, "signal": signal, "category": "composite",
        "details": {"rsi": rsi_s, "stoch": stoch_s},
    }

    # --- MACD + Stochastic ---
    if macd_s != "NEUTRAL" and macd_s == stoch_s:
        signal = macd_s
    else:
        signal = "NEUTRAL"
    results["MACD_Stoch_Combo"] = {
        "value": None, "signal": signal, "category": "composite",
        "details": {"macd": macd_s, "stoch": stoch_s},
    }

    # --- Triple Oscillator: RSI + MACD + Stochastic 全一致 ---
    if rsi_s != "NEUTRAL" and rsi_s == macd_s == stoch_s:
        signal = rsi_s
    else:
        signal = "NEUTRAL"
    results["Triple_OSC_Combo"] = {
        "value": None, "signal": signal, "category": "composite",
        "details": {"rsi": rsi_s, "macd": macd_s, "stoch": stoch_s},
    }

    # --- 全指標AND一致: オシレーター + トレンド全指標が同方向（5つ以上） ---
    all_sigs = (
        [v.get("signal", "NEUTRAL") for v in osc.values()] +
        [v.get("signal", "NEUTRAL") for v in trend.values()]
    )
    non_neutral = [s for s in all_sigs if s != "NEUTRAL"]
    if len(non_neutral) >= 5 and len(set(non_neutral)) == 1:
        signal = non_neutral[0]
    else:
        signal = "NEUTRAL"
    results["All_AND_Consensus"] = {
        "value": len(non_neutral),
        "signal": signal,
        "category": "composite",
        "details": {
            "agreeing_count": len(non_neutral),
            "total_checked": len(all_sigs),
        },
    }

    return results
