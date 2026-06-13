"""ブランド検索 → 新規商品取り込み (楽天 / Amazon)。"""
from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Category
from apps.products.services import rakuten_sync, amazon_sync
from apps.products.services.sync_common import (
    upsert_from_rakuten, upsert_from_amazon, find_existing_product,
    extract_model_numbers, clean_product_name,
)


class Command(BaseCommand):
    help = "ブランド検索で楽天/Amazonから新規商品を取り込む。重複は自動判定。"

    def add_arguments(self, parser):
        parser.add_argument("--brand", required=True)
        parser.add_argument("--keyword", default="")
        parser.add_argument("--category", required=True)
        parser.add_argument("--source", choices=["rakuten", "amazon", "all"], default="rakuten")
        parser.add_argument("--hits", type=int, default=10)
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--draft", action="store_true",
                            help="新規商品を非公開(下書き)で作成する")

    def handle(self, *args, **opts):
        ptype = Category.objects.filter(slug=opts["category"], parent__isnull=True).first()
        if not ptype:
            raise CommandError(f"カテゴリ slug='{opts['category']}' が見つかりません")

        sources = ["rakuten", "amazon"] if opts["source"] == "all" else [opts["source"]]
        results_summary = {}

        for src in sources:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {src.upper()} ==="))
            if src == "rakuten":
                if not rakuten_sync.is_enabled():
                    self.stdout.write(self.style.WARNING("  楽天API未設定 - スキップ"))
                    continue
                items = rakuten_sync.search_items(
                    keyword=opts["keyword"], brand=opts["brand"],
                    hits=opts["hits"], page=opts["page"],
                )
                upsert = upsert_from_rakuten
            else:
                if not amazon_sync.is_enabled():
                    self.stdout.write(self.style.WARNING("  Amazon API未設定 - スキップ"))
                    continue
                items = amazon_sync.search_items(
                    keyword=opts["keyword"], brand=opts["brand"], count=opts["hits"],
                )
                upsert = upsert_from_amazon

            if not items:
                self.stdout.write(self.style.WARNING("  取得 0件"))
                continue

            counts = {"created": 0, "updated": 0, "fuzzy_review": 0, "skipped": 0}
            seen_models = set()  # バッチ内重複検出 (同型番が複数ショップから来るのを防ぐ)
            seen_codes = set()
            for parsed in items:
                title_full = parsed.get("title") or ""
                title = title_full[:50]

                # バッチ内重複: 同じ rakuten_item_code 又は型番が既に処理されていればスキップ
                rcode = parsed.get("rakuten_item_code", "")
                target_models = extract_model_numbers(title_full)
                if rcode and rcode in seen_codes:
                    self.stdout.write(f"  [batch_dup] {title} (同 itemCode 重複スキップ)")
                    counts["skipped"] += 1
                    continue
                if target_models and target_models & seen_models:
                    self.stdout.write(f"  [batch_dup] {title} (同型番重複スキップ)")
                    counts["skipped"] += 1
                    continue

                # 後段で処理対象なら、型番/itemCode を記録
                if rcode:
                    seen_codes.add(rcode)
                if target_models:
                    seen_models.update(target_models)

                if opts["dry_run"]:
                    existing, mt = find_existing_product(parsed, ptype)
                    if existing:
                        action = "fuzzy_review" if mt == "fuzzy" else "updated"
                        marker = "[既存]" if action == "updated" else "[要確認]"
                        self.stdout.write(f"  {marker} [{mt}] {title} -> {existing.name[:40]}")
                    else:
                        action = "created"
                        cleaned = clean_product_name(title_full, brand_hint=opts["brand"])
                        self.stdout.write(f"  [新規] {title}")
                        self.stdout.write(f"         -> 整形後: {cleaned[:60]}")
                    counts[action] += 1
                else:
                    obj, action = upsert(parsed, ptype, brand_hint=opts["brand"], publish=not opts["draft"])
                    name = obj.name[:40] if obj else "-"
                    self.stdout.write(f"  [{action}] {name}")
                    counts[action] += 1

            results_summary[src] = counts

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== サマリー ==="))
        for src, c in results_summary.items():
            self.stdout.write(
                f"  {src}: created={c['created']} / updated={c['updated']} / "
                f"fuzzy_review={c['fuzzy_review']} / skipped={c['skipped']}"
            )
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n  ※ --dry-run のため DB 変更なし"))
