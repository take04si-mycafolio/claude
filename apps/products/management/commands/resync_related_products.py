"""記事本文の [product slug=] から Article.related_products を一括再同期する。

post_save シグナルと同じロジック (apps.products.signals.sync_related_products) を
全記事(または --slug 指定)に適用する。既存記事の M2M を本文基準で埋め直す用途。

使い方:
  python manage.py resync_related_products              # 公開記事すべて
  python manage.py resync_related_products --all        # 非公開も含む全記事
  python manage.py resync_related_products --slug=osusume-hikaku --slug=1man-ika-biganki
  python manage.py resync_related_products --dry-run    # 変更せず件数のみ表示
"""
from django.core.management.base import BaseCommand

from apps.products.models import Article
from apps.products.signals import extract_product_slugs, sync_related_products


class Command(BaseCommand):
    help = "記事本文の [product slug=] から Article.related_products を再同期する"

    def add_arguments(self, parser):
        parser.add_argument("--slug", action="append", dest="slugs", default=None,
                            help="対象スラッグ(複数指定可)。省略時は対象記事すべて")
        parser.add_argument("--all", action="store_true",
                            help="非公開記事も含める(既定は is_published=True のみ)")
        parser.add_argument("--dry-run", action="store_true",
                            help="DBを変更せず、抽出される商品数のみ表示")

    def handle(self, *args, **opts):
        qs = Article.objects.all()
        if opts["slugs"]:
            qs = qs.filter(slug__in=opts["slugs"])
        elif not opts["all"]:
            qs = qs.filter(is_published=True)

        total_articles = touched = total_links = 0
        for a in qs.order_by("slug"):
            slugs = extract_product_slugs(a.content)
            if not slugs:
                continue
            total_articles += 1
            if opts["dry_run"]:
                n = a.related_products.filter(slug__in=slugs).count()
                self.stdout.write(f"  [dry] {a.slug}: 本文{len(slugs)}件 / 既存M2M一致{n}件")
                total_links += len(slugs)
                continue
            n = sync_related_products(a)
            touched += 1
            total_links += n
            self.stdout.write(f"  {a.slug}: related_products={n}")

        verb = "対象(dry-run)" if opts["dry_run"] else "再同期"
        self.stdout.write(self.style.SUCCESS(
            f"{verb}完了: 記事{total_articles}件 / 更新{touched}件 / 紐付け延べ{total_links}件"
        ))
