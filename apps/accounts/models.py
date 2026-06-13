from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class AgeRange(models.TextChoices):
    TEENS = "10s", "10代"
    TWENTIES = "20s", "20代"
    THIRTIES = "30s", "30代"
    FORTIES = "40s", "40代"
    FIFTIES = "50s", "50代"
    SIXTIES_PLUS = "60s+", "60代以上"


class SkinType(models.TextChoices):
    DRY = "dry", "乾燥肌"
    OILY = "oily", "脂性肌"
    COMBINATION = "combination", "混合肌"
    SENSITIVE = "sensitive", "敏感肌"
    NORMAL = "normal", "普通肌"


class Gender(models.TextChoices):
    FEMALE = "female", "女性"
    MALE = "male", "男性"
    OTHER = "other", "その他"


class User(AbstractUser):
    email = models.EmailField("メールアドレス", unique=True)
    nickname = models.CharField("ニックネーム", max_length=50, blank=True)
    age_range = models.CharField(
        "年代", max_length=8, choices=AgeRange.choices, blank=True
    )
    skin_type = models.CharField(
        "肌質", max_length=16, choices=SkinType.choices, blank=True
    )
    gender = models.CharField(
        "性別", max_length=8, choices=Gender.choices, blank=True
    )
    avatar = models.ImageField(
        "プロフィールアイコン",
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text="未設定のときは下のプリセットアイコンが表示されます",
    )
    icon_number = models.PositiveSmallIntegerField(
        "アバター番号", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1〜10から選択",
    )
    bio = models.TextField("自己紹介", max_length=300, blank=True)
    twitter = models.CharField("X (Twitter)", max_length=15, blank=True,
                               help_text="@は不要")
    instagram = models.CharField("Instagram", max_length=30, blank=True,
                                 help_text="@は不要")
    tiktok = models.CharField("TikTok", max_length=24, blank=True,
                              help_text="@は不要")
    youtube_url = models.URLField("YouTube URL", blank=True)
    website_url = models.URLField("Webサイト", blank=True)
    email_verified = models.BooleanField("メール認証済み", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    # ===== Thank You Culture =====
    @cached_property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()

    @cached_property
    def helpful_count(self):
        from apps.reviews.models import ReviewHelpful
        return ReviewHelpful.objects.filter(
            review__user=self, review__is_approved=True
        ).count()

    @cached_property
    def review_level(self):
        score = self.review_count * 5 + self.helpful_count
        thresholds = [
            (1000, 10), (600, 9), (400, 8), (200, 7),
            (100, 6),  (50, 5),  (25, 4), (10, 3), (3, 2),
        ]
        for t, lv in thresholds:
            if score >= t:
                return lv
        return 1

    @cached_property
    def category_badge(self):
        from django.db.models import Count
        top = (
            self.reviews.filter(is_approved=True)
            .values("product__product_type__name")
            .annotate(c=Count("id"))
            .order_by("-c")
            .first()
        )
        if top and top["c"] >= 3 and top["product__product_type__name"]:
            return f"{top['product__product_type__name']}マスター"
        return None

    def __str__(self):
        return self.nickname or self.email

    @property
    def has_written_review(self):
        return self.reviews.exists()


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name="ユーザー",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="bookmarked_by",
        verbose_name="気になる商品",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "気になる"
        verbose_name_plural = "気になる"
        unique_together = [("user", "product")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ♡ {self.product}"


# ===== ミッション機能 =====
class ActionType(models.TextChoices):
    """ミッションのステップが対象にするサイト内行動。"""
    REVIEW = "review", "口コミを投稿する"
    REVIEW_WITH_PHOTO = "review_with_photo", "写真付きで口コミを投稿する"
    HELPFUL = "helpful", "「参考になった」を獲得する"
    BOOKMARK = "bookmark", "「気になる」に登録する"
    EMAIL_VERIFIED = "email_verified", "メールアドレスを認証する"
    PROFILE_COMPLETE = "profile_complete", "プロフィールを完成させる"
    SNS_TWITTER = "sns_twitter", "X(Twitter)アカウントを連携する"
    SNS_INSTAGRAM = "sns_instagram", "Instagramアカウントを連携する"
    SNS_TIKTOK = "sns_tiktok", "TikTokアカウントを連携する"
    SNS_YOUTUBE = "sns_youtube", "YouTubeチャンネルを連携する"


class CodeMode(models.TextChoices):
    SHARED = "shared", "全員共通コード"
    UNIQUE = "unique", "個別シリアルコード(プール)"


class CompletionStatus(models.TextChoices):
    AWARDED = "awarded", "プレゼント獲得"
    PENDING = "pending", "コード準備中"
    SOLD_OUT = "sold_out", "定員終了(対象外)"


class Mission(models.Model):
    title = models.CharField("ミッション名", max_length=80)
    description = models.TextField("説明", blank=True)
    reward_label = models.CharField(
        "プレゼント内容", max_length=120,
        help_text="例: 全品10%OFFクーポン / サンプルプレゼント引換券",
    )
    code_mode = models.CharField(
        "コード配布方式", max_length=8, choices=CodeMode.choices,
        default=CodeMode.SHARED,
    )
    shared_code = models.CharField(
        "共通コード", max_length=60, blank=True,
        help_text="配布方式が「全員共通コード」のとき、達成者全員に表示するコード",
    )
    reward_limit = models.PositiveIntegerField(
        "配布上限(先着・数量限定)", null=True, blank=True,
        help_text="プレゼントを渡せる人数の上限。空欄で無制限。"
                  "上限に達した後の達成者は対象外（受付終了）になります。",
    )
    min_review_level = models.PositiveSmallIntegerField(
        "参加可能レビューランク(下限)", default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="このレビューランク(Lv.)以上の会員が参加できます。1で下限なし。",
    )
    max_review_level = models.PositiveSmallIntegerField(
        "参加可能レビューランク(上限)", default=10,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="このレビューランク(Lv.)以下の会員が参加できます。10で上限なし。"
                  "下限と上限を同じ値にすると、その Lv. の会員だけが対象になります"
                  "（例: 下限1・上限1で Lv.1 限定キャンペーン）。",
    )
    starts_at = models.DateTimeField(
        "開始日時", null=True, blank=True,
        help_text="この日時以降の口コミ・参考になった・気になるの実績だけを"
                  "カウントします。空欄で全期間（常設ミッション）。",
    )
    ends_at = models.DateTimeField(
        "終了日時", null=True, blank=True,
        help_text="この日時を過ぎると新規の達成受付を終了します（既存の獲得は保持）。"
                  "空欄で無期限。",
    )
    is_active = models.BooleanField("公開中", default=True)
    order = models.PositiveSmallIntegerField("表示順", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ミッション"
        verbose_name_plural = "ミッション"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.min_review_level > self.max_review_level:
            raise ValidationError({
                "max_review_level": "上限は下限以上の値にしてください。",
            })
        if self.starts_at and self.ends_at and self.starts_at > self.ends_at:
            raise ValidationError({
                "ends_at": "終了日時は開始日時より後にしてください。",
            })

    def has_started(self, now=None) -> bool:
        """開始済みか（starts_at 未設定なら常に開始済み）。"""
        if self.starts_at is None:
            return True
        return (now or timezone.now()) >= self.starts_at

    def has_ended(self, now=None) -> bool:
        """終了済みか（ends_at 未設定なら無期限）。"""
        if self.ends_at is None:
            return False
        return (now or timezone.now()) > self.ends_at

    def is_open(self, now=None) -> bool:
        """新規の達成を受け付けられる期間内か。"""
        now = now or timezone.now()
        return self.has_started(now) and not self.has_ended(now)

    def level_eligible(self, level: int) -> bool:
        """指定レビューランクが参加条件（下限〜上限）を満たすか。"""
        return self.min_review_level <= level <= self.max_review_level

    def level_condition_label(self) -> str:
        """参加条件のレビューランクを人間向けに表現する。"""
        lo, hi = self.min_review_level, self.max_review_level
        if lo <= 1 and hi >= 10:
            return "全員参加可"
        if lo == hi:
            return f"Lv.{lo} 限定"
        if hi >= 10:
            return f"Lv.{lo} 以上"
        if lo <= 1:
            return f"Lv.{hi} 以下"
        return f"Lv.{lo}〜{hi}"

    def slots_used(self):
        """プレゼント対象として確保済みの人数（獲得＋準備中、定員終了は除く）。"""
        return self.completions.exclude(
            status=CompletionStatus.SOLD_OUT
        ).count()

    def slots_remaining(self):
        """残り配布可能数。無制限なら None。"""
        if self.reward_limit is None:
            return None
        return max(0, self.reward_limit - self.slots_used())

    def is_sold_out(self):
        return self.reward_limit is not None and self.slots_used() >= self.reward_limit


class MissionStep(models.Model):
    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name="steps",
        verbose_name="ミッション",
    )
    action_type = models.CharField(
        "アクション", max_length=24, choices=ActionType.choices,
    )
    target_count = models.PositiveSmallIntegerField(
        "目標回数", default=1,
        validators=[MinValueValidator(1)],
        help_text="この回数だけ達成すると、このステップはクリア",
    )
    label = models.CharField(
        "表示ラベル", max_length=80, blank=True,
        help_text="未入力ならアクションの既定文言を使用",
    )
    order = models.PositiveSmallIntegerField("表示順", default=0)

    class Meta:
        verbose_name = "達成ステップ"
        verbose_name_plural = "達成ステップ"
        ordering = ["order", "id"]

    def display_label(self):
        if self.label:
            return self.label
        base = self.get_action_type_display()
        if self.target_count > 1:
            return f"{base}（{self.target_count}回）"
        return base

    def __str__(self):
        return f"{self.mission.title} / {self.display_label()}"


class MissionRewardCode(models.Model):
    """配布方式=個別シリアルコードのときのコードプール。"""
    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name="codes",
        verbose_name="ミッション",
    )
    code = models.CharField("コード", max_length=60)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_mission_codes",
        verbose_name="割当先",
    )
    assigned_at = models.DateTimeField("割当日時", null=True, blank=True)

    class Meta:
        verbose_name = "シリアルコード"
        verbose_name_plural = "シリアルコード"
        unique_together = [("mission", "code")]
        ordering = ["id"]

    def __str__(self):
        state = "使用済" if self.assigned_to_id else "未使用"
        return f"{self.code} ({state})"


class UserMissionCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="mission_completions", verbose_name="ユーザー",
    )
    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name="completions",
        verbose_name="ミッション",
    )
    assigned_code = models.CharField(
        "発行コード", max_length=60, blank=True,
        help_text="空の場合はコード準備中、または定員終了で対象外",
    )
    status = models.CharField(
        "状態", max_length=12, choices=CompletionStatus.choices,
        default=CompletionStatus.AWARDED,
    )
    completed_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(
        "お祝い表示済み日時", null=True, blank=True,
        help_text="達成ポップアップを会員に表示済みならその日時。空なら次回表示",
    )

    class Meta:
        verbose_name = "ミッション達成"
        verbose_name_plural = "ミッション達成"
        unique_together = [("user", "mission")]
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.user} ✓ {self.mission.title}"
