from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Bookmark,
    Device,
    Mission,
    MissionRewardCode,
    MissionStep,
    User,
    UserMissionCompletion,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "nickname", "age_range", "skin_type", "gender",
                    "is_staff", "email_verified", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser", "email_verified",
                   "gender", "age_range", "skin_type")
    search_fields = ("email", "username", "nickname", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login", "created_at")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("プロフィール", {"fields": ("nickname", "icon_number", "bio",
                                "age_range", "skin_type", "gender")}),
        ("SNS", {"fields": ("twitter", "instagram", "tiktok",
                            "youtube_url", "website_url")}),
        ("権限", {"fields": ("is_active", "is_staff", "is_superuser",
                          "email_verified", "groups", "user_permissions")}),
        ("日時", {"fields": ("date_joined", "last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "username", "password1", "password2")}),
    )


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__nickname", "product__name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user", "product")
    list_per_page = 50


class MissionStepInline(admin.StackedInline):
    """ミッションの達成ステップをミッション編集画面から直接管理。"""
    model = MissionStep
    extra = 1
    fields = ("action_type", "target_count", "label", "order")


class MissionRewardCodeInline(admin.TabularInline):
    """個別シリアルコードのプール。配布方式=個別のときに登録。"""
    model = MissionRewardCode
    extra = 0
    fields = ("code", "assigned_to", "assigned_at")
    readonly_fields = ("assigned_to", "assigned_at")
    autocomplete_fields = ()


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("title", "reward_label", "code_mode", "limit_display",
                    "level_range_display", "starts_at", "ends_at",
                    "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("is_active", "code_mode", "min_review_level",
                   "max_review_level")
    search_fields = ("title", "reward_label")
    readonly_fields = ("created_at", "slots_display")
    inlines = (MissionStepInline, MissionRewardCodeInline)
    save_on_top = True
    fieldsets = (
        (None, {"fields": ("title", "description", "is_active", "order")}),
        ("開催期間", {"fields": (("starts_at", "ends_at"),)}),
        ("参加条件", {"fields": (("min_review_level", "max_review_level"),)}),
        ("プレゼント設定", {"fields": ("reward_label", "code_mode",
                                 "shared_code", "reward_limit",
                                 "slots_display")}),
        ("日時", {"fields": ("created_at",)}),
    )

    @admin.display(description="参加ランク")
    def level_range_display(self, obj):
        return obj.level_condition_label()

    @admin.display(description="配布状況")
    def slots_display(self, obj):
        if obj.pk is None:
            return "-"
        used = obj.slots_used()
        if obj.reward_limit is None:
            return f"{used}名に配布済み（無制限）"
        remaining = obj.slots_remaining()
        state = "受付終了" if remaining == 0 else f"残り{remaining}"
        return f"{used} / {obj.reward_limit}名（{state}）"

    @admin.display(description="配布上限")
    def limit_display(self, obj):
        return obj.reward_limit if obj.reward_limit is not None else "無制限"


@admin.register(UserMissionCompletion)
class UserMissionCompletionAdmin(admin.ModelAdmin):
    """達成記録(自動生成)の監査用ビュー。"""
    list_display = ("user", "mission", "status", "assigned_code", "completed_at")
    list_filter = ("status", "mission", "completed_at")
    search_fields = ("user__email", "user__nickname", "assigned_code")
    autocomplete_fields = ("user", "mission")
    readonly_fields = ("user", "mission", "status", "assigned_code",
                       "completed_at", "seen_at")
    list_per_page = 50

    def has_add_permission(self, request):
        return False


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """通知先端末(API自動登録)の監査用ビュー。"""
    list_display = ("user", "platform", "is_active", "app_version",
                    "device_name", "last_seen_at", "created_at")
    list_filter = ("platform", "is_active", "created_at")
    search_fields = ("user__email", "user__nickname", "device_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("last_seen_at", "created_at", "updated_at")
    list_per_page = 50
