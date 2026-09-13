"""人からの修正指示（EditorNote）を担当AI社員が読み書きするCLI。

承認センターのレビューページで人が書いた指示を受け取り、修正後に対応内容と
「次に活かす学び」を記録する。学びは learning.build_editor_note_digest() が
指示書へ還流するので、記録＝次回以降の執筆品質に効く。

使い方:
  # 自分宛の未対応の指示を読む（起動時に必ず最初に実行する）
  manage.py editor_notes --assignee writer
  # 「🛑 検品差し戻し」と付いたものは検品担当(リン様)がfailedにした指摘。
  # 人の指示と同じように直し、同じように --resolve で閉じる
  # 対応を記録する（1件ずつ・修正を終えてから）
  manage.py editor_notes --resolve 12 --note "導入を書き直し具体条件を追加" \
      --lesson "冒頭は一般論でなく『誰が・どの条件で』から書く"
  # 対応不要と判断した場合（理由を --note に必ず書く）
  manage.py editor_notes --resolve 12 --dismiss --note "既に本文で言及済みのため"
  # 修正が全部終わったリライト案を検品待ちに戻す
  manage.py editor_notes --requeue rewrite:34
  # これまでの指摘傾向（学習ダイジェスト）
  manage.py editor_notes --digest
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models import EditorNote, RewriteDraft


class Command(BaseCommand):
    help = "人からの修正指示の確認・対応記録（AI社員用）"

    def add_arguments(self, parser):
        parser.add_argument("--assignee", default="",
                            help="担当キー(writer/product_writer/followup/qa)で絞る")
        parser.add_argument("--kind", default="", help="rewrite/article/product_v2")
        parser.add_argument("--target", type=int, default=None, help="対象ID")
        parser.add_argument("--all", action="store_true",
                            help="対応済みも含めて表示する")
        parser.add_argument("--resolve", type=int, default=None, help="対応記録するnote ID")
        parser.add_argument("--note", default="", help="--resolve の対応内容（必須）")
        parser.add_argument("--lesson", default="",
                            help="--resolve の次に活かす学び（一般化して1〜2文）")
        parser.add_argument("--dismiss", action="store_true",
                            help="--resolve を「対応不要」で閉じる")
        parser.add_argument("--requeue", default="",
                            help="修正完了した対象を検品待ちに戻す（例: rewrite:34）")
        parser.add_argument("--digest", action="store_true",
                            help="指摘傾向の学習ダイジェストを表示")

    def handle(self, *a, **o):
        if o["digest"]:
            from apps.analytics.learning import build_editor_note_digest
            self.stdout.write(build_editor_note_digest() or "（修正指示の記録はまだありません）")
            return
        if o["requeue"]:
            self._requeue(o["requeue"])
            return
        if o["resolve"]:
            self._resolve(o)
            return
        self._list(o)

    # ------------------------------------------------------------------
    def _list(self, o):
        qs = EditorNote.objects.all()
        if not o["all"]:
            qs = qs.filter(status="open")
        if o["assignee"]:
            qs = qs.filter(assignee=o["assignee"])
        if o["kind"]:
            qs = qs.filter(kind=o["kind"])
        if o["target"] is not None:
            qs = qs.filter(target_id=o["target"])
        notes = list(qs.order_by("kind", "target_id", "id"))
        if not notes:
            self.stdout.write("対象なし（未対応の修正指示はありません）")
            return
        self.stdout.write(f"未対応の修正指示 {len(notes)}件\n")
        current = None
        for n in notes:
            key = (n.kind, n.target_id)
            if key != current:
                current = key
                self.stdout.write(
                    f"\n■ [{n.get_kind_display()}] /{n.slug}/ {n.target_title}\n"
                    f"  レビュー画面: {n.review_url}"
                    + (f"\n  リライト案ID: {n.target_id}" if n.kind == "rewrite" else "")
                    + (f"\n  記事ID: {n.target_id}" if n.kind == "article" else "")
                    + (f"\n  商品PK: {n.target_id}" if n.kind == "product_v2" else ""))
            src = "🛑 検品差し戻し " if n.source == "qa" else ""
            self.stdout.write(
                f"  - note#{n.id} {src}[{n.get_category_display()}] "
                f"({n.get_status_display()}・{n.created_at:%m/%d %H:%M})")
            if n.quote:
                self.stdout.write(f"    該当箇所: {n.quote[:400]}")
            for line in (n.comment or "").splitlines():
                self.stdout.write(f"    指示: {line}")
            if n.resolution:
                self.stdout.write(f"    対応済: {n.resolution}")
        self.stdout.write(
            "\n対応後: manage.py editor_notes --resolve <id> --note \"対応内容\" "
            "--lesson \"次に活かす学び\"\n"
            "リライト案は全件対応後に manage.py editor_notes --requeue rewrite:<id> "
            "で検品待ちに戻す（新規記事・商品記事v2は修正保存だけでよい）")

    # ------------------------------------------------------------------
    def _resolve(self, o):
        n = EditorNote.objects.filter(id=o["resolve"]).first()
        if not n:
            raise CommandError(f"note#{o['resolve']} が見つかりません")
        if not o["note"].strip():
            raise CommandError("--note に対応内容（または対応不要の理由）を書いてください")
        n.status = "dismissed" if o["dismiss"] else "fixed"
        n.resolution = o["note"].strip()
        if o["lesson"].strip():
            n.lesson = o["lesson"].strip()
        n.resolved_at = timezone.now()
        n.save(update_fields=["status", "resolution", "lesson", "resolved_at"])
        left = EditorNote.objects.filter(
            kind=n.kind, target_id=n.target_id, status="open").count()
        self.stdout.write(self.style.SUCCESS(
            f"✅ note#{n.id} を「{n.get_status_display()}」で記録しました"))
        if not n.lesson and not o["dismiss"]:
            self.stdout.write(self.style.WARNING(
                "※ --lesson が未記入です。学びを残さないと同じ指摘を繰り返します"))
        if left:
            self.stdout.write(f"この記事の未対応はあと {left}件")
        else:
            self.stdout.write("この記事の修正指示はすべて対応済みです。"
                              + ("`--requeue rewrite:%s` で検品待ちに戻してください"
                                 % n.target_id if n.kind == "rewrite"
                                 else "検品担当の再検品を待ってください"))

    # ------------------------------------------------------------------
    def _requeue(self, spec):
        try:
            kind, raw = spec.split(":", 1)
            obj_id = int(raw)
        except ValueError:
            raise CommandError("--requeue は kind:id の形で指定します（例: rewrite:34）")
        left = EditorNote.objects.filter(
            kind=kind, target_id=obj_id, status="open").count()
        if left:
            raise CommandError(
                f"未対応の修正指示が {left}件 残っています。先に --resolve してください")
        if kind != "rewrite":
            self.stdout.write(
                "新規記事・商品記事v2は本文を保存すれば検品対象に戻ります（操作不要）")
            return
        d = RewriteDraft.objects.filter(id=obj_id).first()
        if not d:
            raise CommandError(f"リライト案 #{obj_id} が見つかりません")
        d.status = "in_review"
        d.qa_result = {}
        d.save(update_fields=["status", "qa_result"])
        self.stdout.write(self.style.SUCCESS(
            f"✅ リライト案 #{d.id}（/{d.article.slug}/）を検品待ちに戻しました"))
