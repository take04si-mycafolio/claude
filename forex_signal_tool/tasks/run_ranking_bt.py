#!/usr/bin/env python3
"""
ランキングページ用バックテスト
SEO管理画面から手動実行。開始日〜終了日を指定してバックテストを実行し、
結果をDBに保存・手法別おすすめを自動生成する。
日足は swing_start_date / swing_end_date を使用。
"""

import sys
import os
import json
import logging
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PARAMS_FILE = "/tmp/ranking_bt_params.json"
RESULT_FILE = "/tmp/ranking_bt_result.json"

SHORT_TFS = ["5min", "15min", "30min"]
DAY_TFS   = ["1hr", "4hr"]
SWING_TFS = ["daily"]

TF_LABELS = {
    "5min": "5分足", "15min": "15分足", "30min": "30分足",
    "1hr":  "1時間足", "4hr": "4時間足", "daily": "日足",
}


# ---------- ユーティリティ ----------

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


def parse_date(s: str):
    """'YYYY-MM-DD' → datetime（naive）"""
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def filter_df_by_range(df, start_str: str, end_str: str):
    """DataFrame を日付でフィルタ。開始・終了が空なら全期間。"""
    s = parse_date(start_str)
    e = parse_date(end_str)
    if s:
        df = df[df["timestamp"] >= s]
    if e:
        e_end = e.replace(hour=23, minute=59, second=59)
        df = df[df["timestamp"] <= e_end]
    return df.copy()


# ---------- スコア計算（JSと同じロジック） ----------

def calc_score(r: dict) -> int:
    wr = float(r.get("win_rate")      or 0)
    pf = float(r.get("profit_factor") or 0)
    n  = int(r.get("total_trades")    or 0)
    sl = float(r.get("sl_pips")       or 0)
    tp = float(r.get("tp_pips")       or 0)
    dd = abs(float(r.get("max_drawdown") or 0))

    dd_pct = (dd / 1_000_000) * 100
    ev = (wr / 100) * tp - (1 - wr / 100) * sl

    if   wr >= 60: wr_s = 30
    elif wr >= 58: wr_s = 27
    elif wr >= 56: wr_s = 24
    elif wr >= 54: wr_s = 20
    elif wr >= 52: wr_s = 16
    elif wr >= 50: wr_s = 12
    else:          wr_s = max(0, int(wr / 50 * 8))

    if   pf >= 1.50: pf_s = 25
    elif pf >= 1.40: pf_s = 22
    elif pf >= 1.30: pf_s = 18
    elif pf >= 1.20: pf_s = 14
    elif pf >= 1.10: pf_s = 10
    elif pf >= 1.00: pf_s = 6
    else:            pf_s = 0

    if   dd_pct <  5: dd_s = 20
    elif dd_pct <  8: dd_s = 17
    elif dd_pct < 12: dd_s = 14
    elif dd_pct < 16: dd_s = 10
    elif dd_pct < 20: dd_s = 6
    else:             dd_s = 2

    if   n >= 500: n_s = 15
    elif n >= 300: n_s = 12
    elif n >= 150: n_s = 9
    elif n >= 80:  n_s = 6
    elif n >= 30:  n_s = 3
    else:          n_s = 0

    if   ev >  5: ev_s = 10
    elif ev >  2: ev_s = 8
    elif ev >  0: ev_s = 6
    elif ev > -2: ev_s = 3
    else:         ev_s = 0

    return wr_s + pf_s + dd_s + n_s + ev_s


# ---------- 手法別おすすめ自動生成 ----------

