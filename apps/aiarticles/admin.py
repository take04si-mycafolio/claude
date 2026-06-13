from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ProductArticleKeyword, ProductArticle, ArticleGenerationLog, NgExpressionRule, SeoKeywordStrategy
from . import generator


@admin.register(ProductArticleKeyword)
class ProductArticleKeywordAdmin(admin.ModelAdmin):
    list_display = ("product", "keyword", "priority", "search_volume", "is_generated", "created_at")
    list_filter = ("is_generated", "created_at")
    search_fields = ("product__name", "keyword")
    autocomplete_fields = ("product",)
    list_editable = ("priority",)
    list_per_page = 50
    actions = ("generate_articles",)

    @admin.action(description="選択キーワードでAI記事を生成")
    def generate_articles(self, request, queryset):
        n = 0
        for kw in queryset:
            try:
                generator.generate_article(kw.product, kw.keyword)
                kw.is_generated = True
                kw.save(update_fields=["is_generated"])
                n += 1
            except Exception as e:
                self.message_user(request, f"失敗: {kw.keyword} - {e}", level="error")
        self.message_user(request, f"{n}件のAI記事を生成しました(下書き状態)")


@admin.register(ProductArticle)
class ProductArticleAdmin(admin.ModelAdmin):
    list_display = ("status_badge", "title_short", "product", "keyword",
                    "yakkihou_badge", "ai_generated_at", "human_reviewer")
    list_filter = ("status", "yakkihou_passed", "ai_generated_at")
    search_fields = ("title", "keyword", "content", "product__name")
    autocomplete_fields = ("product", "human_reviewer", "published_article")
    readonly_fields = ("ai_generated_at", "human_reviewed_at", "created_at", "updated_at",
                       "yakkihou_check_display")
    date_hierarchy = "ai_generated_at"
    list_per_page = 30
    save_on_top = True
    actions = ("approve_articles", "reject_articles", "publish_approved")

    fieldsets = (
        ("対象", {"fields": ("product", "keyword", "status")}),
        ("記事内容", {"fields": ("title", "excerpt", "content")}),
        ("品質チェック", {"fields": ("yakkihou_passed", "yakkihou_check_display")}),
        ("レビュー", {"fields": ("human_reviewer", "human_reviewed_at")}),
        ("公開連携", {"fields": ("published_article",)}),
        ("メタ", {"fields": ("ai_generated_at", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="状態")
    def status_badge(self, obj):
        colors = {
            "draft": ("#FEF2F2", "#991B1B"),
            "pending_review": ("#FFFBEB", "#B45309"),
            "approved": ("#EFF6FF", "#1D4ED8"),
            "published": ("#ECFDF5", "#047857"),
            "rejected": ("#F3F4F6", "#6B7280"),
        }
        bg, fg = colors.get(obj.status, ("#EEE", "#666"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">{}</span>',
            bg, fg, obj.get_status_display())

    @admin.display(description="タイトル")
    def title_short(self, obj):
        return obj.title[:50] + ("…" if len(obj.title) > 50 else "")

    @admin.display(description="薬機法")
    def yakkihou_badge(self, obj):
        if obj.yakkihou_passed:
            return format_html('<span style="color:#047857;font-weight:700">✓ OK</span>')
        return format_html('<span style="color:#991B1B;font-weight:700">⚠ 要確認</span>')

    @admin.display(description="薬機法チェック詳細")
    def yakkihou_check_display(self, obj):
        import json
        return format_html('<pre style="background:#FBF6F4;padding:10px;border-radius:8px;font-size:11px">{}</pre>',
                           json.dumps(obj.yakkihou_check, ensure_ascii=False, indent=2))

    @admin.action(description="✓ 承認(approved)")
    def approve_articles(self, request, queryset):
        n = queryset.update(status="approved", human_reviewer=request.user, human_reviewed_at=timezone.now())
        self.message_user(request, f"{n}件を承認しました")

    @admin.action(description="✗ 却下(rejected)")
    def reject_articles(self, request, queryset):
        n = queryset.update(status="rejected", human_reviewer=request.user, human_reviewed_at=timezone.now())
        self.message_user(request, f"{n}件を却下しました")

    @admin.action(description="📢 承認済を公開(Article作成)")
    def publish_approved(self, request, queryset):
        n = 0
        for pa in queryset.filter(status="approved"):
            try:
                generator.publish_article(pa, user=request.user)
                n += 1
            except Exception as e:
                self.message_user(request, f"失敗: {pa.title[:30]} - {e}", level="error")
        self.message_user(request, f"{n}件を公開しました")


@admin.register(ArticleGenerationLog)
class ArticleGenerationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "success_badge", "product", "keyword",
                    "ai_model", "tokens_total", "duration_ms")
    list_filter = ("success", "ai_provider", "ai_model", "created_at")
    search_fields = ("keyword", "product__name", "raw_output", "error_message")
    readonly_fields = [f.name for f in ArticleGenerationLog._meta.fields]
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

    @admin.display(description="結果")
    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color:#047857;font-weight:700">✓</span>')
        return format_html('<span style="color:#991B1B;font-weight:700">✗</span>')

    @admin.display(description="トークン")
    def tokens_total(self, obj):
        if obj.tokens_input is None and obj.tokens_output is None:
            return "-"
        return f"{(obj.tokens_input or 0):,} → {(obj.tokens_output or 0):,}"



# ===== 記事タイプ別 推奨テンプレ説明 =====
ARTICLE_TYPE_TEMPLATES = {
    "review": "「商品名 口コミ」向け。ユーザーの体験・写真付きレビュー・良い点/悪い点を中心に構成。",
    "effect": "「商品名 効果」「美顔器 効果」向け。薬機法に注意し、効果断定ではなく使用感・サポート表現で構成。",
    "comparison": "「A B 比較」「RF EMS 違い」向け。CVが高い記事。比較表・おすすめする人/しない人を必ず入れる。",
    "ranking": "「おすすめ」「ランキング」向け。入口記事。カテゴリ内の商品記事へ内部リンクする。",
    "howto": "「使い方」向け。使用手順・注意点・FAQを中心に構成。",
    "faq": "「意味ある？」「本当に必要？」など疑問解決向け。結論ファーストで構成。",
}


@admin.register(SeoKeywordStrategy)
class SeoKeywordStrategyAdmin(admin.ModelAdmin):
    list_display = (
        "priority_badge", "keyword", "category", "article_type",
        "search_volume", "commercial_intent_score", "competition_score",
        "status_badge", "status", "target_url_short", "updated_at",
    )
    list_display_links = ("keyword",)
    list_filter = ("status", "article_type", "category", "assigned_to")
    search_fields = ("keyword", "search_intent", "memo", "category")
    list_editable = ("status", "search_volume", "commercial_intent_score", "competition_score")
    list_per_page = 50
    ordering = ("-priority_score",)
    autocomplete_fields = ("related_product", "related_article", "parent_keyword", "assigned_to")
    filter_horizontal = ("internal_link_targets",)
    date_hierarchy = "updated_at"
    save_on_top = True
    actions = (
        "set_status_planned", "set_status_writing",
        "set_status_generated", "set_status_published",
        "create_product_article_keyword", "create_article_draft",
    )

    fieldsets = (
        ("基本情報", {"fields": ("category", "keyword", "search_intent", "article_type", "article_type_template")}),
        ("優先度計算", {"fields": ("search_volume", "commercial_intent_score", "competition_score", "priority_score")}),
        ("ステータス・担当", {"fields": ("status", "assigned_to", "target_url")}),
        ("関連リンク", {"fields": ("related_product", "related_article")}),
        ("内部リンク戦略", {"fields": ("parent_keyword", "internal_link_targets", "link_anchor_text")}),
        ("メモ", {"fields": ("memo",)}),
        ("日時", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("priority_score", "article_type_template", "created_at", "updated_at")

    @admin.display(description="優先度")
    def priority_badge(self, obj):
        s = obj.priority_score or 0
        if s >= 80:
            bg, color, label = "#FEE2E2", "#7F1D1D", f"🔥最優先 {s:.0f}"
        elif s >= 40:
            bg, color, label = "#FED7AA", "#9A3412", f"高 {s:.0f}"
        elif s >= 10:
            bg, color, label = "#FEF3C7", "#92400E", f"中 {s:.0f}"
        else:
            bg, color, label = "#F3F4F6", "#6B7280", f"低 {s:.0f}"
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700;white-space:nowrap">{}</span>',
            bg, color, label,
        )

    @admin.display(description="状態")
    def status_badge(self, obj):
        colors = {
            "idea": ("#F3F4F6", "#6B7280"),
            "planned": ("#EFF6FF", "#1D4ED8"),
            "writing": ("#FFFBEB", "#B45309"),
            "generated": ("#FAF5FF", "#7C3AED"),
            "checking": ("#FEF3C7", "#92400E"),
            "published": ("#ECFDF5", "#047857"),
            "rewrite": ("#FEF2F2", "#991B1B"),
            "hold": ("#F3F4F6", "#9CA3AF"),
        }
        bg, fg = colors.get(obj.status, ("#EEE", "#666"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">{}</span>',
            bg, fg, obj.get_status_display(),
        )

    @admin.display(description="公開URL")
    def target_url_short(self, obj):
        if not obj.target_url:
            return "-"
        url = obj.target_url
        short = url[:35] + "..." if len(url) > 35 else url
        return format_html('<a href="{}" target="_blank" style="color:#C97B84">{}</a>', url, short)

    @admin.display(description="📋 記事タイプ別 推奨構成")
    def article_type_template(self, obj):
        from django.utils.safestring import mark_safe
        tpl = ARTICLE_TYPE_TEMPLATES.get(obj.article_type, "")
        if not tpl:
            return "-"
        return mark_safe(
            f'<div style="background:#FBF6F4;border-left:4px solid #C97B84;padding:10px 14px;'
            f'border-radius:0 8px 8px 0;font-size:13px;line-height:1.7;color:#3A2E33">{tpl}</div>'
        )

    # ----- ステータス変更アクション -----
    @admin.action(description="📝 「作成予定」に変更")
    def set_status_planned(self, request, queryset):
        n = queryset.update(status="planned")
        self.message_user(request, f"{n}件を「作成予定」に変更")

    @admin.action(description="✍ 「執筆中」に変更")
    def set_status_writing(self, request, queryset):
        n = queryset.update(status="writing")
        self.message_user(request, f"{n}件を「執筆中」に変更")

    @admin.action(description="🤖 「AI生成済み」に変更")
    def set_status_generated(self, request, queryset):
        n = queryset.update(status="generated")
        self.message_user(request, f"{n}件を「AI生成済み」に変更")

    @admin.action(description="📢 「公開済み」に変更")
    def set_status_published(self, request, queryset):
        n = queryset.update(status="published")
        self.message_user(request, f"{n}件を「公開済み」に変更")

    # ----- 既存AI生成機能との連携 -----
    @admin.action(description="🔗 ProductArticleKeyword を作成 (AI生成準備)")
    def create_product_article_keyword(self, request, queryset):
        """選択キーワードから ProductArticleKeyword を作成 (AI生成の前段階)"""
        n_created, n_skipped = 0, 0
        for sk in queryset:
            if not sk.related_product:
                n_skipped += 1
                continue
            obj, created = ProductArticleKeyword.objects.get_or_create(
                product=sk.related_product,
                keyword=sk.keyword,
                defaults={
                    "search_volume": sk.search_volume,
                    "priority": int(sk.priority_score),
                    "notes": f"From SeoKeywordStrategy #{sk.id} ({sk.get_article_type_display()})",
                }
            )
            if created:
                sk.status = "planned"
                sk.save(update_fields=["status"])
                n_created += 1
        self.message_user(
            request,
            f"作成: {n_created}件 / スキップ: {n_skipped}件 (related_product 未設定はスキップ)"
        )

    @admin.action(description="📄 products.Article の下書きを作成")
    def create_article_draft(self, request, queryset):
        """選択キーワードから Article の下書きを作成"""
        from apps.products.models import Article, Category
        from django.utils.text import slugify
        n_created, n_skipped = 0, 0
        for sk in queryset:
            if sk.related_article:
                n_skipped += 1
                continue
            base_slug = slugify(sk.keyword, allow_unicode=True)[:80]
            slug = base_slug
            i = 1
            while Article.objects.filter(slug=slug).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            ptype = None
            if sk.related_product and sk.related_product.product_type:
                ptype = sk.related_product.product_type
            elif sk.category:
                ptype = Category.objects.filter(parent__isnull=True, name=sk.category).first()                     or Category.objects.filter(parent__isnull=True, slug=sk.category).first()
            article = Article.objects.create(
                title=f"[下書き] {sk.keyword}",
                slug=slug,
                content="<p>下書きです。SeoKeywordStrategyから自動作成されました。</p>",
                excerpt=sk.search_intent[:200] if sk.search_intent else "",
                seo_keyword=sk.keyword,
                product_type=ptype,
                is_published=False,
            )
            sk.related_article = article
            sk.status = "writing"
            sk.save(update_fields=["related_article", "status"])
            n_created += 1
        self.message_user(
            request,
            f"Article下書き作成: {n_created}件 / スキップ: {n_skipped}件 (既に related_article あり)"
        )
