from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import SkinType


class UsagePeriod(models.TextChoices):
    UNDER_1M = "lt1m", "1ヶ月未満"
    M1_3 = "1-3m", "1〜3ヶ月"
    M3_6 = "3-6m", "3〜6ヶ月"
    M6_12 = "6-12m", "6ヶ月〜1年"
    OVER_1Y = "gt1y", "1年以上"


class Effectiveness(models.TextChoices):
    EXCELLENT = "excellent", "とても効果を感じた"
    GOOD = "good", "効果を感じた"
    NEUTRAL = "neutral", "どちらとも言えない"
    POOR = "poor", "あまり感じなかった"
    NONE = "none", "効果を感じなかった"


class Review(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="美顔器",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="投稿者",
    )
    rating = models.PositiveSmallIntegerField(
        "星評価",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField("タイトル", max_length=120)
    body = models.TextField("本文")
    usage_period = models.CharField(
        "使用期間", max_length=8, choices=UsagePeriod.choices, blank=True
    )
    effectiveness = models.CharField(
        "効果実感", max_length=16, choices=Effectiveness.choices, blank=True
    )
    skin_type = models.CharField(
        "投稿時の肌質", max_length=16, choices=SkinType.choices, blank=True
    )
    is_approved = models.BooleanField(
        "承認済み",
        default=True,
        help_text="管理者が非表示にする場合はチェックを外してください",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "口コミ"
        verbose_name_plural = "口コミ"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"], name="unique_review_per_product_user"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.title} ({self.rating}★)"
