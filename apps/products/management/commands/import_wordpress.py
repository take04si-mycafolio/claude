"""WordPressエクスポートXML (WXR) からインポート

自動判定:
- `biganki1` カスタム投稿タイプ → Product (美顔器)
- `post` (通常投稿) → Article (記事)
- `category` タクソノミー → Category

使い方:
    python manage.py import_wordpress path/to/export.xml
    python manage.py import_wordpress path/to/export.xml --dry-run
"""

from __future__ import annotations

import re
import urllib.parse
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
    help = "WordPressエクスポートXML (WXR) をインポートします"

    def add_arguments(self, parser):
        parser.add_argument("xml_path", help="WordPressエクスポートXMLへのパス")
        parser.add_argument(
            "--dry-run", action="store_true", help="DBへ書き込まず件数のみ表示"
        )
        parser.add_argument(
            "--skip-articles", action="store_true", help="記事(post)のインポートをスキップ"
        )
        parser.add_argument(
            "--skip-products", action="store_true", help="商品(biganki1)のインポートをスキップ"
        )

    def handle(self, *args, **opts):
        path = opts["xml_path"]
        dry = opts["dry_run"]

        try:
            tree = ET.parse(path)
        except (ET.ParseError, FileNotFoundError) as e:
            raise CommandError(f"XMLの読み込みに失敗しました: {e}")

        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            raise CommandError("channel要素が見つかりません")

        categories = self._import_categories(channel, dry)
        self.stdout.write(f"カテゴリ: {len(categories)} 件")

        items = channel.findall("item")
        biganki_items = [
            it for it in items if _text(it, "wp:post_type") == "biganki1"
            and _text(it, "wp:status") == "publish"
        ]
        post_items = [
            it for it in items if _text(it, "wp:post_type") == "post"
            and _text(it, "wp:status") == "publish"
        ]

        self.stdout.write(f"美顔器(biganki1): {len(biganki_items)} 件 / 記事(post): {len(post_items)} 件")

        products_created = 0
        if not opts["skip_products"]:
            products_created = self._import_products(biganki_items, categories, dry)

        articles_created = 0
        if not opts["skip_articles"]:
            articles_created = self._import_articles(post_items, dry)

        label = "[DRY-RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{label}完了: 美顔器 {products_created} 件 / 記事 {articles_created} 件 / カテゴリ {len(categories)} 件"
        ))

    def _import_categories(self, channel, dry):
        cats = {}
        for c in channel.findall("wp:category", NS):
            name_el = c.find("wp:cat_name", NS)
            slug_el = c.find("wp:category_nicename", NS)
            if name_el is None or not name_el.text:
                continue
            name = name_el.text.strip()
            raw_slug = (slug_el.text or "").strip() if slug_el is not None else slugify(name, allow_unicode=True)
            slug = urllib.parse.unquote(raw_slug)
            if dry:
                cats[slug] = None
                self.stdout.write(f"  [DRY] cat: {name} ({slug})")
                continue
            obj, _ = Category.objects.get_or_create(
                slug=slug[:120] or slugify(name, allow_unicode=True)[:120],
                defaults={"name": name},
            )
            if obj.name != name:
                obj.name = name
                obj.save(update_fields=["name"])
            cats[slug] = obj
        return cats

    def _import_products(self, items, categories, dry):
        count = 0
        for it in items:
            title = _text(it, "title") or "(無題)"
            post_id = _int(_text(it, "wp:post_id"))
            slug_base = _text(it, "wp:post_name") or slugify(title, allow_unicode=True)
            slug_base = slug_base[:200] or f"biganki-{post_id}"
            published_at = _parse_date(
                _text(it, "wp:post_date_gmt") or _text(it, "pubDate")
            )

            pm = _postmeta(it)
            brand = _strip_html(pm.get("program_name_eiji", ""))[:100]
            product_name = _strip_html(pm.get("program_name", "")) or title
            image_url = pm.get("img", "").strip()
            affiliate_url = pm.get("afitag", "").strip()
            rakuten_url = pm.get("rakutentag", "").strip()
            amazon_url = pm.get("amazontag", "").strip()
            price_raw = pm.get("sort2", "").strip()
            price = _int(price_raw)
            sort_order = _int(pm.get("sort1", "")) or 0

            description = pm.get("syoukai_pr", "") or ""
            features = pm.get("tokutyo", "") or ""

            cat_pairs = _category_items(it)

            if dry:
                self.stdout.write(f"  [DRY] product: {product_name} (brand={brand}, price={price}, cats={len(cat_pairs)})")
                count += 1
                continue

            defaults = {
                "name": product_name[:200],
                "slug": _unique_slug(Product, slug_base, post_id),
                "brand": brand,
                "price": price,
                "image_url": image_url,
                "affiliate_url": affiliate_url,
                "rakuten_url": rakuten_url,
                "amazon_url": amazon_url,
                "description": description,
                "features": features,
                "sort_order": sort_order,
                "is_published": True,
            }
            prod, created = Product.objects.update_or_create(
                wp_post_id=post_id, defaults=defaults
            )
            # カテゴリ紐付け（カスタムタクソノミーも登録）
            cat_objs = []
            for slug, name in cat_pairs:
                if slug in categories and categories[slug] is not None:
                    cat_objs.append(categories[slug])
                else:
                    obj, _ = Category.objects.get_or_create(
                        slug=slug[:120], defaults={"name": name}
                    )
                    categories[slug] = obj
                    cat_objs.append(obj)
            if cat_objs:
                prod.categories.set(cat_objs)
            count += 1
        return count

    def _import_articles(self, items, dry):
        count = 0
        for it in items:
            title = _text(it, "title") or "(無題)"
            post_id = _int(_text(it, "wp:post_id"))
            slug_base = _text(it, "wp:post_name") or slugify(title, allow_unicode=True)
            slug_base = slug_base[:200] or f"post-{post_id}"
            published_at = _parse_date(
                _text(it, "wp:post_date_gmt") or _text(it, "pubDate")
            )
            content = _text(it, "content:encoded")
            excerpt = _text(it, "excerpt:encoded")
            author = _text(it, "dc:creator")

            if dry:
                self.stdout.write(f"  [DRY] article: {title}")
                count += 1
                continue

            Article.objects.update_or_create(
                wp_post_id=post_id,
                defaults={
                    "title": title[:255],
                    "slug": _unique_slug(Article, slug_base, post_id, field="wp_post_id"),
                    "content": content,
                    "excerpt": excerpt,
                    "wp_author": author[:100],
                    "published_at": published_at,
                    "is_published": True,
                },
            )
            count += 1
        return count


