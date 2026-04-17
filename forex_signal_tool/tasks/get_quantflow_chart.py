#!/usr/bin/env python3
"""
QuantFlow スコアチャートデータを JSON で出力する。
PHP admin の api.php から exec() で同期呼び出しされる。
"""
import sys
import os
import json
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DISPLAY_HOURS = 168  # 表示期間: 直近 1 週間


def main():
    from app import create_app
    from app.services.data_fetcher import get_candles
    from app.services.quantflow_backtest import _compute_scores, WARMUP

    limit = WARMUP + DISPLAY_HOURS + 20

    app = create_app()
    with app.app_context():
        df = get_candles("USDJPY", "1hr", limit=limit)
        if df.empty:
            print(json.dumps({"ok": False, "error": "1hr データなし"}))
            return

        df = df.reset_index(drop=True)
        scores = _compute_scores(df, limit)

        start_idx = max(WARMUP, len(df) - DISPLAY_HOURS)
        result = []
        for i in range(start_idx, len(df)):
            score = scores[i]
            if score is None or math.isnan(float(score)):
                score = None

            ts = df["timestamp"].iloc[i]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)

            result.append({
                "ts":    ts.strftime("%m/%d %H:%M"),
                "score": int(score) if score is not None else None,
                "close": round(float(df["close"].iloc[i]), 3),
            })

        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
