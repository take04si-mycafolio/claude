from django.db import models


class ContactMessage(models.Model):
    name = models.CharField("お名前", max_length=100, blank=True)
    email = models.EmailField("メールアドレス")
    subject = models.CharField("件名", max_length=200)
    body = models.TextField("お問い合わせ内容")
    is_read = models.BooleanField("既読", default=False, db_index=True)
    is_replied = models.BooleanField("返信済み", default=False, db_index=True)
    admin_notes = models.TextField("管理メモ", blank=True, help_text="ユーザーには見えない管理用メモ")
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=500, blank=True)
    created_at = models.DateTimeField("受信日時", auto_now_add=True, db_index=True)
    replied_at = models.DateTimeField("返信日時", null=True, blank=True)

    class Meta:
        verbose_name = "お問い合わせ"
        verbose_name_plural = "お問い合わせ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.subject} - {self.email}"