def generate_recommendations(all_results: list, ind_info: dict = None) -> dict:
    """
    バックテスト結果から手法別・ペア別スコア上位5件を生成。
    返す形式:
      {"short": {"USDJPY": [...], ...}, "day": {...}, "swing": {...}}

    ind_info: INDICATOR_INFO を外部から渡せる（循環インポート回避用）
    """
    if ind_info is None:
        try:
            from tasks.generate_static import INDICATOR_INFO as _II
            ind_info = _II
        except ImportError:
            ind_info = {}

    method_tfs = {
        "short": SHORT_TFS,
        "day":   DAY_TFS,
        "swing": SWING_TFS,
    }
    pairs = ["USDJPY", "GBPJPY", "EURJPY"]

    # スコア付け
    scored = []
    for r in all_results:
        r = dict(r)
        r["_score"] = calc_score(r)
        scored.append(r)

    result = {}
    for method, tfs in method_tfs.items():
        result[method] = {}
        for pair in pairs:
            filtered = [
                r for r in scored
                if r["currency_pair"] == pair and r["timeframe"] in tfs
            ]
            filtered.sort(key=lambda x: x["_score"], reverse=True)
            top5 = filtered[:5]

            recs = []
            for r in top5:
                ind_name = r.get("indicator_name", "")
                info     = ind_info.get(ind_name, {})
                display  = info.get("display", ind_name)
                tf_lbl   = TF_LABELS.get(r.get("timeframe", ""), r.get("timeframe", ""))
                recs.append({
                    "indicator_name": ind_name,
                    "indicator":      display,
                    "pair":           pair[:3] + "/" + pair[3:],
                    "tf":             tf_lbl,
                    "win_rate":       round(float(r.get("win_rate")      or 0), 1),
                    "profit_factor":  round(float(r.get("profit_factor") or 0), 2),
                    "total_trades":   int(r.get("total_trades") or 0),
                    "score":          r["_score"],
                    "description":    (
                        f"勝率 {float(r.get('win_rate') or 0):.1f}% ／ "
                        f"PF {float(r.get('profit_factor') or 0):.2f} ／ "
                        f"{r.get('total_trades', 0)}回"
                    ),
                })
            result[method][pair] = recs

    return result


