"""21日判定確定後に後続対応が無い「放置リライト」を列挙する(LLM不使用・読み取りのみ)。

自動運用(2026-09-06〜)の毎日cron rewrite_followup.sh が最初に呼び、
0件ならヘッドレスClaudeを起動せず終了する(コスト0の空振り)。

「未処理」の定義:
  - status=applied かつ 判定確定(eval_status が pending_eval 以外)
  - (declined / flat / keep_damaged=True) のいずれか = 対応が必要な判定
  - 同一記事に後続の非却下ドラフトが無い(=誰も次の手を打っていない)
  - かつ lesson の最終【後続対応】マーカーが次のいずれか:
      * マーカー無し(未着手)
      * 「様子見」で、記録日から WATCH_DAYS(14日) 経過(=再確認期限到来)
    ※「クローズ」「再リライト」マーカーは完了扱いでキューに戻らない

マーカー書式(処理側のヘッドレスClaudeが lesson に追記):
  【後続対応】YYYY-MM-DD 様子見#N(基準:28日表示X/クリックY/対象クエリ順位Z 根拠:...)
  【後続対応】YYYY-MM-DD クローズ(ノイズ確定・回復済み|低表示・トリアージへ返却)
  【後続対応】YYYY-MM-DD 再リライトDraft#Nを作業台投入(方針:...)
様子見は最大2回(#2まで)。再確認時の昇格/クローズ基準は
/opt/claude-ops/agents/rewrite_followup.md の「様子見の再確認」を正とする。

    python manage.py followup_backlog            # 人間可読
    python manage.py followup_backlog --json     # cron用JSON
    python manage.py followup_backlog --limit 3
"""
import json
import re
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.analytics.models import RewriteDraft

HANDLED_MARK = "【後続対応】"
WATCH_DAYS = 14          # 様子見の再確認期限(日)
MARK_RE = re.compile(r"【後続対応】(\d{4}-\d{2}-\d{2})\s*(\S[^\n]*)")


def _followup_state(lesson):
    """lesson の最終【後続対応】マーカーから (状態, 記録日, 本文) を返す。
    状態: none(未着手) / watch(様子見中) / recheck(様子見の再確認期限到来) / done(完了)"""
    marks = MARK_RE.findall(lesson or "")
    if not marks:
        return ("none", None, "")
    day_s, body = marks[-1]
    try:
        day = date.fromisoformat(day_s)
    except ValueError:
        return ("done", None, body)  # 日付不明の旧形式は完了扱い(誤再処理を避ける)
    if "様子見" in body:
        if date.today() >= day + timedelta(days=WATCH_DAYS):
            return ("recheck", day, body)
        return ("watch", day, body)
    return ("done", day, body)  # クローズ / 再リライト等


def backlog(limit=None):
    qs = (RewriteDraft.objects.filter(status="applied")
          .exclude(eval_status="pending_eval")
          .select_related("article").order_by("measured_at", "id"))
    items = []
    for d in qs:
        needs = d.eval_status in ("declined", "flat") or d.keep_damaged
        if not needs:
            continue
        state, marked_on, mark_body = _followup_state(d.lesson)
        if state in ("done", "watch"):
            continue
        if RewriteDraft.objects.filter(article=d.article, id__gt=d.id)\
                .exclude(status="rejected").exists():
            continue
        items.append({
            "followup_state": state,  # none=初回 / recheck=様子見の再確認
            "watch_marked_on": marked_on.isoformat() if marked_on else None,
            "watch_mark": mark_body[:200],
            "draft_id": d.id,
            "slug": d.article.slug,
            "eval_status": d.eval_status,
            "keep_damaged": d.keep_damaged,
            "grow_before": d.grow_before,
            "grow_after": d.grow_after,
            "target_query": d.target_query,
            "measured_at": d.measured_at.isoformat() if d.measured_at else None,
        })
        if limit and len(items) >= limit:
            break
    return items


class Command(BaseCommand):
    help = "判定確定後に後続対応が無いリライトを列挙する(読み取りのみ)"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **opts):
        items = backlog(opts["limit"])
        if opts["json"]:
            self.stdout.write(json.dumps(items, ensure_ascii=False))
            return
        if not items:
            self.stdout.write("未処理の判定確定リライトはありません")
            return
        for it in items:
            self.stdout.write(
                f"#{it['draft_id']} /{it['slug']}/ {it['eval_status']}"
                f"{'(keep毀損)' if it['keep_damaged'] else ''} "
                f"grow {it['grow_before']}→{it['grow_after']} 測定{it['measured_at']}")
        self.stdout.write(f"計 {len(items)} 件")
