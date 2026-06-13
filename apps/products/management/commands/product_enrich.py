"""既存商品に楽天/Amazonアフィリエイトリンクを自動補完。"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.products.models import Category, Product
from apps.products.services import rakuten_sync, amazon_sync
from apps.products.services.sync_common import similarity


class Command(BaseCommand):
    help = "既存商品に楽天/Amazonアフィリエイトリンクを自動補完"

    def add_arguments(self, parser):
        parser.add_argument("--category", required=True)
        parser.add_argument("--source", choices=["rakuten", "amazon"], default="rakuten")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--missing-only", action="store_true")
        parser.add_argument("--threshold", type=float, default=0.80)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        ptype = Category.objects.filter(slug=opts["category"], parent__isnull=True).first()
        if not ptype:
            raise CommandError(f"カテゴリ slug='{opts['category']}' が見つかりません")

        qs = Product.objects.filter(is_published=True, product_type=ptype)
        if opts["missing_only"]:
            if opts["source"] == "rakuten":
                qs = qs.filter(rakuten_url="")
            else:
                qs = qs.filter(amazon_url="")
        qs = qs.order_by("sort_order", "id")
        if opts["limit"] > 0:
            qs = qs[: opts["limit"]]

        total = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== {opts['source'].upper()} enrichment / {total}件 対象 ==="
        ))

        counts = {"matched": 0, "low_score": 0, "no_result": 0, "api_off": 0}

        for p in qs:
            self.stdout.write(f"\n[{p.id:4d}] {p.name[:50]}")

            if opts["source"] == "rakuten":
                if not rakuten_sync.is_enabled():
                    counts["api_off"] += 1
                    continue
                results = rakuten_sync.search_items(keyword=p.name, hits=3)
            else:
                if not amazon_sync.is_enabled():
                    counts["api_off"] += 1
                    continue
                results = amazon_sync.search_items(keyword=p.name, count=3)

            if not results:
                self.stdout.write(self.style.WARNING("  -> 検索結果0件"))
                counts["no_result"] += 1
                continue

            best, best_score = None, 0.0
            for r in results:
                s = similarity(p.name, r.get("title", ""))
                if s > best_score:
                    best, best_score = r, s

            if best_score < opts["threshold"]:
                self.stdout.write(self.style.WARNING(
                    f"  -> 低スコア {best_score:.2f}: {(best.get('title','') or '')[:40]}"
                ))
                counts["low_score"] += 1
                continue

            url = (
                best.get("affiliate_url") or best.get("rakuten_url")
                if opts["source"] == "rakuten"
                else best.get("amazon_url")
            )
            self.stdout.write(self.style.SUCCESS(
                f"  [マッチ {best_score:.2f}] {(best.get('title','') or '')[:40]}"
            ))
            self.stdout.write(f"     URL: {(url or '')[:80]}")

            if not opts["dry_run"] and url:
                if opts["source"] == "rakuten":
                    p.rakuten_url = url
                    p.rakuten_item_code = best.get("rakuten_item_code", "")
                    p.rakuten_synced_at = timezone.now()
                else:
                    p.amazon_url = url
                    p.asin = best.get("asin", "")
                    p.amazon_synced_at = timezone.now()
                if not p.image_url and best.get("image_url"):
                    p.image_url = best["image_url"]
                p.save()
            counts["matched"] += 1

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== サマリー ==="))
        for k, v in counts.items():
            self.stdout.write(f"  {k}: {v}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n  ※ --dry-run のため DB 変更なし"))