# --- helpers ---

def _text(el, path):
    if el is None:
        return ""
    child = el.find(path, NS)
    return (child.text or "").strip() if child is not None and child.text else ""


def _int(s):
    if not s:
        return None
    s = str(s).strip().replace(",", "")
    try:
        return int(s)
    except ValueError:
        m = re.search(r"\d+", s)
        return int(m.group()) if m else None


def _postmeta(item):
    result = {}
    for m in item.findall("wp:postmeta", NS):
        k = m.find("wp:meta_key", NS)
        v = m.find("wp:meta_value", NS)
        if k is None or not k.text:
            continue
        result[k.text] = (v.text or "") if v is not None else ""
    return result


CATEGORY_DOMAINS = {"category", "biganki1_taxonomy4"}  # 標準カテゴリ + 機能分類


def _category_slugs(item):
    slugs = []
    for c in item.findall("category"):
        if c.get("domain") in CATEGORY_DOMAINS:
            nicename = c.get("nicename")
            if nicename:
                slugs.append(nicename)
    return slugs


def _category_items(item):
    """(slug, name) ペアを返す。未登録カテゴリをオンザフライで作るため"""
    pairs = []
    for c in item.findall("category"):
        if c.get("domain") in CATEGORY_DOMAINS:
            nicename = urllib.parse.unquote(c.get("nicename") or "")
            name = (c.text or "").strip()
            if nicename and name and name != "指定なし":
                pairs.append((nicename, name))
    return pairs


def _parse_date(raw: str):
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if dt and dt.tzinfo is None:
        dt = make_aware(dt)
    return dt


def _unique_slug(model, base, wp_post_id=None, field="wp_post_id"):
    base = (base or "item")[:200]
    slug = base
    i = 2
    qs = model.objects.filter(slug=slug)
    if wp_post_id is not None and hasattr(model, field):
        qs = qs.exclude(**{field: wp_post_id})
    while qs.exists():
        slug = f"{base}-{i}"[:220]
        i += 1
        qs = model.objects.filter(slug=slug)
        if wp_post_id is not None and hasattr(model, field):
            qs = qs.exclude(**{field: wp_post_id})
    return slug


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
