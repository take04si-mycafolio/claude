"""
使い方:
  python manage.py generate_article --product-slug eh-sa3b --keyword "EH-SA3B 口コミ"
  python manage.py generate_article --all-keywords --limit 10
"""
from django.core.management.base import BaseCommand, CommandError
from apps.products.models import Product
from apps.aiarticles.models import ProductArticleKeyword
from apps.aiarticles import generator


class Command(BaseCommand):
    help = "DB保存の商品情報のみを使ってAI記事を生成"

    def add_arguments(self, parser):
        parser.add_argument("--product-slug", help="商品のslug")
        parser.add_argument("--keyword", help="ターゲットキーワード")
        parser.add_argument("--all-keywords", action="store_true",
                            help="未生成のキーワードを優先順で全部生成")
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument("--ai-provider", default="stub")

    def handle(self, *args, **opts):
        if opts["all_keywords"]:
            qs = ProductArticleKeyword.objects.filter(is_generated=False).select_related("product")[:opts["limit"]]
            for kw in qs:
                self.stdout.write(f"→ {kw.product.name} / {kw.keyword}")
                try:
                    pa = generator.generate_article(kw.product, kw.keyword, ai_provider=opts["ai_provider"])
                    kw.is_generated = True
                    kw.save(update_fields=["is_generated"])
                    self.stdout.write(self.style.SUCCESS(f"  ✓ ID={pa.id} status={pa.status}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ {e}"))
        elif opts["product_slug"] and opts["keyword"]:
            product = Product.objects.get(slug=opts["product_slug"])
            pa = generator.generate_article(product, opts["keyword"], ai_provider=opts["ai_provider"])
            self.stdout.write(self.style.SUCCESS(f"OK: ID={pa.id} status={pa.status}"))
        else:
            raise CommandError("--product-slug + --keyword か --all-keywords を指定")
