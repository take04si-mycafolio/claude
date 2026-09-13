from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    ProductUseLog,
    ProductUseLogImage,
    ProductUseLogReport,
    Review,
    ReviewHelpful,
    ReviewImage,
    ReviewReport,
    ReportStatus,
)


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0
    fields = ("thumb", "image", "order")
    readonly_fields = ("thumb",)

    @admin.display(description="プレビュー")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:8px;object-fit:cover">',
                obj.image.url,
            )
        return "-"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    inlines = (ReviewImageInline,)
    list_display = ("product", "user", "rating", "title", "is_approved",
                    "is_rejected", "is_deleted", "campaign_consumed_at",
                    "delete_count", "helpful_count", "created_at")
    list_display_links = ("product", "title")
    list_filter = ("is_deleted", "is_approved", "is_rejected", "rating",
                   "skin_type", "effectiveness", "usage_period", "created_at")
    search_fields = ("product__name", "user__email", "user__nickname",
                     "title", "body")
    autocomplete_fields = ("product", "user")
    list_editable = ("is_approved", "is_rejected")
    readonly_fields = ("created_at", "updated_at", "deleted_at",
                       "campaign_consumed_at", "delete_count")
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    actions = ("approve_selected", "unapprove_selected", "restore_selected")

    fieldsets = (
        ("対象", {"fields": ("product", "user", "is_approved")}),
        ("総合評価", {"fields": ("rating", "title", "body")}),
        ("詳細評価", {"fields": ("cospa", "control", "safety", "expression", "icon")}),
        ("投稿者属性", {"fields": ("skin_type", "usage_period", "effectiveness")}),
        ("削除・キャンペーン", {
            "fields": ("is_deleted", "deleted_at", "delete_count",
                       "campaign_consumed_at"),
            "description": "削除済み口コミは会員・サイトから見えず、運営のみ閲覧可。"
                           "キャンペーン算入済みは会員側で削除不可。",
        }),
        ("WP移行情報", {"fields": ("wp_comment_id",), "classes": ("collapse",)}),
        ("日時", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        # 運営は削除済みを含む全件を確認できる（既定マネージャは削除済みを隠すため）。
        return Review.all_objects.get_queryset()

    @admin.action(description="選択した口コミを復活する（削除を取り消す）")
    def restore_selected(self, request, queryset):
        n = queryset.update(is_deleted=False, deleted_at=None)
        self.message_user(request, f"{n}件を復活しました")

    @admin.display(description="参考になった", ordering="helpfuls__count")
    def helpful_count(self, obj):
        return obj.helpfuls.count()

    @admin.action(description="選択した口コミを承認する")
    def approve_selected(self, request, queryset):
        # queryset.update() では post_save が飛ばずミッション完了処理が走らないため
        # 1件ずつ save する（承認した時点で達成判定→承認待ちの達成記録が作られる）。
        n = 0
        for review in queryset.filter(is_approved=False):
            review.is_approved = True
            review.save(update_fields=["is_approved"])
            n += 1
        self.message_user(request, f"{n}件を承認しました")

    @admin.action(description="選択した口コミを非承認にする")
    def unapprove_selected(self, request, queryset):
        n = queryset.update(is_approved=False)
        self.message_user(request, f"{n}件を非承認にしました")


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    """口コミ通報の確認・対応用。自動削除/非表示はしない（運営が内容を見て判断する）。"""

    list_display = ("id", "review", "reporter", "reason", "status",
                    "created_at", "resolved_at", "resolved_by")
    list_display_links = ("id", "review")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("reporter__email", "review__title", "comment")
    autocomplete_fields = ("resolved_by",)
    readonly_fields = ("review", "reporter", "reason", "comment",
                       "created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        ("通報内容（読み取り専用）", {
            "fields": ("review", "reporter", "reason", "comment", "created_at"),
        }),
        ("対応（運営が編集）", {
            "fields": ("status", "admin_note", "resolved_by", "resolved_at"),
        }),
        ("更新日時", {"fields": ("updated_at",), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        # status を「対応済み」にしたら resolved_at を自動セット（未設定時のみ）。
        # 対応済み以外へ戻したら resolved_at をクリアする。複雑にしすぎない範囲の補助。
        if obj.status == ReportStatus.RESOLVED:
            if obj.resolved_at is None:
                obj.resolved_at = timezone.now()
            if obj.resolved_by is None:
                obj.resolved_by = request.user
        else:
            obj.resolved_at = None
        super().save_model(request, obj, form, change)


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ("user", "review_title", "review_product", "created_at")
    search_fields = ("user__email", "review__title", "review__product__name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user", "review")
    list_per_page = 50

    @admin.display(description="口コミタイトル")
    def review_title(self, obj):
        return obj.review.title

    @admin.display(description="商品")
    def review_product(self, obj):
        return obj.review.product.name


# ======================================================================
# 使用記録（ProductUseLog）の admin。運営は論理削除済みも含め全件確認できる。
# ======================================================================
class ProductUseLogImageInline(admin.TabularInline):
    model = ProductUseLogImage
    extra = 0
    fields = ("thumb", "image", "order")
    readonly_fields = ("thumb",)

    @admin.display(description="プレビュー")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:8px;object-fit:cover">',
                obj.image.url,
            )
        return "-"


@admin.register(ProductUseLog)
class ProductUseLogAdmin(admin.ModelAdmin):
    inlines = (ProductUseLogImageInline,)
    list_display = ("id", "product", "user", "review", "title", "body_excerpt",
                    "has_image", "is_approved", "is_deleted", "created_at",
                    "updated_at")
    list_display_links = ("id", "product")
    list_editable = ("is_approved",)
    list_filter = ("is_approved", "is_deleted", "created_at")
    search_fields = ("product__name", "user__email", "user__nickname",
                     "title", "body")
    autocomplete_fields = ("product", "user", "review")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    actions = ("approve_selected", "unapprove_selected")

    @admin.action(description="選択した使用記録を承認する")
    def approve_selected(self, request, queryset):
        # 使用記録はミッション集計対象外のためシグナル発火は不要（update でよい）。
        n = queryset.update(is_approved=True)
        self.message_user(request, f"{n}件を承認しました")

    @admin.action(description="選択した使用記録を非承認にする")
    def unapprove_selected(self, request, queryset):
        n = queryset.update(is_approved=False)
        self.message_user(request, f"{n}件を非承認にしました")

    def get_queryset(self, request):
        # 運営は削除済みを含む全件を確認できる（既定マネージャは削除済みを隠すため）。
        return ProductUseLog.all_objects.get_queryset()

    @admin.display(description="本文")
    def body_excerpt(self, obj):
        return (obj.body[:40] + "…") if len(obj.body) > 40 else obj.body

    @admin.display(description="画像", boolean=True)
    def has_image(self, obj):
        return obj.images.exists()


@admin.register(ProductUseLogImage)
class ProductUseLogImageAdmin(admin.ModelAdmin):
    list_display = ("id", "use_log", "order", "created_at")
    search_fields = ("use_log__product__name",)
    readonly_fields = ("created_at",)
    list_per_page = 50


@admin.register(ProductUseLogReport)
class ProductUseLogReportAdmin(admin.ModelAdmin):
    """使用記録通報の確認・対応用。自動削除/非表示はしない（運営が内容を見て判断する）。"""

    list_display = ("id", "use_log", "reporter", "reason", "status",
                    "created_at", "resolved_at", "resolved_by")
    list_display_links = ("id", "use_log")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("reporter__email", "use_log__body", "comment")
    autocomplete_fields = ("resolved_by",)
    readonly_fields = ("use_log", "reporter", "reason", "comment",
                       "created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        ("通報内容（読み取り専用）", {
            "fields": ("use_log", "reporter", "reason", "comment", "created_at"),
        }),
        ("対応（運営が編集）", {
            "fields": ("status", "admin_note", "resolved_by", "resolved_at"),
        }),
        ("更新日時", {"fields": ("updated_at",), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        if obj.status == ReportStatus.RESOLVED:
            if obj.resolved_at is None:
                obj.resolved_at = timezone.now()
            if obj.resolved_by is None:
                obj.resolved_by = request.user
        else:
            obj.resolved_at = None
        super().save_model(request, obj, form, change)
