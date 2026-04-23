from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField("カテゴリ名", max_length=100, unique=True)
    slug = models.SlugField("スラッグ", max_length=120, unique=True)
    description = models.TextField("説明", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "カテゴリ"
        verbose_name_plural = "カテゴリ"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField("商品名", max_length=200)
    slug = models.SlugField("スラッグ", max_length=220, unique=True, allow_unicode=True)
    brand = models.CharField("メーカー", max_length=100, blank=True)
    categories = models.ManyToManyField(
        Category, related_name="products", blank=True, verbose_name="カテゴリ"
    )
    price = models.PositiveIntegerField("参考価格(円)", null=True, blank=True)
    image = models.ImageField("画像", upload_to="products/", blank=True, null=True)
    image_url = models.URLField("画像URL(外部)", blank=True)
    description = models.TextField("商品説明", blank=True)
    features = models.TextField("特徴", blank=True, help_text="箇条書きで記載")
    official_url = models.URLField("公式サイトURL", blank=True)
    affiliate_url = models.URLField("アフィリエイトURL", blank=True)
    is_published = models.BooleanField("公開", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "美顔器"
        verbose_name_plural = "美顔器"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        return self.image_url or ""

    def review_stats(self):
        stats = self.reviews.filter(is_approved=True).aggregate(
            avg=Avg("rating"), count=Count("id")
        )
        return {
            "average": round(stats["avg"], 1) if stats["avg"] else 0,
            "count": stats["count"] or 0,
        }


class Article(models.Model):
    """WordPressからインポートする記事コンテンツ (SEO用の読み物ページ)"""

    title = models.CharField("タイトル", max_length=255)
    slug = models.SlugField("スラッグ", max_length=280, unique=True, allow_unicode=True)
    content = models.TextField("本文(HTML)")
    excerpt = models.TextField("抜粋", blank=True)
    related_products = models.ManyToManyField(
        Product, related_name="articles", blank=True, verbose_name="関連商品"
    )
    wp_post_id = models.IntegerField("WordPress投稿ID", null=True, blank=True, unique=True)
    wp_author = models.CharField("WP投稿者", max_length=100, blank=True)
    published_at = models.DateTimeField("公開日", null=True, blank=True)
    is_published = models.BooleanField("公開", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "記事"
        verbose_name_plural = "記事"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("products:article_detail", kwargs={"slug": self.slug})
