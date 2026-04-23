from django.contrib import admin
from django.utils.html import format_html

from .models import Article, Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("indent_name", "parent", "sort_order", "product_count")
    list_filter = ("parent",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("sort_order",)

    @admin.display(description="カテゴリ名")
    def indent_name(self, obj):
        return ("└ " if obj.parent_id else "") + obj.name

    @admin.display(description="商品数")
    def product_count(self, obj):
        if obj.parent_id is None:
            return obj.products_of_type.count()
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "price",
        "is_published",
        "review_count",
        "thumb",
        "updated_at",
    )
    search_fields = ("name", "brand", "description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "brand", "product_type", "categories", "is_published", "sort_order")}),
        ("価格・リンク", {
            "fields": ("price", "official_url", "affiliate_url", "rakuten_url", "amazon_url")
        }),
        ("画像", {"fields": ("image", "image_url")}),
        ("説明", {"fields": ("description", "features")}),
        ("メタ", {"fields": ("wp_post_id", "created_at", "updated_at")}),
    )
    list_filter = ("is_published", "product_type", "brand", "categories")
    readonly_fields = ("created_at", "updated_at", "wp_post_id")

    @admin.display(description="口コミ数")
    def review_count(self, obj):
        return obj.reviews.count()

    @admin.display(description="画像")
    def thumb(self, obj):
        url = obj.display_image
        if url:
            return format_html(
                '<img src="{}" style="height:40px;object-fit:contain" />', url
            )
        return "-"


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "wp_post_id", "published_at", "is_published")
    list_filter = ("is_published", "published_at")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("related_products",)
    readonly_fields = ("created_at", "updated_at", "wp_post_id", "wp_author")
