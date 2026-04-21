#!/usr/bin/env python3
"""
セッション専用バックテスト

東京・ロンドン・NY 各時間帯に限定したローソク足だけでバックテストを実行し、
結果を session_ranking_results に直接保存する。
simulation_trades / backtest_results は変更しない。
"""
import sys
import os
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta, date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARAMS_FILE = "/tmp/session_bt_params.json"
RESULT_FILE = "/tmp/session_bt_result.json"

SHORT_TFS = ["5min", "15min", "30min"]
DAY_TFS   = ["1hr", "4hr"]
# daily は1本が丸1日のデータなのでセッションフィルタ対象外

TF_LABELS = {
    "5min": "5分足", "15min": "15分足", "30min": "30分足",
    "1hr":  "1時間足", "4hr": "4時間足",
}

SESSIONS = [
    {"key": "japan",  "label": "東京",   "jst_start":  8, "jst_end": 15},
    {"key": "london", "label": "ロンドン", "jst_start": 15, "jst_end": 21},
    {"key": "ny",     "label": "NY",      "jst_start": 21, "jst_end":  8},  # 深夜0時またぎ
]


def write_status(status: str, message: str, extra: dict = None):
    data = {
        "status":     status,
        "message":    message,
        "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
    }
    if extra:
        data.update(extra)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def filter_session(df: pd.DataFrame, sess: dict) -> pd.DataFrame:
    """DataFrame を JST セッション時間帯でフィルタ（timestamp は UTC naive）"""
    jst_hour = (df["timestamp"] + pd.Timedelta(hours=9)).dt.hour
    s, e = sess["jst_start"], sess["jst_end"]
    if s < e:
        mask = (jst_hour >= s) & (jst_hour < e)
    else:
        mask = (jst_hour >= s) | (jst_hour < e)
    return df[mask].copy()


def parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def main():
    if not os.path.exists(PARAMS_FILE):
        write_status("error", "パラメータファイルが見つかりません")
        return

    with open(PARAMS_FILE, encoding="utf-8") as f:
        params = json.load(f)

    start_date = params.get("start_date", "")
    end_date   = params.get("end_date", "")

    write_status("running", "初期化中...", {"started_at": int(time.time())})

    from app import create_app
    from app.config import Config
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_all_backtests
    from tasks.run_ranking_bt import _session_score

    app = create_app()
    with app.app_context():
        import sqlalchemy as sa
        from app.models.settings import Setting

        sl_pips         = Setting.get_float("sl_pips",         20.0)
        tp_pips         = Setting.get_float("tp_pips",         40.0)
        initial_capital = Setting.get_float("initial_capital", 1_000_000)

        engine  = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI)
        today   = date.today()
        now     = datetime.now(timezone.utc).replace(tzinfo=None)

        all_tfs     = SHORT_TFS + DAY_TFS
        total_steps = len(SESSIONS) * len(Config.CURRENCY_PAIRS) * len(all_tfs)
        step        = 0

        # sess_agg[session_key][indicator_name] = {total, wins, losses, dd, tp_sum}
        # PF は個別値の平均ではなく、合計勝利×TP / 合計敗北×SL で正しく計算する
        sess_agg = {
            s["key"]: defaultdict(lambda: {
                "total": 0, "wins": 0, "losses": 0, "dd": 0.0, "tp_sum": 0.0
            })
            for s in SESSIONS
        }

        trade_cutoff   = today - timedelta(days=30)
        all_trade_rows = []   # session_trade_history に保存する個別トレード

        for sess in SESSIONS:
            sk = sess["key"]
            for pair in Config.CURRENCY_PAIRS:
                for tf in all_tfs:
                    step += 1
                    write_status(
                        "running",
                        f"[{step}/{total_steps}] {sess['label']} {pair} {TF_LABELS.get(tf, tf)} ..."
                    )

                    df = get_candles(pair, tf, limit=2000)
                    if df.empty:
                        logger.warning("データなし: %s %s", pair, tf)
                        continue

                    # 日付範囲フィルタ
                    s_dt = parse_date(start_date)
                    e_dt = parse_date(end_date)
                    if s_dt:
                        df = df[df["timestamp"] >= s_dt]
                    if e_dt:
                        df = df[df["timestamp"] <= e_dt.replace(hour=23, minute=59, second=59)]

                    # セッション時間帯フィルタ
                    session_df = filter_session(df, sess)

                    if len(session_df) < 50:
                        logger.info("  データ不足スキップ: %s %s %s (%d本)",
                                    sk, pair, tf, len(session_df))
                        continue

                    results = run_all_backtests(
                        pair=pair, timeframe=tf, df=session_df,
                        initial_capital=initial_capital,
                        sl_pips=sl_pips, tp_pips=tp_pips,
                        backtest_hours=99999,
                    )

                    for r in results:
                        if not r:
                            continue
                        ind = r.get("indicator_name", "")
                        n   = int(r.get("total_trades") or 0)
                        if n == 0:
                            continue
                        wins = int(r.get("winning_trades") or 0)
                        dd   = abs(float(r.get("max_drawdown") or 0))
                        tp   = float(r.get("total_profit") or 0)

                        d = sess_agg[sk][ind]
                        d["total"]  += n
                        d["wins"]   += wins
                        d["losses"] += (n - wins)
                        d["dd"]      = max(d["dd"], dd)
                        d["tp_sum"] += tp

                        # 過去30日分の個別トレードを収集
                        for t in r.get("trades", []):
                            ets = t["entry_ts"]
                            if hasattr(ets, "to_pydatetime"):
                                ets = ets.to_pydatetime()
                            ets_jst = ets + timedelta(hours=9)
                            trade_date_jst = ets_jst.date()
                            # NYセッションは深夜0時またぎ。JST 00:00-07:59 のトレードは
                            # 前日21:00から続くNYセッション分なので1日戻す
                            if sk == "ny" and ets_jst.hour < 8:
                                trade_date_jst = trade_date_jst - timedelta(days=1)
                            if trade_date_jst < trade_cutoff:
                                continue
                            xts = t.get("exit_ts")
                            if xts is not None and hasattr(xts, "to_pydatetime"):
                                xts = xts.to_pydatetime()
                            all_trade_rows.append({
                                "sk":  sk,
                                "td":  trade_date_jst,
                                "ind": ind,
                                "cp":  pair,
                                "tf":  tf,
                                "ea":  ets,
                                "dir": t.get("signal", ""),
                                "ep":  t.get("entry_price"),
                                "tpp": t.get("tp_price"),
                                "slp": t.get("sl_price"),
                                "slpips": sl_pips,
                                "tppips": tp_pips,
                                "xa":  xts,
                                "xp":  t.get("exit_price"),
                                "oc":  t.get("outcome"),
                                "pl":  t.get("profit_loss"),
                                "ca":  now,
                            })

                    logger.info("  %s %s %s: %d件", sk, pair, tf, len(results))

        # ── session_trade_history に保存（30日ローリング）──
        write_status("running", f"トレード履歴保存中 ({len(all_trade_rows)}件)...")
        with engine.connect() as conn:
            conn.execute(sa.text(
                "DELETE FROM session_trade_history WHERE trade_date < :c"
            ), {"c": trade_cutoff})
            conn.execute(sa.text(
                "DELETE FROM session_trade_history WHERE trade_date >= :c"
            ), {"c": trade_cutoff})
            for t in all_trade_rows:
                conn.execute(sa.text("""
                    INSERT INTO session_trade_history
                    (session_key, trade_date, indicator_name, currency_pair, timeframe,
                     entry_at, direction, entry_price, tp_price, sl_price,
                     sl_pips, tp_pips, exit_at, exit_price, outcome, profit_loss, created_at)
                    VALUES (:sk, :td, :ind, :cp, :tf, :ea, :dir, :ep, :tpp, :slp,
                            :slpips, :tppips, :xa, :xp, :oc, :pl, :ca)
                """), t)
            conn.commit()
        logger.info("session_trade_history 保存完了: %d件", len(all_trade_rows))

        # ── session_ranking_results に保存 ──
        write_status("running", "ランキング保存中...")
        with engine.connect() as conn:
            conn.execute(sa.text(
                "DELETE FROM session_ranking_results WHERE snapshot_date = :d"
            ), {"d": today})

            for sess in SESSIONS:
                sk    = sess["key"]
                cards = []
                for ind, d in sess_agg[sk].items():
                    n = d["total"]
                    if n < 5:
                        continue
                    wr      = round(d["wins"] / n * 100, 1)
                    pf      = round((d["wins"] * tp_pips) / (d["losses"] * sl_pips), 4) if d["losses"] > 0 else 0.0
                    dd      = d["dd"]
                    avg_pnl = round(d["tp_sum"] / n, 0)
                    score   = _session_score(wr, pf if pf > 0 else 1.0, n)
                    cards.append({
                        "indicator_name": ind,
                        "win_rate":       wr,
                        "profit_factor":  pf,
                        "max_drawdown":   dd,
                        "total_trades":   n,
                        "avg_pnl":        avg_pnl,
                        "score":          score,
                    })

                for rank, c in enumerate(
                    sorted(cards, key=lambda x: x["score"], reverse=True)[:5], 1
                ):
                    conn.execute(sa.text("""
                        INSERT INTO session_ranking_results
                        (session_key, snapshot_date, rank_position, indicator_name,
                         win_rate, profit_factor, max_drawdown, total_trades,
                         avg_pnl, score, computed_at)
                        VALUES (:sk, :d, :rk, :ind, :wr, :pf, :dd, :tr, :ap, :sc, :ca)
                    """), {
                        "sk": sk,  "d": today,           "rk":  rank,
                        "ind": c["indicator_name"],
                        "wr": c["win_rate"],    "pf": c["profit_factor"],
                        "dd": c["max_drawdown"], "tr": c["total_trades"],
                        "ap": c["avg_pnl"],     "sc": c["score"], "ca": now,
                    })
            conn.commit()
        logger.info("session_ranking_results 保存完了")

    # 静的ページ再生成
    write_status("running", "静的ページ生成中...")
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    ret    = subprocess.call([sys.executable, script])

    if ret == 0:
        write_status("done", "セッション専用バックテスト完了・静的ページ生成済み")
    else:
        write_status("done", "セッション専用バックテスト完了 ※静的ページ生成失敗")
    logger.info("セッション専用バックテスト終了")


if __name__ == "__main__":
    main()
