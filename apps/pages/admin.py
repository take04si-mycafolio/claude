from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("status_badge", "received", "subject_truncated", "from_who",
                    "email_link", "preview")
    list_display_links = ("subject_truncated",)
    list_filter = ("is_read", "is_replied", "created_at")
    search_fields = ("name", "email", "subject", "body", "admin_notes")
    date_hierarchy = "created_at"
    list_per_page = 50
    readonly_fields = ("created_at", "ip", "user_agent",
                       "name", "email", "subject", "body_display")
    actions = ("mark_as_read", "mark_as_replied", "mark_as_unread", "mark_as_unreplied")

    fieldsets = (
        ("📩 受信内容", {"fields": ("name", "email", "subject", "body_display")}),
        ("📋 ステータス", {"fields": ("is_read", "is_replied", "replied_at", "admin_notes")}),
        ("🔍 メタ情報", {"fields": ("created_at", "ip", "user_agent"), "classes": ("collapse",)}),
    )

    @admin.display(description="状態")
    def status_badge(self, obj):
        if obj.is_replied:
            return format_html('<span style="background:#ECFDF5;color:#047857;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">返信済</span>')
        if obj.is_read:
            return format_html('<span style="background:#EFF6FF;color:#1D4ED8;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">既読</span>')
        return format_html('<span style="background:#FEF2F2;color:#991B1B;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700">●未読</span>')

    @admin.display(description="受信", ordering="-created_at")
    def received(self, obj):
        return obj.created_at.strftime("%m/%d %H:%M")

    @admin.display(description="件名")
    def subject_truncated(self, obj):
        weight = "700" if not obj.is_read else "400"
        return format_html('<span style="font-weight:{}">{}</span>', weight,
                           obj.subject[:40] + "…" if len(obj.subject) > 40 else obj.subject)

    @admin.display(description="差出人")
    def from_who(self, obj):
        return obj.name or "(匿名)"

    @admin.display(description="メール")
    def email_link(self, obj):
        return format_html(
            '<a href="mailto:{}?subject=Re:%20{}" style="color:#C97B84">📧 {}</a>',
            obj.email, obj.subject, obj.email)

    @admin.display(description="本文プレビュー")
    def preview(self, obj):
        s = obj.body[:50].replace("\n", " ")
        return s + ("…" if len(obj.body) > 50 else "")

    @admin.display(description="お問い合わせ内容")
    def body_display(self, obj):
        return format_html(
            '<div style="background:#FBF6F4;border:1px solid #F2DEE0;border-radius:12px;padding:18px;'
            'white-space:pre-wrap;line-height:1.85;color:#3A2E33;font-size:14px">{}</div>'
            '<div style="margin-top:12px"><a href="mailto:{}?subject=Re:%20{}" '
            'style="display:inline-block;padding:10px 22px;background:#C97B84;color:#fff;'
            'border-radius:999px;text-decoration:none;font-weight:700;font-size:13px">'
            '📧 このアドレスに返信メールを書く</a></div>',
            obj.body, obj.email, obj.subject)

    @admin.action(description="✓ 既読にする")
    def mark_as_read(self, request, queryset):
        n = queryset.update(is_read=True)
        self.message_user(request, f"{n}件を既読にしました")

    @admin.action(description="✉ 返信済みにする")
    def mark_as_replied(self, request, queryset):
        n = queryset.update(is_replied=True, replied_at=timezone.now(), is_read=True)
        self.message_user(request, f"{n}件を返信済みにしました")

    @admin.action(description="○ 未読に戻す")
    def mark_as_unread(self, request, queryset):
        n = queryset.update(is_read=False)
        self.message_user(request, f"{n}件を未読に戻しました")

    @admin.action(description="○ 未返信に戻す")
    def mark_as_unreplied(self, request, queryset):
        n = queryset.update(is_replied=False, replied_at=None)
        self.message_user(request, f"{n}件を未返信に戻しました")

    def has_add_permission(self, request): return False

    def change_view(self, request, object_id, *args, **kwargs):
        # 詳細を開いたら自動既読
        ContactMessage.objects.filter(id=object_id, is_read=False).update(is_read=True)
        return super().change_view(request, object_id, *args, **kwargs)
