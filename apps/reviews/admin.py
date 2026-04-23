from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "user",
        "rating",
        "title",
        "is_approved",
        "created_at",
    )
    list_filter = ("is_approved", "rating", "effectiveness", "skin_type", "usage_period")
    search_fields = ("title", "body", "user__email", "user__nickname", "product__name")
    autocomplete_fields = ("product", "user")
    readonly_fields = ("created_at", "updated_at")
    actions = ["approve_reviews", "unapprove_reviews"]

    @admin.action(description="選択した口コミを承認")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="選択した口コミを非承認(非表示)")
    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
