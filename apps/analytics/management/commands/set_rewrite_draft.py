"""
Claude Code が書いた案を RewriteDraft に投入  python manage.py set_rewrite_draft

アプリ外(Claude Code)が指示書に沿って執筆した draft_title/draft_content を流し込み、
status=in_review にする。★ここでもLLMは呼ばない（ただの受け取り口）。

    python manage.py set_rewrite_draft --draft 7 \
        --title-file /tmp/t.txt --content-file /tmp/c.html --diff-file /tmp/d.txt
    python manage.py set_rewrite_draft --draft 7 --title "…" --content-file /tmp/c.html
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.analytics.models import RewriteDraft


class Command(BaseCommand):
    help = "RewriteDraft に案(draft_title/draft_content)を投入し status=in_review にする"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, required=True)
        parser.add_argument("--title", type=str, default=None)
        parser.add_argument("--title-file", type=str, default=None)
        parser.add_argument("--content", type=str, default=None)
        parser.add_argument("--content-file", type=str, default=None)
        parser.add_argument("--diff", type=str, default=None)
        parser.add_argument("--diff-file", type=str, default=None)

    def _val(self, inline, path):
        if path:
            with open(path, encoding="utf-8") as f:
                return f.read()
        return inline

    def handle(self, *args, **opts):
        try:
            d = RewriteDraft.objects.get(id=opts["draft"])
        except RewriteDraft.DoesNotExist:
            raise CommandError(f"RewriteDraft(id={opts['draft']}) が見つかりません")

        title = self._val(opts["title"], opts["title_file"])
        content = self._val(opts["content"], opts["content_file"])
        diff = self._val(opts["diff"], opts["diff_file"])

        if title is not None:
            d.draft_title = title.strip()
        if content is not None:
            d.draft_content = content
        if diff is not None:
            d.diff_summary = diff.strip()
        if not d.draft_content:
            raise CommandError("draft_content が空です（--content/--content-file を指定してください）")

        d.status = "in_review"
        d.reviewed_at = timezone.now()
        d.save(update_fields=["draft_title", "draft_content", "diff_summary",
                              "status", "reviewed_at"])
        self.stdout.write(self.style.SUCCESS(
            f"✅ Draft #{d.id} に投入（title={len(d.draft_title)}字 / content={len(d.draft_content)}字）"
            f" status=in_review"))
        self.stdout.write(f"レビュー: https://sc-tsusho.jp/admin/analytics/rewritedraft/{d.id}/change/")
