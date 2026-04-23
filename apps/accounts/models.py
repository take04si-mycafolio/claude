from django.contrib.auth.models import AbstractUser
from django.db import models


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


class User(AbstractUser):
    email = models.EmailField("メールアドレス", unique=True)
    nickname = models.CharField("ニックネーム", max_length=50, blank=True)
    age_range = models.CharField(
        "年代", max_length=8, choices=AgeRange.choices, blank=True
    )
    skin_type = models.CharField(
        "肌質", max_length=16, choices=SkinType.choices, blank=True
    )
    email_verified = models.BooleanField("メール認証済み", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.nickname or self.email

    @property
    def has_written_review(self):
        return self.reviews.exists()
