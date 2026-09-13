"""
リライト指示書と現本文を出力  python manage.py show_rewrite_instruction --draft <id>

Claude Code が RewriteDraft の指示書・現タイトル・現本文を読むための出力コマンド。
（アプリはLLMを呼ばない。執筆は Claude Code が担う）

    python manage.py show_rewrite_instruction --draft 7
    python manage.py show_rewrite_instruction --draft 7 --content   # 現本文も全文出力
"""
from django.core.management.base import BaseCommand, CommandError
from apps.analytics.models import RewriteDraft


class Command(BaseCommand):
    help = "RewriteDraft の指示書・チェックリスト・現本文を出力する"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, required=True, help="RewriteDraft id")
        parser.add_argument("--content", action="store_true", help="現本文(content)も全文出力")

    def handle(self, *args, **opts):
        try:
            d = RewriteDraft.objects.select_related("article").get(id=opts["draft"])
        except RewriteDraft.DoesNotExist:
            raise CommandError(f"RewriteDraft(id={opts['draft']}) が見つかりません")
        a = d.article
        self.stdout.write("=" * 70)
        self.stdout.write(f"RewriteDraft #{d.id}  status={d.status}  article=/{a.slug}/")
        self.stdout.write("=" * 70)
        self.stdout.write("\n【指示書】\n" + (d.instructions or "(なし)"))
        self.stdout.write("\n【チェックリスト】")
        for c in (d.checklist or []):
            mark = {True: "OK", False: "NG", None: "--"}.get(c.get("ok"), "--")
            self.stdout.write(f"  [{mark}] {c.get('label')}  :: {c.get('note')}")
        self.stdout.write(f"\n【現タイトル】\n{a.title}")
        if opts["content"]:
            self.stdout.write(f"\n【現本文(content)】\n{a.content or ''}")
        else:
            self.stdout.write(f"\n【現本文】{len(a.content or '')}字（全文は --content で出力）")
        self.stdout.write(
            "\n投入: python manage.py set_rewrite_draft --draft "
            f"{d.id} --title-file <t.txt> --content-file <c.html> [--diff-file <d.txt>]")
