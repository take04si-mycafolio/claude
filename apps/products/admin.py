from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import markdown as md_lib
from .models import ApiCredential, Product, Category, Article, ArticleImage, SeoWeeklyReport


class ArticleImageInline(admin.StackedInline):
    """記事内に貼り付ける画像を記事ページから直接管理。
    アップロード後にコピー用のHTMLスニペットが3パターン自動表示される。"""
    model = ArticleImage
    extra = 1
    fields = ('image', 'alt_text', 'caption', 'order', 'preview',
              'snippet_simple', 'snippet_figure', 'snippet_center')
    readonly_fields = ('preview', 'snippet_simple', 'snippet_figure', 'snippet_center')
    classes = ('collapse',)

    @admin.display(description='プレビュー')
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:240px;max-height:160px;border-radius:6px;border:1px solid #ddd">',
                obj.image.url,
            )
        return '—'

    def _snippet_input(self, snippet):
        return format_html(
            '<input type="text" readonly value="{}" '
            'onclick="this.select();" '
            'style="width:100%;font-size:11px;font-family:monospace;padding:6px;">',
            snippet,
        )

    @admin.display(description='① シンプルな画像')
    def snippet_simple(self, obj):
        if not obj.image:
            return '—'
        alt = obj.alt_text or ''
        return self._snippet_input(
            f'<img src="{obj.image.url}" alt="{alt}" '
            f'style="max-width:100%;height:auto;border-radius:8px;margin:16px 0;">'
        )

    @admin.display(description='② キャプション付き<figure>')
    def snippet_figure(self, obj):
        if not obj.image:
            return '—'
        alt = obj.alt_text or ''
        cap = obj.caption or alt
        return self._snippet_input(
            f'<figure style="margin:24px 0;text-align:center;">'
            f'<img src="{obj.image.url}" alt="{alt}" '
            f'style="max-width:100%;height:auto;border-radius:8px;">'
            f'<figcaption style="font-size:12px;color:#888;margin-top:8px;">{cap}</figcaption>'
            f'</figure>'
        )

    @admin.display(description='③ センター大画像')
    def snippet_center(self, obj):
        if not obj.image:
            return '—'
        alt = obj.alt_text or ''
        return self._snippet_input(
            f'<div style="text-align:center;margin:24px 0;">'
            f'<img src="{obj.image.url}" alt="{alt}" '
            f'style="max-width:100%;height:auto;border-radius:8px;">'
            f'</div>'
        )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "slug", "parent", "show_in_header", "sort_order")
    list_display_links = ("thumb", "name")
    list_filter = ("parent", "show_in_header")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("show_in_header", "sort_order")
    ordering = ("parent__name", "sort_order", "name")
    fieldsets = (
        ("基本情報", {"fields": ("name", "slug", "parent", "sort_order", "show_in_header")}),
        ("説明", {"fields": ("description",)}),
        ("画像(イラスト)", {
            "fields": ("image", "image_url"),
            "description": "カテゴリTOPページに表示するイラスト/アイキャッチ画像。imageフィールドにアップロードするか、image_urlに外部URLを指定。",
        }),
        ("ランディングHTML", {"fields": ("landing_html",), "classes": ("collapse",)}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    @admin.display(description="画像")
    def thumb(self, obj):
        from django.utils.html import format_html
        url = ''
        try:
            if obj.image and obj.image.name:
                url = obj.image.url
        except Exception:
            pass
        if not url:
            url = obj.image_url or ''
        if url:
            return format_html('<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:6px">', url)
        return "—"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "brand", "product_type", "price",
                    "is_published", "is_discontinued", "sort_order", "updated_at")
    list_display_links = ("thumb", "name")
    list_filter = ("is_published", "is_discontinued", "product_type", "brand", "categories")
    search_fields = ("name", "brand", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_published", "is_discontinued", "sort_order", "price")
    filter_horizontal = ("categories",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("product_type",)
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        ("基本情報", {"fields": ("name", "slug", "brand", "product_type",
                              "price", "is_published", "sort_order")}),
        ("カテゴリ(機能)", {"fields": ("categories",)}),
        ("画像", {"fields": ("image", "image_url")}),
        ("商品説明", {"fields": ("description", "features")}),
        ("購入リンク", {"fields": ("official_url", "affiliate_url",
                                "rakuten_url", "amazon_url")}),
        ("SEO", {
            "fields": ("meta_title", "meta_description"),
            "description": "検索結果に表示されるタイトル・説明文。空欄ならそれぞれ商品名・商品説明から自動取得します。",
        }),
        ("WP移行情報", {"fields": ("wp_post_id",), "classes": ("collapse",)}),
        ("日時", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="画像")
    def thumb(self, obj):
        url = obj.display_image if hasattr(obj, "display_image") else (obj.image_url or "")
        if url:
            return format_html('<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:6px">', url)
        return "—"


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "index_status",
                    "index_checked_at", "updated_at")
    list_display_links = ("title",)
    list_filter = ("is_published", "index_status", "product_type", "published_at")
    search_fields = ("title", "slug", "excerpt", "content", "seo_keyword")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_published",)
    list_select_related = ("product_type",)
    filter_horizontal = ("related_products",)
    autocomplete_fields = ("product_type",)
    readonly_fields = ("created_at", "updated_at", "seo_check_display",
                       "index_status", "index_checked_at", "index_raw_status")
    date_hierarchy = "published_at"
    list_per_page = 30
    save_on_top = True
    inlines = (ArticleImageInline,)
    actions = (
        "run_compliance_seo_check",
        "rewrite_anthropic",
        "rewrite_openai",
        "set_category_bigankiki",
        "set_category_biyou",
        "publish_selected",
        "unpublish_selected",
        "recheck_indexing",
    )

    fieldsets = (
        ("基本情報", {"fields": ("title", "slug", "product_type", "is_published", "published_at")}),
        ("SEO設定", {"fields": ("seo_keyword", "meta_title", "meta_description"),
                     "description": "検索エンジン向けの設定。空欄時はタイトル/抜粋がフォールバックとして使われます。"}),
        ("内容", {
            "fields": ("thumbnail", "thumbnail_url", "excerpt", "content"),
            "description": (
                "商品カード埋込: 本文内に [product slug=\"商品スラッグ\"]紹介文(改行可)[/product] "
                "と書くと商品カードが自動表示されます。商品スラッグはProducts一覧のslug列で確認できます。"
            ),
        }),
        ("関連商品", {"fields": ("related_products",)}),
        ("構造化データ(JSON-LD)", {
            "fields": ("structured_data",),
            "classes": ("collapse",),
            "description": "Schema.org の JSON-LD をペーストすると、記事ページ内に script タグで自動出力されます。FAQPage / ItemList / Article などに対応。Google リッチリザルトテスト( https://search.google.com/test/rich-results )で事前に検証してから貼り付けるのが安全です。",
        }),
        ("品質チェック結果", {"fields": ("seo_check_display",), "classes": ("collapse",)}),
        ("Googleインデックス状況", {
            "fields": ("index_status", "index_checked_at", "index_raw_status"),
            "classes": ("collapse",),
            "description": "check_indexing コマンド（URL Inspection API）で自動更新されます。手動編集は不要です。",
        }),
        ("WP移行情報", {"fields": ("wp_post_id", "wp_author"), "classes": ("collapse",)}),
        ("日時", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="SEO・コンプライアンス チェック結果")
    def seo_check_display(self, obj):
        from django.utils.safestring import mark_safe
        from django.utils.html import escape
        import json
        d = obj.seo_check_result or {}
        if not d:
            return "未実施"
        return mark_safe(
            f'<pre style="background:#FBF6F4;padding:12px;border-radius:8px;font-size:11px;max-height:400px;overflow:auto">{escape(json.dumps(d, ensure_ascii=False, indent=2))}</pre>'
        )

    @admin.action(description="🔍 コンプライアンス + SEO品質チェックを実行")
    def run_compliance_seo_check(self, request, queryset):
        from apps.aiarticles.compliance import ArticleComplianceService
        from apps.aiarticles import seo_quality
        from django.utils import timezone
        for art in queryset:
            kw = art.seo_keyword or art.title[:30]
            cc = ArticleComplianceService.check(art.content)
            sm = seo_quality.analyze_seo_metrics(art.content, kw)
            art.seo_check_result = {
                "compliance": cc, "metrics": sm,
                "keyword_used": kw,
                "checked_at": timezone.now().isoformat(),
            }
            art.save(update_fields=["seo_check_result"])
        self.message_user(request, f"{queryset.count()}件のチェック完了")

    @admin.action(description="🔁 Anthropic Claudeで全文AI再生成 (薬機法+SEO準拠)")
    def rewrite_anthropic(self, request, queryset):
        from apps.aiarticles import rewriter
        n_ok, n_ng = 0, 0
        for art in queryset:
            kw = art.seo_keyword or art.title[:30]
            r = rewriter.rewrite_article(art, keyword=kw, ai_provider="anthropic", max_attempts=3)
            if r["success"]:
                n_ok += 1
            else:
                n_ng += 1
        self.message_user(request, f"全文再生成: 成功 {n_ok}件 / 失敗 {n_ng}件")

    @admin.action(description="🔁 OpenAI GPTで全文AI再生成 (薬機法+SEO準拠)")
    def rewrite_openai(self, request, queryset):
        from apps.aiarticles import rewriter
        n_ok, n_ng = 0, 0
        for art in queryset:
            kw = art.seo_keyword or art.title[:30]
            r = rewriter.rewrite_article(art, keyword=kw, ai_provider="openai", max_attempts=3)
            if r["success"]:
                n_ok += 1
            else:
                n_ng += 1
        self.message_user(request, f"全文再生成: 成功 {n_ok}件 / 失敗 {n_ng}件")

    @admin.action(description="選択した記事のカテゴリを「美顔器」に設定")
    def set_category_bigankiki(self, request, queryset):
        from .models import Category
        cat = Category.objects.filter(parent__isnull=True, slug="bigankiki").first()
        if cat:
            n = queryset.update(product_type=cat)
            self.message_user(request, f"{n}件を美顔器カテゴリに設定")

    @admin.action(description="選択した記事のカテゴリを「美容コラム」に設定")
    def set_category_biyou(self, request, queryset):
        from .models import Category
        cat = Category.objects.filter(parent__isnull=True, slug="biyou").first()
        if cat:
            n = queryset.update(product_type=cat)
            self.message_user(request, f"{n}件を美容コラムカテゴリに設定")

    @admin.action(description="選択した記事を公開状態にする")
    def publish_selected(self, request, queryset):
        n = queryset.update(is_published=True)
        self.message_user(request, f"{n}件を公開しました")

    @admin.action(description="選択した記事を非公開にする")
    def unpublish_selected(self, request, queryset):
        n = queryset.update(is_published=False)
        self.message_user(request, f"{n}件を非公開にしました")

    @admin.action(description="🔎 選択した記事のインデックス状況を再チェック")
    def recheck_indexing(self, request, queryset):
        from django.core.management import call_command
        from django.contrib import messages
        slugs = list(queryset.values_list("slug", flat=True))
        if not slugs:
            self.message_user(request, "対象がありません", level=messages.WARNING)
            return
        try:
            # check_indexing --slug=... を選択記事について順次実行
            call_command("check_indexing", slug=slugs)
        except Exception as e:  # noqa: BLE001
            self.message_user(
                request, f"インデックス再チェックに失敗しました: {type(e).__name__}: {e}",
                level=messages.ERROR,
            )
            return
        self.message_user(request, f"{len(slugs)}件のインデックス状況を再チェックしました")



@admin.register(ApiCredential)
class ApiCredentialAdmin(admin.ModelAdmin):
    """シングルトン管理: 一覧画面を変更画面にリダイレクト風の挙動。"""

    fieldsets = (
        ("Amazon PA-API v5", {
            "fields": (
                "is_amazon_enabled",
                "amazon_access_key",
                "amazon_secret_key",
                "amazon_partner_tag",
                "amazon_marketplace",
            ),
            "description": "Amazon Associates Central で発行した認証情報。シークレットキーは再表示できないので保管時は必ず控えてください。",
        }),
        ("楽天市場 API", {
            "fields": (
                "is_rakuten_enabled",
                "rakuten_app_id",
                "rakuten_access_key",
                "rakuten_affiliate_id",
            ),
            "description": "楽天デベロッパー(アプリID) + 楽天アフィリエイト(アフィリID)で取得。",
        }),
        ("メタ", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # 既に1件あれば追加不可
        return not ApiCredential.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        from django import forms as djforms
        form = super().get_form(request, obj, **kwargs)
        # 秘密鍵系を password 風に
        for field_name in ("amazon_secret_key", "amazon_access_key",
                           "rakuten_app_id", "rakuten_access_key", "rakuten_affiliate_id"):
            if field_name in form.base_fields:
                form.base_fields[field_name].widget = djforms.PasswordInput(
                    render_value=True,
                    attrs={"autocomplete": "off", "style": "width: 480px;"},
                )
        return form


@admin.register(SeoWeeklyReport)
class SeoWeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('period_display', 'total_clicks', 'total_impressions', 'avg_ctr_display', 'total_sessions', 'generated_at')
    list_filter = ('period_end',)
    ordering = ('-period_end',)
    readonly_fields = ('rendered_report_display', 'generated_at')

    fieldsets = (
        ('📊 レポート概要', {
            'fields': ('period_start', 'period_end', 'generated_at'),
        }),
        ('📈 サマリ指標', {
            'fields': ('total_clicks', 'total_impressions', 'avg_ctr', 'total_sessions', 'avg_position'),
        }),
        ('📊 前週比較', {
            'fields': ('clicks_change_pct', 'sessions_change_pct'),
            'classes': ('collapse',),
        }),
        ('📝 週次レポート（整形表示）', {
            'fields': ('rendered_report_display',),
        }),
        ('📂 元データ（Markdown）', {
            'fields': ('report_markdown',),
            'classes': ('collapse',),
        }),
        ('🔍 詳細データ（JSON）', {
            'fields': ('top_pages', 'top_queries', 'winners', 'losers',
                       'rewrite_candidates', 'ctr_underperformers', 'suggested_actions'),
            'classes': ('collapse',),
        }),
    )

    def period_display(self, obj):
        return f"{obj.period_start} 〜 {obj.period_end}"
    period_display.short_description = '期間'

    def avg_ctr_display(self, obj):
        return f"{obj.avg_ctr:.2f}%"
    avg_ctr_display.short_description = '平均CTR'

    def rendered_report_display(self, obj):
        if not obj.report_markdown:
            return mark_safe('<p style="color: #999;">まだレポートが生成されていません</p>')
        html = md_lib.markdown(obj.report_markdown, extensions=['tables', 'fenced_code', 'nl2br'])
        styled = f'''
        <div style="max-width: 900px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.7; padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
        {html}
        </div>
        '''
        return mark_safe(styled)
    rendered_report_display.short_description = 'レポート本文'
