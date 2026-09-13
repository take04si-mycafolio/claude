"""
リライト作業台への手動追加  python manage.py add_rewrite_draft

GSCトリアージ由来でない任意の記事を、基準記事(お手本)を設定して作業台(RewriteDraft)に入れる。
指示書は make_rewrite_instructions と同じ決定論ロジックで生成する（LLM不使用）。

    python manage.py add_rewrite_draft --slug=biyou-kaden-kaitori
    python manage.py add_rewrite_draft --slug=biyou-kaden-kaitori --reference=refa-curl-iron-pro-plus
    python manage.py add_rewrite_draft --slug=biyou-kaden-kaitori --force   # 未完下書きがあっても新規作成
"""
from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Article
from apps.analytics.rewrite_manual import create_manual_rewrite_draft, ManualRewriteError


class Command(BaseCommand):
    help = "記事を手動でリライト作業台(RewriteDraft)に追加する（基準記事を任意で設定）"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="リライト対象記事の slug")
        parser.add_argument("--reference", default=None,
                            help="基準記事(お手本)の slug（任意）")
        parser.add_argument("--keyword", action="append", default=None,
                            help="狙うキーワード（複数指定可・先頭が主クエリ）。"
                                 "例: --keyword='美容家電 買取' --keyword='美顔器 売る'")
        parser.add_argument("--force", action="store_true",
                            help="未完の下書きが既にあっても新規作成する")

    def _get(self, slug, label):
        try:
            return Article.objects.get(slug=slug)
        except Article.DoesNotExist:
            raise CommandError(f"{label}記事が見つかりません: slug={slug}")

    def handle(self, *args, **opts):
        article = self._get(opts["slug"], "対象")
        reference = self._get(opts["reference"], "基準") if opts["reference"] else None
        try:
            rd = create_manual_rewrite_draft(article, reference_article=reference,
                                             force=opts["force"],
                                             keywords=opts.get("keyword"))
        except ManualRewriteError as e:
            raise CommandError(str(e))

        ref_txt = f" / 基準記事: /{reference.slug}/" if reference else ""
        kw_txt = (f" / キーワード{len(rd.target_grow)}件: "
                  + "、".join(q.get("query", "") for q in rd.target_grow)) if rd.target_grow else ""
        self.stdout.write(self.style.SUCCESS(
            f"✅ 作業台に追加: Draft #{rd.id} ← /{article.slug}/"
            f"（status=instructed・手動{ref_txt}{kw_txt}）"))
        self.stdout.write(
            f"レビュー: https://sc-tsusho.jp/admin/analytics/rewritedraft/{rd.id}/change/")
