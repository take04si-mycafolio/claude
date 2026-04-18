"""
カスタム V2 複合指標の評価モジュール

custom_v2_indicators テーブルに登録された戦略設定を読み込み、
最新確定バー（df.iloc[-2]）に対して entry_conditions を評価して
BUY / SELL / NEUTRAL シグナルを返す。
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_custom(df: pd.DataFrame) -> dict:
    """
    DB の全アクティブなカスタム指標を評価して返す。
    app context が必要（Flask のリクエスト外では app.app_context() で呼ぶこと）。
    """
    try:
        from app.models.custom_indicator import CustomV2Indicator
    except Exception:
        return {}

    if df is None or len(df) < 3:
        return {}

    try:
        from app.services.condition_evaluator import evaluate_group
    except Exception as e:
        logger.warning("condition_evaluator import failed: %s", e)
        return {}

    idx = len(df) - 2   # 最新確定バー

    results: dict = {}
    try:
        indicators = CustomV2Indicator.query.filter_by(is_active=True).all()
    except Exception as e:
        logger.warning("custom_v2_indicators query failed: %s", e)
        return {}

    for ind in indicators:
        cfg    = ind.strategy_config or {}
        signal = "NEUTRAL"

        if cfg.get("version") == "2.0":
            # v2.0: evaluate BUY and SELL sides independently
            for side_dir, side_key in (("BUY", "buy"), ("SELL", "sell")):
                side_cfg = cfg.get(side_key)
                if not side_cfg:
                    continue
                entry_cg = side_cfg.get("entry_conditions")
                if not entry_cg:
                    continue
                try:
                    ok, _ = evaluate_group(entry_cg, df, idx)
                    if ok:
                        signal = side_dir
                        break
                except Exception as e:
                    logger.debug("CustomV2 [%s] %s evaluate error: %s", ind.name, side_dir, e)
        else:
            direction = cfg.get("direction", "BUY")
            entry_cg  = cfg.get("entry_conditions")
            if entry_cg:
                try:
                    ok, _ = evaluate_group(entry_cg, df, idx)
                    if ok:
                        signal = "BUY" if direction in ("BUY", "BOTH") else "SELL"
                except Exception as e:
                    logger.debug("CustomV2 [%s] evaluate error: %s", ind.name, e)

        results[ind.name] = {
            "value":    1.0 if signal != "NEUTRAL" else 0.0,
            "signal":   signal,
            "category": "カスタム複合",
            "details":  {"display": ind.display_name},
        }

    return results
