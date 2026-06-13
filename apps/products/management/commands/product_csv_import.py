"""CSV から商品を一括インポート (色違い自動マージ込)。"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Product, Category
from apps.products.services.sync_common import (
    find_existing_product, _generate_slug,
)


class Command(BaseCommand):
    help = "CSV ファイルから商品を一括インポート (重複は自動でマージ、色違いはスキップ)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="CSV ファイルのパス")
        parser.add_argument("--dry-run", action="store_true",
                            help="DB 変更せず判定のみ")

    def handle(self, *args, **opts):
        path = opts["csv_path"]
        try:
            f = open(path, encoding="utf-8-sig")
        except FileNotFoundError:
            raise CommandError(f"ファイルが見つかりません: {path}")

        reader = csv.DictReader(f)
        required = {"name", "brand", "category"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise CommandError(f"必須列が不足: {missing}")

        counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0, "color_variant": 0}
        seen_name_brand = set()

        for i, row in enumerate(reader, start=2):
            # 連結CSV の 2 回目以降のヘッダ行を無視
            if (row.get("name") or "").strip().lower() == "name":
                continue

            name = (row.get("name") or "").strip()
            brand = (row.get("brand") or "").strip()
            model = (row.get("model") or "").strip()
            category_slug = (row.get("category") or "").strip()
            price_raw = (row.get("price") or "").strip()
            description = (row.get("description") or "").strip()
            image_url = (row.get("image_url") or "").strip()
            official_url = (row.get("official_url") or "").strip()

            if not name or not brand or not category_slug:
                self.stdout.write(self.style.ERROR(
                    f"  行{i}: 必須項目空欄 (name/brand/category) - スキップ"
                ))
                counts["error"] += 1
                continue

            # CSV内 (name + brand) 重複は色違いとみなしスキップ
            nb_key = (name, brand)
            if nb_key in seen_name_brand:
                self.stdout.write(self.style.WARNING(
                    f"  [color] 行{i}: {name} ({brand}, model={model}) 色違いスキップ"
                ))
                counts["color_variant"] += 1
                continue
            seen_name_brand.add(nb_key)

            ptype = Category.objects.filter(slug=category_slug, parent__isnull=True).first()
            if not ptype:
                self.stdout.write(self.style.ERROR(
                    f"  行{i}: カテゴリ '{category_slug}' が見つかりません - スキップ"
                ))
                counts["error"] += 1
                continue

            # 重複判定: 名前+型番から検索
            full_name = f"{name} {model}".strip() if model else name
            parsed = {"title": full_name}
            existing, match_type = find_existing_product(parsed, ptype)

            try:
                price = int(price_raw) if price_raw else None
            except ValueError:
                price = None

            if existing:
                if opts["dry_run"]:
                    self.stdout.write(f"  [既存] 行{i}: {full_name} → 「{existing.name}」(match: {match_type})")
                else:
                    if not existing.brand and brand:
                        existing.brand = brand
                    if not existing.price and price:
                        existing.price = price
                    if not existing.description and description:
                        existing.description = description
                    if not existing.image_url and image_url:
                        existing.image_url = image_url
                    if not existing.official_url and official_url:
                        existing.official_url = official_url
                    existing.save()
                    self.stdout.write(f"  [既存] 行{i}: {full_name} → 「{existing.name}」 更新")
                counts["updated"] += 1
            else:
                if opts["dry_run"]:
                    self.stdout.write(f"  [新規] 行{i}: {full_name}")
                else:
                    slug = _generate_slug(full_name, fallback="csv-item")
                    Product.objects.create(
                        name=full_name[:200],
                        slug=slug,
                        product_type=ptype,
                        brand=brand[:100],
                        price=price,
                        description=description[:500],
                        image_url=image_url,
                        official_url=official_url,
                        is_published=True,
                        source="manual",
                    )
                    self.stdout.write(f"  [新規] 行{i}: {full_name}")
                counts["created"] += 1

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== サマリー ==="))
        for k, v in counts.items():
            self.stdout.write(f"  {k}: {v}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n※ --dry-run のため DB 変更なし"))
        f.close()
