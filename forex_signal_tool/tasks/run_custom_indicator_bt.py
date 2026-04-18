#!/usr/bin/env python3
"""
カスタム複合指標のバックテスト実行タスク
PHP admin の api.php から nohup で呼び出される。

Usage: python3 run_custom_indicator_bt.py --name CustomV2_XXX
"""
import sys, os, argparse, logging

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PAIRS      = ["USDJPY", "GBPJPY", "EURJPY"]
TIMEFRAMES = ["1hr", "4hr", "daily"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="CustomV2Indicator.name")
    args = parser.parse_args()
    ind_name = args.name

    from app import create_app, db
    from app.models.custom_indicator import CustomV2Indicator
    from app.models.settings import Setting
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_backtest_for_indicator, save_backtest_results
    from app.services.condition_evaluator import evaluate_group

    status_key = f"custom_bt_status_{ind_name}"
    app = create_app()

    with app.app_context():
        ind = CustomV2Indicator.query.filter_by(name=ind_name).first()
        if not ind:
            logger.error("指標が見つかりません: %s", ind_name)
            return

        Setting.set(status_key, "running")
        cfg       = ind.strategy_config
        direction = cfg.get("direction", "BUY")
        entry_cg  = cfg.get("entry_conditions")

        def _indicator_func(df):
            try:
                ok, _ = evaluate_group(entry_cg, df, len(df) - 2)
                sig   = (direction if direction in ("BUY", "SELL") else "BUY") if ok else "NEUTRAL"
            except Exception:
                sig = "NEUTRAL"
            return {ind_name: {"signal": sig, "value": 1.0 if ok else 0.0, "category": "カスタム複合"}}

        sl_pips = float(Setting.get("sl_pips", "20"))
        tp_pips = float(Setting.get("tp_pips", "40"))
        capital = float(Setting.get("initial_capital", "1000000"))

        total = 0
        for pair in PAIRS:
            for tf in TIMEFRAMES:
                try:
                    df = get_candles(pair, tf, limit=500)
                    if df.empty or len(df) < 30:
                        continue
                    result = run_backtest_for_indicator(
                        df             = df,
                        indicator_name = ind_name,
                        indicator_func = _indicator_func,
                        pair           = pair,
                        timeframe      = tf,
                        initial_capital= capital,
                        sl_pips        = sl_pips,
                        tp_pips        = tp_pips,
                    )
                    if result:
                        result["indicator_category"] = "カスタム複合"
                        save_backtest_results(result, db.session)
                        total += 1
                        logger.info("%s %s %s: win_rate=%.1f%% trades=%d",
                                    ind_name, pair, tf,
                                    result.get("win_rate", 0),
                                    result.get("total_trades", 0))
                except Exception as e:
                    logger.warning("%s %s %s error: %s", ind_name, pair, tf, e)

        Setting.set(status_key, "done")
        logger.info("完了: %d バックテスト実行", total)


if __name__ == "__main__":
    main()
