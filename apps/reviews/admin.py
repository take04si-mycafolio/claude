from django.contrib import admin
from django.utils.html import format_html

from .models import Review, ReviewHelpful, ReviewImage


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
                    "helpful_count", "created_at")
    list_display_links = ("product", "title")
    list_filter = ("is_approved", "rating", "skin_type", "effectiveness",
                   "usage_period", "created_at")
    search_fields = ("product__name", "user__email", "user__nickname",
                     "title", "body")
    autocomplete_fields = ("product", "user")
    list_editable = ("is_approved",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50
    save_on_top = True
    actions = ("approve_selected", "unapprove_selected")

    fieldsets = (
        ("対象", {"fields": ("product", "user", "is_approved")}),
        ("総合評価", {"fields": ("rating", "title", "body")}),
        ("詳細評価", {"fields": ("cospa", "control", "safety", "expression", "icon")}),
        ("投稿者属性", {"fields": ("skin_type", "usage_period", "effectiveness")}),
        ("WP移行情報", {"fields": ("wp_comment_id",), "classes": ("collapse",)}),
        ("日時", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="参考になった", ordering="helpfuls__count")
    def helpful_count(self, obj):
        return obj.helpfuls.count()

    @admin.action(description="選択した口コミを承認する")
    def approve_selected(self, request, queryset):
        n = queryset.update(is_approved=True)
        self.message_user(request, f"{n}件を承認しました")

    @admin.action(description="選択した口コミを非承認にする")
    def unapprove_selected(self, request, queryset):
        n = queryset.update(is_approved=False)
        self.message_user(request, f"{n}件を非承認にしました")


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