def save_recommendations_to_db(recs: dict):
    """推薦データを site_content テーブルに保存"""
    import sqlalchemy as sa
    from app.config import Config

    engine = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI)
    key_map = {
        "short": "ranking_short_term",
        "day":   "ranking_day_trade",
        "swing": "ranking_swing",
    }
    with engine.connect() as conn:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS site_content (
                content_key   VARCHAR(100) NOT NULL PRIMARY KEY,
                content_value MEDIUMTEXT,
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        for method, key in key_map.items():
            val = json.dumps(recs[method], ensure_ascii=False)
            conn.execute(sa.text("""
                INSERT INTO site_content (content_key, content_value) VALUES (:k, :v)
                ON DUPLICATE KEY UPDATE content_value=VALUES(content_value), updated_at=NOW()
            """), {"k": key, "v": val})
        conn.commit()
    logger.info("手法別おすすめを site_content に保存完了")


# ---------- セッション別データ保存 ----------

def _session_score(wr: float, pf: float, total: int) -> int:
    """セッションランキング用スコア（calc_score の簡易版）"""
    if   wr >= 60: wr_s = 30
    elif wr >= 58: wr_s = 27
    elif wr >= 56: wr_s = 24
    elif wr >= 54: wr_s = 20
    elif wr >= 52: wr_s = 16
    elif wr >= 50: wr_s = 12
    else:          wr_s = max(0, int(wr / 50 * 8))

    if   pf >= 1.50: pf_s = 25
    elif pf >= 1.40: pf_s = 22
    elif pf >= 1.30: pf_s = 18
    elif pf >= 1.20: pf_s = 14
    elif pf >= 1.10: pf_s = 10
    elif pf >= 1.00: pf_s = 6
    else:            pf_s = 0

    if   total >= 500: n_s = 15
    elif total >= 300: n_s = 12
    elif total >= 150: n_s = 9
    elif total >= 80:  n_s = 6
    elif total >= 30:  n_s = 3
    else:              n_s = 0

    return wr_s + pf_s + n_s


def save_session_data_to_db(days: int = 30, target_date=None):
    """
    simulation_trades からセッション別データを計算し2テーブルに保存。

    処理の流れ:
      1. target_date のトレードを simulation_trades から取得
      2. session_trade_history に保存（30日ローリング固定）
      3. session_trade_history の全蓄積データからセッション別ランキングを再計算
         → days の大小に関わらず常に蓄積済み全データを使うため
            ロンドン・NYも十分なサンプルでランキングが生成される

    target_date: 保存対象日（None=当日、"YYYY-MM-DD" or date オブジェクト）
    days       : simulation_trades の参照期間（backfill用、デフォルト30）
    """
    import sqlalchemy as sa
    from app.config import Config
    from collections import defaultdict
    from datetime import date, datetime as _dt, timedelta, timezone

    RETENTION_DAYS = 30  # 履歴保持期間は常に30日固定
    engine = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI)

    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = _dt.strptime(target_date, "%Y-%m-%d").date()

    cutoff = target_date - timedelta(days=RETENTION_DAYS)
    now    = datetime.now(timezone.utc).replace(tzinfo=None)

    # target_date 当日のトレードのみ取得（セッション分類付き）
    SESSION_SQL = """
        SELECT
            indicator_name,
            currency_pair,
            timeframe,
            entry_at,
            direction,
            entry_price,
            tp_price,
            sl_price,
            sl_pips,
            tp_pips,
            exit_at,
            exit_price,
            outcome,
            profit_loss,
            CASE
                WHEN HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) >= 8
                 AND HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) < 15 THEN 'japan'
                WHEN HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) >= 15
                 AND HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) < 21 THEN 'london'
                ELSE 'ny'
            END AS session_key,
            DATE(DATE_ADD(entry_at, INTERVAL 9 HOUR)) AS trade_date
        FROM simulation_trades
        WHERE outcome IN ('WIN', 'LOSS')
          AND DATE(DATE_ADD(entry_at, INTERVAL 9 HOUR)) = :target_date
    """

    with engine.connect() as conn:
        # PF/DD ルックアップ（指標名 → backtest_results の最良値）
        bt_rows = conn.execute(sa.text(
            "SELECT indicator_name, profit_factor, max_drawdown "
            "FROM backtest_results ORDER BY win_rate DESC"
        )).fetchall()
        bt_lk = {}
        for br in bt_rows:
            if br[0] not in bt_lk:
                bt_lk[br[0]] = {"pf": float(br[1] or 0), "dd": float(br[2] or 0)}

        # ── Step1: session_trade_history 更新 ──
        rows = conn.execute(sa.text(SESSION_SQL), {"target_date": target_date}).fetchall()

        # 30日より古いデータを削除
        conn.execute(sa.text(
            "DELETE FROM session_trade_history WHERE trade_date < :cutoff"
        ), {"cutoff": cutoff})
        # target_date 分を削除して再挿入
        conn.execute(sa.text(
            "DELETE FROM session_trade_history WHERE trade_date = :target_date"
        ), {"target_date": target_date})
        for r in rows:
            conn.execute(sa.text("""
                INSERT INTO session_trade_history
                (session_key, trade_date, indicator_name, currency_pair, timeframe,
                 entry_at, direction, entry_price, tp_price, sl_price, sl_pips, tp_pips,
                 exit_at, exit_price, outcome, profit_loss, created_at)
                VALUES (:sk, :td, :ind, :cp, :tf, :ea, :dir, :ep, :tp, :sl,
                        :slp, :tpp, :xa, :xp, :oc, :pl, :ca)
            """), {
                "sk":  r.session_key,  "td": r.trade_date,    "ind": r.indicator_name,
                "cp":  r.currency_pair, "tf": r.timeframe,
                "ea":  r.entry_at,     "dir": r.direction,    "ep":  r.entry_price,
                "tp":  r.tp_price,     "sl":  r.sl_price,     "slp": r.sl_pips,
                "tpp": r.tp_pips,      "xa":  r.exit_at,      "xp":  r.exit_price,
                "oc":  r.outcome,      "pl":  r.profit_loss,  "ca":  now,
            })
        conn.commit()
        logger.info("  session_trade_history 更新完了: %s (%d件)", target_date, len(rows))

        # ── Step2: session_ranking_results を蓄積全データから再計算 ──
        # 蓄積済み session_trade_history を session × indicator で集計
        agg_rows = conn.execute(sa.text("""
            SELECT
                session_key,
                indicator_name,
                COUNT(*)              AS total,
                SUM(outcome = 'WIN')  AS wins,
                AVG(profit_loss)      AS avg_pnl
            FROM session_trade_history
            GROUP BY session_key, indicator_name
            HAVING COUNT(*) >= 3
        """)).fetchall()

        conn.execute(sa.text(
            "DELETE FROM session_ranking_results WHERE snapshot_date = :target_date"
        ), {"target_date": target_date})

        sess_cards = defaultdict(list)
        for r in agg_rows:
            sk      = r[0]
            ind     = r[1]
            total   = int(r[2])
            wins    = int(r[3])
            avg_pnl = float(r[4] or 0)
            wr      = round(wins / total * 100, 1)
            bt      = bt_lk.get(ind, {})
            pf      = bt.get("pf", 0.0)
            dd      = bt.get("dd", 0.0)
            score   = _session_score(wr, pf if pf > 0 else 1.0, total)
            sess_cards[sk].append({
                "indicator_name": ind,
                "win_rate":       wr,
                "profit_factor":  pf,
                "max_drawdown":   dd,
                "total_trades":   total,
                "avg_pnl":        round(avg_pnl, 0),
                "score":          score,
            })

        for sk, cards in sess_cards.items():
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
                    "sk": sk, "d": target_date, "rk": rank, "ind": c["indicator_name"],
                    "wr": c["win_rate"],    "pf": c["profit_factor"],
                    "dd": c["max_drawdown"], "tr": c["total_trades"],
                    "ap": c["avg_pnl"],     "sc": c["score"], "ca": now,
                })
        conn.commit()
    logger.info("セッション別データ保存完了 (日付=%s, 集計対象=%d件)", target_date, len(agg_rows))


