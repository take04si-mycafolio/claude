from django.contrib import admin
from django.utils.html import format_html
from .models import AccessLog


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ("created_at_jst", "status_badge", "method", "url_short",
                    "user", "ip", "bot_label", "referer_short")
    list_filter = ("status_code", "method", "is_bot", "created_at")
    search_fields = ("url", "ip", "user_agent", "referer", "user__email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "url", "method", "status_code", "ip",
                       "user_agent", "referer", "user", "is_bot")
    list_per_page = 100
    actions = ("delete_old_logs",)

    @admin.display(description="日時", ordering="-created_at")
    def created_at_jst(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")

    @admin.display(description="ステータス", ordering="status_code")
    def status_badge(self, obj):
        c = obj.status_code or 0
        if 200 <= c < 300:
            color, bg = "#047857", "#ECFDF5"
        elif 300 <= c < 400:
            color, bg = "#1D4ED8", "#EFF6FF"
        elif c == 404:
            color, bg = "#B45309", "#FFFBEB"
        elif 400 <= c < 500:
            color, bg = "#991B1B", "#FEF2F2"
        elif 500 <= c:
            color, bg = "#FFFFFF", "#991B1B"
        else:
            color, bg = "#666", "#EEE"
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700">{}</span>',
            bg, color, c)

    @admin.display(description="URL")
    def url_short(self, obj):
        return obj.url if len(obj.url) <= 60 else obj.url[:60] + "…"

    @admin.display(description="リファラ")
    def referer_short(self, obj):
        return obj.referer[:40] + "…" if len(obj.referer) > 40 else (obj.referer or "-")

    @admin.display(description="Bot")
    def bot_label(self, obj):
        if obj.is_bot:
            return format_html(
                '<span style="background:#FEF2F2;color:#991B1B;padding:2px 8px;border-radius:8px;font-size:11px">BOT</span>')
        return ""

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

    @admin.action(description="30日以上前のログを削除")
    def delete_old_logs(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        n = AccessLog.objects.filter(created_at__lt=cutoff).delete()[0]
        self.message_user(request, f"{n}件削除しました")
