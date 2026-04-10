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
from datetime import datetime, timezone

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

def generate_recommendations(all_results: list) -> dict:
    """
    バックテスト結果から手法別・ペア別スコア上位5件を生成。
    返す形式:
      {"USDJPY": [...5件], "GBPJPY": [...5件], "EURJPY": [...5件]}
    """
    # INDICATOR_INFO をインポートして表示名を取得
    try:
        from tasks.generate_static import INDICATOR_INFO
    except ImportError:
        INDICATOR_INFO = {}

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
                info     = INDICATOR_INFO.get(ind_name, {})
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

    write_status("running", "初期化中...", {"started_at": int(time.time())})

    from app import create_app
    from app.config import Config
    from app.services.data_fetcher import get_candles
    from app.services.backtester import run_all_backtests, save_backtest_results

    app = create_app()
    with app.app_context():
        from app.models.settings import Setting

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

                # 日足は多め、その他は5000本取得
                limit = 2000 if tf == "daily" else 5000
                df = get_candles(pair, tf, limit=limit)
                if df.empty:
                    logger.warning("データなし: %s %s", pair, tf)
                    continue

                df = filter_df_by_range(df, s_date, e_date)

                if len(df) < 30:
                    logger.warning("期間内データ不足: %s %s (%d件)", pair, tf, len(df))
                    continue

                results = run_all_backtests(
                    pair=pair, timeframe=tf, df=df,
                    initial_capital=initial_capital,
                    sl_pips=sl_pips, tp_pips=tp_pips,
                    backtest_hours=99999,           # df全体を使用
                )
                saved = save_backtest_results(results)
                total_saved += saved
                all_bt_results.extend(results)
                logger.info("  %s %s: %d件保存", pair, tf, saved)

        logger.info("バックテスト完了: 合計%d件保存", total_saved)

        # 手法別おすすめ自動生成
        write_status("running", "手法別おすすめ自動生成中...")
        try:
            recs = generate_recommendations(all_bt_results)
            save_recommendations_to_db(recs)
        except Exception as exc:
            logger.warning("おすすめ生成失敗: %s", exc)

        # 最終更新日時を記録
        now_str = datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M UTC")
        Setting.set("last_backtest_at", now_str)
        Setting.set("backtest_status",  "done")

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