# ---------- メイン ----------

def main():
    if not os.path.exists(PARAMS_FILE):
        write_status("error", "パラメータファイルが見つかりません")
        return

    with open(PARAMS_FILE, encoding="utf-8") as f:
        params = json.load(f)

    start_date   = params.get("start_date", "")
    end_date     = params.get("end_date", "")
    swing_start  = params.get("swing_start_date") or start_date
    swing_end    = params.get("swing_end_date")   or end_date
    force_full   = bool(params.get("force_full", False))

    init_msg = "初期化中（データリセット + フルバックテスト）..." if force_full else "初期化中..."
    write_status("running", init_msg, {"started_at": int(time.time())})

    from app import create_app
    from app.config import Config
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_all_backtests, save_backtest_results

    app = create_app()
    with app.app_context():
        from app.models.settings import Setting
        from app.models.backtest import BacktestResult
        from app.models.simulation_trade import SimulationTrade
        import sqlalchemy as _sa

        sl_pips         = Setting.get_float("sl_pips",         20.0)
        tp_pips         = Setting.get_float("tp_pips",         40.0)
        initial_capital = Setting.get_float("initial_capital", 1_000_000)

        all_bt_results = []
        total_saved    = 0
        all_tfs        = SHORT_TFS + DAY_TFS + SWING_TFS
        total_steps    = len(Config.CURRENCY_PAIRS) * len(all_tfs)
        step           = 0

        for pair in Config.CURRENCY_PAIRS:
            for tf in all_tfs:
                step += 1
                is_swing = (tf in SWING_TFS)
                s_date   = swing_start if is_swing else start_date
                e_date   = swing_end   if is_swing else end_date

                write_status(
                    "running",
                    f"[{step}/{total_steps}] {pair} {TF_LABELS.get(tf, tf)} 実行中...",
                )

                # 各TF 2000本取得（統計上十分かつ処理速度優先）
                df = get_candles(pair, tf, limit=2000)
                if df.empty:
                    logger.warning("データなし: %s %s", pair, tf)
                    continue

                df = filter_df_by_range(df, s_date, e_date)

                if len(df) < 30:
                    logger.warning("期間内データ不足: %s %s (%d件)", pair, tf, len(df))
                    continue

                # ---- インクリメンタルバックテスト判定 ----
                # force_full=True のときは既存データを削除してフルバックテスト
                # SL/TPが同じで既存トレードがある場合は新規分のみ処理する
                incremental_from_ts = None
                recompute_stats     = False

                from app import db as _db

                if force_full:
                    # 既存データを削除してフルバックテスト
                    del_trades = SimulationTrade.query.filter_by(
                        currency_pair=pair, timeframe=tf
                    ).delete()
                    del_bt = BacktestResult.query.filter_by(
                        currency_pair=pair, timeframe=tf
                    ).delete()
                    _db.session.commit()
                    logger.info("  リセット: %s %s (trades=%d件, results=%d件削除)", pair, tf, del_trades, del_bt)
                else:
                    last_exit = _db.session.execute(
                        _sa.select(_sa.func.max(SimulationTrade.exit_at)).where(
                            SimulationTrade.currency_pair == pair,
                            SimulationTrade.timeframe     == tf,
                        )
                    ).scalar()

                    if last_exit is not None:
                        existing_bt = BacktestResult.query.filter_by(
                            currency_pair=pair, timeframe=tf
                        ).first()
                        sl_tp_ok = (
                            existing_bt is not None
                            and abs(float(existing_bt.sl_pips or 0) - sl_pips) < 0.001
                            and abs(float(existing_bt.tp_pips or 0) - tp_pips) < 0.001
                        )
                        if sl_tp_ok:
                            # tz-naive に統一して比較
                            le = last_exit.replace(tzinfo=None) if hasattr(last_exit, "tzinfo") and last_exit.tzinfo else last_exit
                            latest_ts = df["timestamp"].max()
                            if hasattr(latest_ts, "to_pydatetime"):
                                latest_ts = latest_ts.to_pydatetime()
                            latest_ts = latest_ts.replace(tzinfo=None) if latest_ts.tzinfo else latest_ts

                            if latest_ts <= le:
                                logger.info("  新規キャンドルなし、スキップ: %s %s", pair, tf)
                                continue

                            incremental_from_ts = le
                            recompute_stats     = True
                            logger.info("  インクリメンタルモード: %s %s (last_exit=%s)", pair, tf, le)
                        else:
                            logger.info("  SL/TP変更 or 初回: %s %s (フルBT)", pair, tf)

                results = run_all_backtests(
                    pair=pair, timeframe=tf, df=df,
                    initial_capital=initial_capital,
                    sl_pips=sl_pips, tp_pips=tp_pips,
                    backtest_hours=99999,           # df全体を使用
                    incremental_from_ts=incremental_from_ts,
                )
                saved = save_backtest_results(results, recompute_stats=recompute_stats)
                total_saved += saved
                all_bt_results.extend(results)
                logger.info("  %s %s: %d件保存%s", pair, tf, saved,
                            " (インクリメンタル)" if incremental_from_ts else "")

        logger.info("バックテスト完了: 合計%d件保存", total_saved)

        # 手法別おすすめ自動生成
        write_status("running", "手法別おすすめ自動生成中...")
        try:
            recs = generate_recommendations(all_bt_results)
            save_recommendations_to_db(recs)
        except Exception as exc:
            logger.warning("おすすめ生成失敗: %s", exc)

        # セッション別ランキング・トレード履歴保存
        write_status("running", "セッション別データ保存中...")
        try:
            save_session_data_to_db()
        except Exception as exc:
            logger.warning("セッションデータ保存失敗: %s", exc)

        # 日次スナップショット保存（バックテスト確定後に記録）
        write_status("running", "スナップショット保存中...")
        try:
            from app.services.backtester import save_daily_snapshot
            snap_count = save_daily_snapshot()
            logger.info("日次スナップショット保存完了: %d件", snap_count)
        except Exception as exc:
            logger.warning("スナップショット保存失敗: %s", exc)

        # 最終更新日時・検証期間を記録
        now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M JST")
        Setting.set("last_backtest_at", now_str)
        Setting.set("backtest_status",  "done")

        # 検証期間（表示用）を保存
        def _fmt(s): return s.replace("-", "/") if s else ""
        s_disp = _fmt(start_date)
        e_disp = _fmt(end_date)
        period_str = f"{s_disp}～{e_disp}" if s_disp and e_disp else s_disp or e_disp
        if period_str:
            Setting.set("backtest_period", period_str)

    # 静的ページ再生成
    write_status("generating", f"静的ページ生成中... (バックテスト{total_saved}件完了)")
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "generate_static.py")
    ret    = subprocess.call([sys.executable, script])

    if ret == 0:
        write_status("done", f"完了: バックテスト{total_saved}件 / 静的ページ生成済み", {
            "total_saved": total_saved,
        })
    else:
        write_status("done", f"バックテスト完了({total_saved}件) ※静的ページ生成失敗", {
            "total_saved": total_saved,
            "static_error": True,
        })


if __name__ == "__main__":
    main()
