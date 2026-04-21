#!/usr/bin/env python3
"""
DB診断スクリプト — session_ranking_results / session_trade_history の状態を確認する。
使い方: python tasks/check_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")

import sqlalchemy as sa
from app.config import Config

engine = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI)

def run(sql, params=None):
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params or {}).fetchall()
    return rows

print("=" * 60)
print("【session_ranking_results】")
rows = run("""
    SELECT session_key, snapshot_date, COUNT(*) AS cnt
    FROM session_ranking_results
    GROUP BY session_key, snapshot_date
    ORDER BY snapshot_date DESC, session_key
""")
if rows:
    for r in rows:
        print(f"  {r[0]:8s}  {r[1]}  {r[2]}件")
else:
    print("  (データなし)")

print()
print("【session_ranking_results — 最新ランキング内訳】")
rows = run("""
    SELECT r.session_key, r.rank_position, r.indicator_name,
           r.win_rate, r.profit_factor, r.total_trades, r.score, r.snapshot_date
    FROM session_ranking_results r
    INNER JOIN (
        SELECT session_key, MAX(snapshot_date) AS md
        FROM session_ranking_results GROUP BY session_key
    ) latest ON r.session_key = latest.session_key AND r.snapshot_date = latest.md
    ORDER BY r.session_key, r.rank_position
""")
if rows:
    cur_sess = None
    for r in rows:
        if r[0] != cur_sess:
            cur_sess = r[0]
            print(f"\n  [{cur_sess}]  ({r[7]})")
        print(f"    {r[1]}位  {r[2]:<30s}  勝率{r[3]}%  PF{r[4]}  {r[5]}回  score{r[6]}")
else:
    print("  (データなし)")

print()
print("【session_trade_history — 日付別件数】")
rows = run("""
    SELECT session_key, trade_date, COUNT(*) AS cnt
    FROM session_trade_history
    GROUP BY session_key, trade_date
    ORDER BY trade_date DESC, session_key
    LIMIT 30
""")
if rows:
    for r in rows:
        print(f"  {r[0]:8s}  {r[1]}  {r[2]}件")
else:
    print("  (データなし)")

print()
print("【simulation_trades — 最新5件】")
rows = run("""
    SELECT indicator_name, currency_pair, timeframe,
           DATE_ADD(entry_at, INTERVAL 9 HOUR) AS entry_jst, outcome
    FROM simulation_trades
    ORDER BY entry_at DESC LIMIT 5
""")
for r in rows:
    print(f"  {r[0]:<30s}  {r[1]}  {r[2]}  {r[3]}  {r[4]}")

print("=" * 60)
