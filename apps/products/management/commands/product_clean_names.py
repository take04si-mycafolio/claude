"""既存商品の name を clean_product_name で再生成する。

api_data に保存された元の楽天/Amazon タイトルから整形し直す。

Usage:
  python manage.py product_clean_names --source rakuten --dry-run
  python manage.py product_clean_names --source rakuten
  python manage.py product_clean_names --source all --category bigankiki
"""
from django.core.management.base import BaseCommand

from apps.products.models import Product
from apps.products.services.sync_common import clean_product_name, is_accessory


class Command(BaseCommand):
    help = "既存商品の name を clean_product_name で再生成"

    def add_arguments(self, parser):
        parser.add_argument("--source", default="rakuten",
                            help="対象 source (manual/rakuten/amazon/wp/all)")
        parser.add_argument("--category", help="特定カテゴリ slug のみ")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        qs = Product.objects.all().order_by("id")
        if opts["source"] != "all":
            qs = qs.filter(source=opts["source"])
        if opts["category"]:
            qs = qs.filter(product_type__slug=opts["category"])
        if opts["limit"] > 0:
            qs = qs[: opts["limit"]]

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== name クリーンアップ / {total} 件 ==="
        ))

        changed = 0
        accessory_count = 0
        skipped_no_data = 0

        for p in qs:
            original = ""
            if isinstance(p.api_data, dict):
                r = p.api_data.get("rakuten", {}) or {}
                a = p.api_data.get("amazon", {}) or {}
                original = (
                    r.get("itemName") or r.get("title")
                    or a.get("title") or ""
                )

            if not original:
                skipped_no_data += 1
                continue

            new_name = clean_product_name(original, brand_hint=p.brand)
            if not new_name or new_name == p.name:
                continue

            is_acc = is_accessory(original)
            marker = "[ACC]" if is_acc else "    "
            self.stdout.write(f"{marker} [{p.id:4d}] {p.name[:35]}")
            self.stdout.write(f"           -> {new_name}")

            if is_acc:
                accessory_count += 1

            if not opts["dry_run"]:
                p.name = new_name
                p.save(update_fields=["name"])
            changed += 1

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== サマリー ==="))
        self.stdout.write(f"  対象: {total} 件")
        self.stdout.write(f"  変更あり: {changed} 件")
        self.stdout.write(f"  アクセサリ判定([ACC]): {accessory_count} 件")
        self.stdout.write(f"  api_data 無しスキップ: {skipped_no_data} 件")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n  ※ --dry-run のため DB 変更なし"))
