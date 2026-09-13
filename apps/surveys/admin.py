from django.contrib import admin

from .models import SurveyResponse


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = (
        "id", "survey_slug", "answers_summary",
        "short_reason", "is_approved", "is_deleted", "created_at",
    )
    list_filter = ("survey_slug", "is_approved", "is_deleted")
    search_fields = ("reason",)
    list_editable = ("is_approved", "is_deleted")
    actions = ("approve_comments", "hide_responses")

    @admin.display(description="回答")
    def answers_summary(self, obj):
        if not obj.answers:
            return "-"
        return ", ".join(f"{k}={v}" for k, v in obj.answers.items())

    @admin.display(description="理由・感想")
    def short_reason(self, obj):
        text = obj.reason or ""
        return (text[:40] + "…") if len(text) > 40 else text

    @admin.action(description="選択したコメントを公開承認する")
    def approve_comments(self, request, queryset):
        n = queryset.update(is_approved=True)
        self.message_user(request, f"{n}件を承認しました。")

    @admin.action(description="選択した回答を集計から除外する")
    def hide_responses(self, request, queryset):
        n = queryset.update(is_deleted=True)
        self.message_user(request, f"{n}件を集計から除外しました。")
