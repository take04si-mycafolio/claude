from django.conf import settings
from django.db import models


class AccessLog(models.Model):
    url = models.CharField("URL", max_length=500, db_index=True)
    method = models.CharField("メソッド", max_length=10, default="GET")
    status_code = models.PositiveSmallIntegerField("ステータスコード", null=True, db_index=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=500, blank=True)
    referer = models.CharField("リファラ", max_length=500, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="ユーザー",
    )
    is_bot = models.BooleanField("Bot判定", default=False, db_index=True)
    created_at = models.DateTimeField("日時", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "アクセスログ"
        verbose_name_plural = "アクセスログ"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at", "url"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.method} {self.url}"
