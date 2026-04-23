"""WordPressのエクスポートXML (WXR) から記事をインポートする

使い方:
    python manage.py import_wordpress path/to/export.xml
    python manage.py import_wordpress path/to/export.xml --as-products  # 記事を商品として取り込む場合

WordPress XMLは "ツール > エクスポート" で出力されるWXR形式に対応します。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.utils.timezone import make_aware

from apps.products.models import Article, Category, Product

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
}


class Command(BaseCommand):
    help = "WordPress XML (WXR) をインポートします"

    def add_arguments(self, parser):
        parser.add_argument("xml_path", help="WordPressエクスポートXMLへのパス")
        parser.add_argument(
            "--as-products",
            action="store_true",
            help="記事を商品データとしても取り込む",
        )
        parser.add_argument(
            "--post-type",
            default="post",
            help="取り込む投稿タイプ (デフォルト: post)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際にDBへ書き込まず、取り込む件数を表示するのみ",
        )

    def handle(self, *args, **options):
        path = options["xml_path"]
        post_type = options["post_type"]
        dry = options["dry_run"]
        as_products = options["as_products"]

        try:
            tree = ET.parse(path)
        except (ET.ParseError, FileNotFoundError) as e:
            raise CommandError(f"XMLを読み込めませんでした: {e}")

        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            raise CommandError("channel要素が見つかりません。正しいWXRファイルですか？")

        items = channel.findall("item")
        total = 0
        imported_articles = 0
        imported_products = 0
        skipped = 0

        categories_by_nicename: dict[str, Category] = {}

        for item in items:
            ptype = _text(item, "wp:post_type")
            status = _text(item, "wp:status")
            if ptype != post_type:
                continue
            if status not in ("publish", "draft", "private"):
                continue
            total += 1

            title = _text(item, "title") or "(無題)"
            post_id_str = _text(item, "wp:post_id")
            post_id = int(post_id_str) if post_id_str and post_id_str.isdigit() else None
            content = _text(item, "content:encoded") or ""
            excerpt = _text(item, "excerpt:encoded") or ""
            author = _text(item, "dc:creator") or ""
            post_name = _text(item, "wp:post_name") or slugify(title, allow_unicode=True)
            post_name = post_name[:200] or f"post-{post_id}"

            pub_raw = _text(item, "wp:post_date_gmt") or _text(item, "pubDate")
            published_at = _parse_date(pub_raw)

            cats = []
            for c in item.findall("category"):
                domain = c.get("domain")
                nicename = c.get("nicename")
                name = (c.text or "").strip()
                if domain == "category" and name:
                    cat = categories_by_nicename.get(nicename)
                    if cat is None and not dry:
                        cat, _ = Category.objects.get_or_create(
                            slug=slugify(nicename or name, allow_unicode=True)[:120] or f"cat-{len(categories_by_nicename)}",
                            defaults={"name": name},
                        )
                        categories_by_nicename[nicename or name] = cat
                    cats.append((nicename, name))

            is_published = status == "publish"

            if dry:
                self.stdout.write(f"[DRY] {title} (id={post_id}, status={status})")
                imported_articles += 1
                continue

            article, created = Article.objects.update_or_create(
                wp_post_id=post_id,
                defaults={
                    "title": title,
                    "slug": _unique_slug(Article, post_name),
                    "content": content,
                    "excerpt": excerpt,
                    "wp_author": author,
                    "published_at": published_at,
                    "is_published": is_published,
                },
            )
            imported_articles += 1

            if as_products and is_published:
                prod, p_created = Product.objects.update_or_create(
                    slug=_unique_slug(Product, post_name, exclude_pk=None),
                    defaults={
                        "name": title,
                        "description": _strip_html_summary(content, 500),
                        "is_published": True,
                    },
                )
                if cats:
                    cat_objs = [
                        categories_by_nicename[c[0]]
                        for c in cats
                        if c[0] in categories_by_nicename
                    ]
                    if cat_objs:
                        prod.categories.add(*cat_objs)
                imported_products += 1

            if post_id is None:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"取り込み完了: 対象 {total} 件 / 記事 {imported_articles} 件"
            + (f" / 商品 {imported_products} 件" if as_products else "")
            + (f" / post_id無しでスキップ相当 {skipped}" if skipped else "")
        ))


def _text(item, path):
    el = item.find(path, NS)
    return (el.text or "").strip() if el is not None and el.text else ""


def _parse_date(raw: str):
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        try:
            dt = datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if dt and dt.tzinfo is None:
        dt = make_aware(dt)
    return dt


def _unique_slug(model, base, exclude_pk=None):
    base = (base or "item")[:200]
    slug = base
    i = 2
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        slug = f"{base}-{i}"[:220]
        i += 1
        qs = model.objects.filter(slug=slug)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
    return slug


def _strip_html_summary(html: str, length: int) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:length]
