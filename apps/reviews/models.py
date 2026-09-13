from django.conf import settings
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone

from apps.accounts.models import SkinType


class ReviewManager(models.Manager):
    """既定マネージャ。論理削除済み(is_deleted=True)を全クエリから自動除外する。

    これにより表示・集計・API・逆参照(user.reviews / product.reviews)のいずれも、
    削除済み口コミを「存在しないもの」として扱う。運営だけが見られるよう、
    削除済みを含む生クエリは all_objects(下の Review.all_objects) を使う。
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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
    # メディアサイト方針(2026-09-06): 会員登録なしのゲスト投稿を許可するため null 可。
    # ゲスト投稿は user=None + guest_name。承認制・薬機法ゲートは会員投稿と同一。
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="投稿者",
        null=True, blank=True,
    )
    guest_name = models.CharField(
        "ゲスト表示名", max_length=40, blank=True, default="",
        help_text="非会員投稿の表示名。空なら「匿名」表示",
    )
    ip_hash = models.CharField(
        "投稿元IPハッシュ", max_length=64, blank=True, default="", db_index=True,
        help_text="非会員投稿のレート制限用(SHA-256・生IPは保存しない)",
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
        "承認済み", default=False,
        help_text="新規投稿は承認待ち(False)で作成し、運営が内容確認後に承認して掲載する。",
    )
    is_rejected = models.BooleanField(
        "非承認(掲載しない)", default=False, db_index=True,
        help_text="運営判断で掲載しない口コミ(薬機法等)。承認センターの承認待ちから外れる。"
                  "削除とは別で、ここを外せば承認待ちに戻る。",
    )
    # ===== 論理削除（運営のみ閲覧可・キャンペーン不正対策） =====
    is_deleted = models.BooleanField(
        "削除済み", default=False, db_index=True,
        help_text="会員が削除した口コミ。サイト表示・集計からは除外し、運営のみ閲覧可。",
    )
    deleted_at = models.DateTimeField("削除日時", null=True, blank=True)
    delete_count = models.PositiveSmallIntegerField(
        "削除回数", default=0,
        help_text="この口コミが削除→再投稿された回数。0より大きいと再投稿の常習を確認できる。",
    )
    # ===== キャンペーン消費（一度カウントされた口コミは次回以降カウントしない） =====
    campaign_consumed_at = models.DateTimeField(
        "キャンペーン算入日時", null=True, blank=True,
        help_text="達成したキャンペーンの集計に算入された日時。以後は別キャンペーンの"
                  "集計対象にせず、会員からの削除も不可にする。",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReviewManager()
    all_objects = models.Manager()  # 削除済みを含む全件（運営/内部処理用）

    class Meta:
        verbose_name = "口コミ"
        verbose_name_plural = "口コミ"
        ordering = ["-created_at"]
        # CASCADE等の内部処理・逆参照削除が削除済み行も辿れるよう、base_managerは全件。
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"], name="unique_review_per_product_user"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.title} ({self.rating}★)"

    @property
    def display_name(self):
        """表示名。会員=ニックネーム / ゲスト=guest_name / どちらも無ければ匿名。"""
        if self.user_id and getattr(self.user, "nickname", ""):
            return self.user.nickname
        return self.guest_name or "匿名"

    @property
    def is_campaign_consumed(self) -> bool:
        return self.campaign_consumed_at is not None

    def soft_delete(self):
        """会員操作による論理削除。実行行・実ファイルは残し、表示/集計からのみ除外する。

        キャンペーンに算入済み(is_campaign_consumed)の口コミは呼び出し側で弾く想定だが、
        二重防御としてここでも拒否する。
        """
        if self.is_campaign_consumed:
            raise PermissionError("campaign-consumed review cannot be deleted")
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.delete_count = (self.delete_count or 0) + 1
        self.save(update_fields=["is_deleted", "deleted_at", "delete_count", "updated_at"])

    def delete(self, *args, **kwargs):
        # 物理削除（admin/内部用）。FKのCASCADEだけだとReviewImageの行は消えても
        # 実ファイルが残るため、先に各画像を .delete() して実ファイルごと確実に削除する。
        for img in self.images.all():
            img.delete()
        return super().delete(*args, **kwargs)


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


class ReportReason(models.TextChoices):
    INAPPROPRIATE = "inappropriate", "不適切な内容"
    FALSE_INFO = "false_info", "虚偽・誇張された内容"
    HARASSMENT = "harassment", "誹謗中傷・嫌がらせ"
    PERSONAL_INFO = "personal_info", "個人情報が含まれている"
    RIGHTS_VIOLATION = "rights_violation", "著作権・肖像権などの権利侵害"
    STEALTH_MARKETING = "stealth_marketing", "広告・ステマの疑い"
    UNRELATED = "unrelated", "商品と関係がない"
    OTHER = "other", "その他"


class ReportStatus(models.TextChoices):
    PENDING = "pending", "未対応"
    REVIEWING = "reviewing", "確認中"
    RESOLVED = "resolved", "対応済み"
    REJECTED = "rejected", "却下"


class ReviewReport(models.Model):
    """口コミ通報。ユーザーが口コミをガイドライン違反等として運営へ通報する。

    重要: 通報されても自動で削除・非表示にはしない。運営が管理画面で確認するための
    受付レコードのみを作る。1ユーザーが同じ口コミを重複通報できないよう UniqueConstraint
    を設ける。自分の口コミの通報・匿名通報は view / serializer 側で禁止する。
    """

    COMMENT_MAX_LEN = 1000

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="対象口コミ",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_reports",
        verbose_name="通報者",
    )
    reason = models.CharField(
        "通報理由", max_length=32, choices=ReportReason.choices
    )
    comment = models.TextField(
        "詳細コメント", blank=True,
        validators=[MaxLengthValidator(COMMENT_MAX_LEN)],
        help_text=f"任意。最大{COMMENT_MAX_LEN}文字。",
    )
    status = models.CharField(
        "対応ステータス", max_length=16,
        choices=ReportStatus.choices, default=ReportStatus.PENDING,
    )
    admin_note = models.TextField("運営メモ", blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    resolved_at = models.DateTimeField("対応日時", null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="resolved_review_reports",
        verbose_name="対応した管理者",
    )

    class Meta:
        verbose_name = "口コミ通報"
        verbose_name_plural = "口コミ通報"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["review", "reporter"],
                name="unique_report_per_review_reporter",
            )
        ]


# ======================================================================
# 使用記録（ProductUseLog）— 通常口コミとは別の「使い続けた経過メモ」。
# 1ユーザー1商品に複数件OK・星評価なし・平均評価/ランキング/review_count/
# helpful_count には一切含めない（FK の related_name を "reviews" と分けることで
# 既存の集計クエリ(reviews__rating 等)から構造的に隔離する）。
# ======================================================================
class UseLogManager(models.Manager):
    """既定マネージャ。論理削除済み(is_deleted=True)を全クエリから自動除外する。

    既存口コミ(Review)の削除方式（論理削除）に合わせる。運営は all_objects を使う。
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class ProductUseLog(models.Model):
    """使用記録。商品を使い続けた感想・経過メモ。

    通常口コミ(Review)との違い:
    - 1ユーザー1商品に複数件投稿できる（ユニーク制約なし）。
    - 星評価(rating)を持たない。平均評価・ランキング・review_count・helpful_count に
      含めない（related_name="use_logs" で既存集計から隔離）。
    - review は任意。既に通常口コミを書いていれば、その経過記録として紐付けられる。
    """

    BODY_MAX_LEN = 5000

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="use_logs",
        verbose_name="商品",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="use_logs",
        verbose_name="投稿者",
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="use_logs",
        verbose_name="紐付け口コミ",
        help_text="任意。同じ商品・同じ投稿者の通常口コミにのみ紐付けられる。",
    )
    title = models.CharField(
        "タイトル", max_length=120, blank=True,
        help_text="任意。一覧で見出しとして表示する。",
    )
    body = models.TextField(
        "本文", validators=[MaxLengthValidator(BODY_MAX_LEN)],
    )
    # 口コミ(Review)と同じ承認制。投稿時は承認待ちで、運営承認後に掲載される。
    is_approved = models.BooleanField(
        "承認済み", default=False, db_index=True,
        help_text="承認すると商品ページ・APIに掲載されます。未承認は投稿者本人と"
                  "運営のみ閲覧可（本人には「承認待ち」と表示）。",
    )
    # 削除方式は既存口コミ(Review)に合わせて論理削除にする。
    is_deleted = models.BooleanField(
        "削除済み", default=False, db_index=True,
        help_text="投稿者が削除した使用記録。表示からは除外し、運営のみ閲覧可。",
    )
    deleted_at = models.DateTimeField("削除日時", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UseLogManager()
    all_objects = models.Manager()  # 削除済みを含む全件（運営/内部処理用）

    class Meta:
        verbose_name = "使用記録"
        verbose_name_plural = "使用記録"
        ordering = ["-created_at"]
        base_manager_name = "all_objects"

    def __str__(self):
        return f"{self.product.name} - 使用記録#{self.pk}"

    def soft_delete(self):
        """投稿者操作による論理削除。行・実ファイルは残し表示からのみ除外する。"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def delete(self, *args, **kwargs):
        # 物理削除（admin/内部用）。画像の実ファイルも確実に消す。
        for img in self.images.all():
            img.delete()
        return super().delete(*args, **kwargs)


class ProductUseLogImage(models.Model):
    MAX_PER_LOG = ReviewImage.MAX_PER_REVIEW  # 既存口コミ画像に合わせる（4枚）

    use_log = models.ForeignKey(
        ProductUseLog,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="使用記録",
    )
    image = models.ImageField("画像", upload_to="use_logs/%Y/%m/")
    order = models.PositiveSmallIntegerField("表示順", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "使用記録画像"
        verbose_name_plural = "使用記録画像"
        ordering = ["order", "id"]

    def __str__(self):
        return f"use_log#{self.use_log_id} image#{self.pk}"

    def save(self, *args, **kwargs):
        # 新規アップロード時のみ圧縮（既存口コミ画像と同一の compress_image）。
        if self.pk is None and self.image and hasattr(self.image, "file"):
            from .imaging import compress_image
            self.image = compress_image(self.image)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.image.delete(save=False)
        super().delete(*args, **kwargs)


class ProductUseLogReport(models.Model):
    """使用記録の通報。通報理由・ステータスは既存の口コミ通報と同じ choices を使う。

    通報されても自動削除・非表示はしない（運営が確認する受付レコードのみ）。
    1ユーザーが同じ使用記録を重複通報できないよう UniqueConstraint を設ける。
    """

    COMMENT_MAX_LEN = 1000

    use_log = models.ForeignKey(
        ProductUseLog,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="対象使用記録",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="use_log_reports",
        verbose_name="通報者",
    )
    reason = models.CharField(
        "通報理由", max_length=32, choices=ReportReason.choices
    )
    comment = models.TextField(
        "詳細コメント", blank=True,
        validators=[MaxLengthValidator(COMMENT_MAX_LEN)],
        help_text=f"任意。最大{COMMENT_MAX_LEN}文字。",
    )
    status = models.CharField(
        "対応ステータス", max_length=16,
        choices=ReportStatus.choices, default=ReportStatus.PENDING,
    )
    admin_note = models.TextField("運営メモ", blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    resolved_at = models.DateTimeField("対応日時", null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="resolved_use_log_reports",
        verbose_name="対応した管理者",
    )

    class Meta:
        verbose_name = "使用記録通報"
        verbose_name_plural = "使用記録通報"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["use_log", "reporter"],
                name="unique_report_per_uselog_reporter",
            )
        ]

    def __str__(self):
        return f"report#{self.pk} use_log#{self.use_log_id}"

    def __str__(self):
        return f"report#{self.pk} review#{self.review_id} ({self.get_status_display()})"


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
