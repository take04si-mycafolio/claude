"""Django管理コマンド: WXR(JSON化済)から products.Article へ一括投入。

設置場所(本番VM):
    /home/deploy/app/apps/products/management/commands/import_wxr.py
    ※ products/management/ と products/management/commands/ に
      空の __init__.py が無ければ作成すること。

呼び出し例(本番VM):
    cd /home/deploy/app

    # 1) dry-run で件数とタイトル確認
    sudo -u deploy .venv/bin/python manage.py import_wxr /tmp/biganki/wxr.json --dry-run

    # 2) 先頭3件だけ実投入(常に is_published=False)
    sudo -u deploy .venv/bin/python manage.py import_wxr /tmp/biganki/wxr.json --limit 3

    # 3) 全件投入(下書き)
    sudo -u deploy .venv/bin/python manage.py import_wxr /tmp/biganki/wxr.json

    # 既存wp_post_idにヒットしたら上書きしたい場合
    sudo -u deploy .venv/bin/python manage.py import_wxr /tmp/biganki/wxr.json --update

仕様:
    - 投入先モデルは products.Article 固定。
    - WPカテゴリ/タグは取り込まない(product_typeはnull、tagモデル無し)。
    - thumbnail_url にはWXRの featured_image_url をそのまま保存。
    - is_published は常に False(管理画面で個別に公開判定する前提)。
    - wp_post_id を冪等キーとし、既存ヒット時はデフォルトでスキップ。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.products.models import Article

POST_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_dt(s: str):
    if not s or s.startswith("0000"):
        return None
    try:
        dt = datetime.strptime(s, POST_DATE_FMT)
    except ValueError:
        return None
    return timezone.make_aware(dt, timezone.get_current_timezone())


class Command(BaseCommand):
    help = "WordPress WXR(JSON化)を products.Article に一括投入(常に下書き)"

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=Path, help="parse_wxr.py 出力のJSON")
        parser.add_argument("--dry-run", action="store_true", help="DB書き込みなし")
        parser.add_argument("--update", action="store_true",
                            help="既存(wp_post_id一致)を上書き。指定なしでskip")
        parser.add_argument("--limit", type=int, default=0,
                            help="先頭N件のみ処理(0=全件)")
        parser.add_argument("--use-cleaned", action="store_true",
                            help="ショートコード除去済み本文(content_cleaned)を採用")

    def handle(self, *args, **opts):
        json_path: Path = opts["json_path"]
        if not json_path.exists():
            raise CommandError(f"JSON not found: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        posts = [p for p in data["posts"] if p["status"] == "publish"]
        if opts["limit"]:
            posts = posts[: opts["limit"]]
        self.stdout.write(self.style.NOTICE(f"target: {len(posts)} published posts"))

        created = updated = skipped = 0
        for p in posts:
            slug = p["slug"] or slugify(p["title"], allow_unicode=True)
            wp_id = p["wp_id"]
            existing = Article.objects.filter(wp_post_id=wp_id).first() if wp_id else None
            if existing is None:
                existing = Article.objects.filter(slug=slug).first()

            if existing and not opts["update"]:
                self.stdout.write(f"  skip(exists): {slug}")
                skipped += 1
                continue

            body = p["content_cleaned"] if opts["use_cleaned"] else p["content_html"]
            values = {
                "title": p["title"][:500],
                "slug": slug[:500],
                "content": body,
                "excerpt": p["excerpt"] or "",
                "thumbnail_url": (p["featured_image_url"] or "")[:500],
                "product_type": None,
                "meta_title": p["title"][:100],
                "meta_description": (p["excerpt"] or "")[:200],
                "wp_post_id": wp_id,
                "wp_author": (p["author_login"] or "")[:500],
                "published_at": _parse_dt(p["post_date"]),
                "is_published": False,
            }

            action = "UPD" if existing else "NEW"
            if opts["dry_run"]:
                img = "Y" if values["thumbnail_url"] else "-"
                self.stdout.write(
                    f"  [DRY] {action}  wp_id={wp_id:>5}  img={img}  {slug}  / {values['title'][:40]}"
                )
                if existing:
                    updated += 1
                else:
                    created += 1
                continue

            with transaction.atomic():
                if existing:
                    for k, v in values.items():
                        setattr(existing, k, v)
                    existing.save()
                    updated += 1
                else:
                    Article.objects.create(**values)
                    created += 1
            self.stdout.write(f"  {action}  {slug}")

        self.stdout.write(self.style.SUCCESS(
            f"done: created={created}, updated={updated}, skipped={skipped}"
        ))
