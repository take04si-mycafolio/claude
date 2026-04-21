-- 006_fix_ny_snapshot_date.sql
-- NY セッションの snapshot_date を「開始日」規約にそろえる（1日前倒し）。
--
-- 背景:
--   session_trade_history.trade_date は NY セッションの「開始日」(= 前日 JST)
--   を採用しているが、session_ranking_results.snapshot_date は BT 実行日
--   (= NY セッション終了日) を採用していた。この1日ずれを解消する。
--
-- 影響範囲: session_ranking_results の session_key='ny' 行のみ。
-- 冪等性: UNIQUE (session_key, snapshot_date, indicator_name) があるため、
--   既に前日に該当行があると重複になりうる。念のため先に衝突する行を削除。

-- 1) 衝突しうる既存の「前日側」NY行を先に削除
DELETE r1 FROM session_ranking_results r1
INNER JOIN session_ranking_results r2
    ON r1.session_key   = 'ny'
   AND r2.session_key   = 'ny'
   AND r1.indicator_name = r2.indicator_name
   AND r1.snapshot_date  = DATE_SUB(r2.snapshot_date, INTERVAL 1 DAY);

-- 2) 残った NY 行の snapshot_date を1日戻す
UPDATE session_ranking_results
SET snapshot_date = DATE_SUB(snapshot_date, INTERVAL 1 DAY)
WHERE session_key = 'ny';
