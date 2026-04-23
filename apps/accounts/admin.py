from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "nickname",
        "username",
        "age_range",
        "skin_type",
        "email_verified",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_staff", "is_superuser", "email_verified", "age_range", "skin_type")
    search_fields = ("email", "nickname", "username")
    ordering = ("-created_at",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "プロフィール",
            {"fields": ("nickname", "age_range", "skin_type", "email_verified")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "nickname",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
