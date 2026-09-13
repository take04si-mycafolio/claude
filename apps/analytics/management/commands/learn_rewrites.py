"""リライト学習ループ（パートD）  python manage.py learn_rewrites

measure_rewrites が確定させた判定（improved/reached_p1/flat/declined）を材料に、

1. applied_tactics が空の判定確定ドラフトへ diff_summary/instructions から戦術を補完抽出
2. 判定確定・未起票のドラフトに「学び(lesson)」の決定論スケルトンを起票
3. RewriteTactic（戦術別成績）を判定確定済み全ドラフトからゼロ再計算（冪等）
4. PlaybookRule の該当ルールに実測エビデンスを書き戻す

LLMは使わない。数値事実の起票と集計のみ。lesson の【分析】行の
質的な要因分析は Claude Code / 人間が admin で追記する。
cron では observe_rewrites.py が measure_rewrites の後に呼ぶ。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.learning import (
    OUTCOME_FIELD, SETTLED, TACTICS, build_lesson_skeleton, extract_tactics)
from apps.analytics.models import PlaybookRule, RewriteDraft, RewriteTactic

# 戦術 → PlaybookRule.key の対応（実測をプレイブックに書き戻す）
TACTIC_TO_RULE = {
    "title_query_match": "title-query-match",
    "commercial_restraint": "intent-commerce-restraint",
    "faq_expand": "faq-coverage",
    "primary_info": "specificity-primary-info",
}


class Command(BaseCommand):
    help = "判定確定リライトから学び起票・戦術成績集計・プレイブック検証を行う（LLM不使用）"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        now = timezone.now()
        w = self.stdout.write

        settled = list(RewriteDraft.objects
                       .filter(status="applied", eval_status__in=SETTLED)
                       .select_related("article")
                       .order_by("applied_at"))
        w(self.style.SUCCESS(f"=== learn_rewrites 判定確定 {len(settled)}件 ==="))

        # 1) 戦術の補完抽出（applied_tactics 空のドラフトのみ・上書きしない）
        filled = 0
        for d in settled:
            if not d.applied_tactics:
                tactics = extract_tactics((d.diff_summary or "") + "\n" + (d.instructions or ""))
                if tactics:
                    d.applied_tactics = tactics
                    if not dry:
                        d.save(update_fields=["applied_tactics"])
                    filled += 1
                    w(f"  補完抽出 #{d.id} {d.article.slug}: {tactics}")

        # 2) 学びの起票（未起票のみ。既存 lesson は再判定でも上書きしない＝人の追記を守る）
        posted = 0
        for d in settled:
            if d.lesson_recorded_at is None:
                d.lesson = build_lesson_skeleton(d)
                d.lesson_recorded_at = now
                if not dry:
                    d.save(update_fields=["lesson", "lesson_recorded_at"])
                posted += 1
                w(f"  学び起票 #{d.id} /{d.article.slug}/ → {d.eval_status}")

        # 3) 戦術成績のゼロ再計算（判定が後日変わっても集計が追随する）
        stats = {}   # slug -> {field: n, keep: n, samples: []}
        for d in settled:
            field = OUTCOME_FIELD.get(d.eval_status)
            if not field:
                continue
            delta = None
            if d.grow_before is not None and d.grow_after is not None:
                delta = round(d.grow_before - d.grow_after, 1)
            for slug in (d.applied_tactics or []):
                if slug not in TACTICS:
                    continue
                s = stats.setdefault(slug, {"n_reached_p1": 0, "n_improved": 0,
                                            "n_flat": 0, "n_declined": 0,
                                            "n_keep_damaged": 0, "samples": []})
                s[field] += 1
                if d.keep_damaged:
                    s["n_keep_damaged"] += 1
                s["samples"].append({"draft_id": d.id, "slug": d.article.slug,
                                     "outcome": d.eval_status, "delta": delta})

        for slug, s in stats.items():
            label, _kw = TACTICS[slug]
            if dry:
                continue
            t, _ = RewriteTactic.objects.get_or_create(
                slug=slug, defaults={"label": label})
            t.label = label
            t.n_reached_p1 = s["n_reached_p1"]
            t.n_improved = s["n_improved"]
            t.n_flat = s["n_flat"]
            t.n_declined = s["n_declined"]
            t.n_keep_damaged = s["n_keep_damaged"]
            t.samples = s["samples"][-20:]
            t.save()
        # 判定が消えた戦術はゼロに戻す（再計算の冪等性）
        if not dry:
            for t in RewriteTactic.objects.exclude(slug__in=stats.keys()):
                t.n_reached_p1 = t.n_improved = t.n_flat = t.n_declined = 0
                t.n_keep_damaged = 0
                t.samples = []
                t.save()

        # 4) プレイブックへの実測書き戻し
        for slug, rule_key in TACTIC_TO_RULE.items():
            s = stats.get(slug)
            if not s:
                continue
            rule = PlaybookRule.objects.filter(key=rule_key).first()
            if not rule:
                continue
            total = s["n_reached_p1"] + s["n_improved"] + s["n_flat"] + s["n_declined"]
            wins = s["n_reached_p1"] + s["n_improved"]
            ev = dict(rule.evidence or {})
            ev["rewrite_measured"] = {
                "total": total, "wins": wins,
                "win_rate": round(100.0 * wins / total, 1) if total else None,
                "as_of": str(now.date()),
            }
            rule.evidence = ev
            rule.verified = total >= 3
            rule.verification_note = (
                f"リライト実測: 適用{total}件中 改善以上{wins}件"
                f"（learn_rewrites {now.date()}）")
            if not dry:
                rule.save(update_fields=["evidence", "verified", "verification_note"])
            w(f"  playbook更新 {rule_key}: {wins}/{total}")

        w(self.style.SUCCESS(
            f"✅ 補完抽出{filled}件 / 学び起票{posted}件 / 戦術集計{len(stats)}種"))
        if posted:
            w("→ 起票された lesson の【分析】行に要因分析を追記してください"
              "（admin: リライト効果測定、または Claude Code に依頼）。")
