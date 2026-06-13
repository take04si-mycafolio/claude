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
        "総合評価",
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
    cospa = models.PositiveSmallIntegerField(
        "コスパ", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    control = models.PositiveSmallIntegerField(
        "操作性", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    safety = models.PositiveSmallIntegerField(
        "安全性", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    expression = models.PositiveSmallIntegerField(
        "表情", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    icon = models.PositiveSmallIntegerField(
        "アイコン番号", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    wp_comment_id = models.IntegerField(
        "WPコメントID", null=True, blank=True, unique=True,
        help_text="WordPressからの取り込み元ID",
    )
    is_approved = models.BooleanField(
        "承認済み", default=True,
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


class ReviewImage(models.Model):
    MAX_PER_REVIEW = 4

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="口コミ",
    )
    image = models.ImageField("画像", upload_to="reviews/%Y/%m/")
    order = models.PositiveSmallIntegerField("表示順", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "口コミ画像"
        verbose_name_plural = "口コミ画像"
        ordering = ["order", "id"]

    def __str__(self):
        return f"review#{self.review_id} image#{self.pk}"

    def save(self, *args, **kwargs):
        # 新規アップロード時のみ圧縮する（保存済みの再保存では再圧縮しない）
        if self.pk is None and self.image and hasattr(self.image, "file"):
            from .imaging import compress_image
            self.image = compress_image(self.image)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # DBレコード削除時に実ファイルも削除する
        self.image.delete(save=False)
        super().delete(*args, **kwargs)


class ReviewHelpful(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_helpfuls",
        verbose_name="ユーザー",
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="helpfuls",
        verbose_name="口コミ",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "review")]
        ordering = ["-created_at"]
        verbose_name = "参考になった"
        verbose_name_plural = "参考になった"

    def __str__(self):
        return f"{self.user} 👍 review#{self.review_id}"
