"""検品担当（リン様）の「要差戻し」を担当AIの作業キューに載せる（2026-09-09新設）。

これまで verdict=failed は qa記録・worklog・WorkReportに残るだけで、担当AIを起動する
仕組みが無かったため、差し戻された記事が誰の手にも渡らず止まっていた（RewriteDraft #206）。
このコマンドは差し戻しを1コマンドで「担当が読める形」にする:

  1. EditorNote(source="qa") を作成 … 担当AIが `editor_notes --assignee <担当>` で読める
  2. agents/triggers/<担当>-qa-<kind><ID>.json を作成 … dispatch_revision.sh が5分以内に起動
  3. ArticleWorkLog に sent_back を記録 … レビューページの履歴に残る

使い方:
  manage.py qa_sendback --kind rewrite --target 206 \
     --reason "重量の公式値と矛盾" "価格ハードコード4か所" --category fact
  # 担当を明示する場合（既定は followup＝なお姉が全種別の修正を兼任）
  manage.py qa_sendback --kind article --target 512 --reason "..." --assignee followup
  # 編集長の判断が要る場合（作業範囲の拡大など）は --needs-desk を付ける
"""
import json
import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models import ArticleWorkLog, EditorNote

TRIG_DIR = Path("/opt/claude-ops/agents/triggers")


class Command(BaseCommand):
    help = "検品の要差戻しを担当AIのキューに載せる（EditorNote + 起動トリガー + worklog）"

    def add_arguments(self, parser):
        parser.add_argument("--kind", required=True,
                            choices=[k for k, _ in EditorNote.KIND_CHOICES])
        parser.add_argument("--target", type=int, required=True, help="対象ID")
        parser.add_argument("--reason", nargs="+", required=True,
                            help="差し戻し理由（1件1指摘。複数指定するとnoteも複数作る）")
        parser.add_argument("--category", default="other",
                            choices=[c for c, _ in EditorNote.CATEGORY_CHOICES],
                            help="指摘の種類（学習還流の集計軸）")
        parser.add_argument("--assignee", default="followup",
                            choices=[a for a, _ in EditorNote.ASSIGNEE_CHOICES])
        parser.add_argument("--needs-desk", action="store_true",
                            help="作業範囲の判断など、編集長の決定が要る差し戻し")
        parser.add_argument("--no-trigger", action="store_true",
                            help="EditorNoteだけ作り、担当AIの即時起動はしない")

    def handle(self, *a, **o):
        kind, target = o["kind"], o["target"]
        slug, title = self._resolve_target(kind, target)

        # 同じ対象に未対応の検品差し戻しが残っているなら重ねない（毎朝の再検品で増殖させない）
        dup = EditorNote.objects.filter(kind=kind, target_id=target,
                                        source="qa", status="open").count()
        if dup:
            self.stdout.write(self.style.WARNING(
                f"未対応の検品差し戻しが既に{dup}件あります（/{slug}/）。"
                "重複を避けるため新しいnoteは作りません。"))
            return

        created = []
        for reason in o["reason"]:
            n = EditorNote.objects.create(
                kind=kind, target_id=target, slug=slug, target_title=title,
                quote="", comment=reason, category=o["category"],
                assignee=o["assignee"], source="qa",
                status="open", sent_back_at=timezone.now(),
            )
            created.append(n)
        ids = ", ".join(f"#{n.id}" for n in created)
        self.stdout.write(self.style.SUCCESS(
            f"検品差し戻しを登録: {ids}（/{slug}/ → {o['assignee']}）"))

        ArticleWorkLog.objects.create(
            kind=kind, target_id=target, slug=slug, agent="qa", action="sent_back",
            summary=f"検品差し戻しを{o['assignee']}のキューへ（note {ids}）",
            detail="\n".join(f"- {r}" for r in o["reason"]),
        )

        if o["needs_desk"]:
            self.stdout.write(self.style.WARNING(
                "作業範囲の判断が要る差し戻しです。編集長（queue.md）にも申し送ってください。"))

        if o["no_trigger"]:
            self.stdout.write("トリガーは作成していません（--no-trigger）")
            return
        self._write_trigger(o["assignee"], kind, target, slug, o["reason"])

    # ------------------------------------------------------------------
    def _resolve_target(self, kind, target):
        if kind == "rewrite":
            from apps.analytics.models import RewriteDraft
            d = RewriteDraft.objects.filter(id=target).select_related("article").first()
            if not d:
                raise CommandError(f"RewriteDraft #{target} が見つかりません")
            return d.article.slug, (d.draft_title or d.article.title)
        if kind == "article":
            from apps.products.models import Article
            a = Article.objects.filter(id=target).first()
            if not a:
                raise CommandError(f"Article #{target} が見つかりません")
            return a.slug, a.title
        from apps.products.models import Product
        p = Product.objects.filter(pk=target).first()
        if not p:
            raise CommandError(f"Product #{target} が見つかりません")
        return p.slug, p.name

    def _write_trigger(self, assignee, kind, target, slug, reasons):
        TRIG_DIR.mkdir(parents=True, exist_ok=True)
        path = TRIG_DIR / f"{assignee}-qa-{kind}{target}.json"
        path.write_text(json.dumps({
            "source": "qa",
            "assignee": assignee,
            "kind": kind,
            "target_id": target,
            "slug": slug,
            "reasons": reasons,
            "created_at": timezone.now().isoformat(),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # 管理画面(deploy)も同じディレクトリに書くので所有者をそろえる
        try:
            shutil.chown(path, user="deploy", group="www-data")
            os.chmod(path, 0o664)
        except (LookupError, PermissionError, OSError) as e:
            self.stdout.write(self.style.WARNING(f"所有者を変更できませんでした: {e}"))
        self.stdout.write(f"起動トリガーを作成: {path}（5分以内に担当AIが動きます）")
