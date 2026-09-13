"""作業報告を管理画面(WorkReport)に登録するコマンド。

ターミナル出力ではなく Django 管理画面で作業内容を確認できるようにする。

例:
    python manage.py post_report \
        --title "マイページ再設計" \
        --status success \
        --summary "/accounts/profile/ をタブ式に再構成" \
        --body-file /path/to/report.md \
        --files-file /path/to/files.txt

本文・変更ファイルは長くなりがちなので、シェルのエスケープを避けるため
--body-file / --files-file でファイル渡しも受け付ける（--body / --files の直接指定も可）。
"""
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.models import WorkReport


class Command(BaseCommand):
    help = "作業報告を管理画面(WorkReport)に登録する"

    def add_arguments(self, parser):
        parser.add_argument("--title", required=True, help="作業タイトル")
        parser.add_argument(
            "--status", default="success",
            choices=[c[0] for c in WorkReport.STATUS_CHOICES],
            help="状態 (success/info/warning/error)")
        parser.add_argument("--summary", default="", help="一覧用の1行サマリー")
        parser.add_argument("--body", default="", help="本文(Markdown)")
        parser.add_argument("--body-file", default="", help="本文をファイルから読み込む")
        parser.add_argument("--files", default="", help="変更ファイル(改行 or カンマ区切り)")
        parser.add_argument("--files-file", default="", help="変更ファイル一覧をファイルから読み込む")

    def handle(self, *args, **opts):
        body = opts["body"]
        if opts["body_file"]:
            try:
                with open(opts["body_file"], encoding="utf-8") as f:
                    body = f.read()
            except OSError as e:
                raise CommandError(f"--body-file を読めません: {e}")

        files = opts["files"]
        if opts["files_file"]:
            try:
                with open(opts["files_file"], encoding="utf-8") as f:
                    files = f.read()
            except OSError as e:
                raise CommandError(f"--files-file を読めません: {e}")
        # カンマ区切りで渡された場合は改行に正規化（1行1ファイル表示のため）。
        files = "\n".join(
            part.strip() for chunk in files.splitlines() or [files]
            for part in chunk.split(",") if part.strip())

        report = WorkReport.objects.create(
            title=opts["title"],
            status=opts["status"],
            summary=opts["summary"],
            body=body,
            files_changed=files,
        )
        self.stdout.write(self.style.SUCCESS(
            f"作業報告を登録しました (id={report.pk}): {report.title}"))
