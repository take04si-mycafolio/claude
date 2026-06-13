from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.products.models import Article, Category, Product


class HomeSitemap(Sitemap):
    protocol = "https"
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["home"]

    def location(self, item):
        return "/"


class StaticViewSitemap(Sitemap):
    protocol = "https"
    priority = 0.5
    changefreq = "monthly"

    def items(self):
        return [
            "products:article_list",
            "pages:terms",
            "pages:privacy",
            "pages:contact",
            "pages:post_review_lp",
        ]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    """カテゴリTOP (/<slug>/)"""
    protocol = "https"
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return Category.objects.filter(show_in_header=True).order_by("sort_order", "id")

    def location(self, obj):
        return f"/{obj.slug}/"


class CategoryRankingSitemap(Sitemap):
    """カテゴリランキング (/<slug>/ranking/)"""
    protocol = "https"
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Category.objects.filter(show_in_header=True).order_by("sort_order", "id")

    def location(self, obj):
        return f"/{obj.slug}/ranking/"


class ArticleSitemap(Sitemap):
    """記事 (/<slug>/)"""
    protocol = "https"
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return Article.objects.filter(is_published=True).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class ProductSitemap(Sitemap):
    """商品 (/<type_slug>/products/<slug>/)"""
    protocol = "https"
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return Product.objects.filter(is_published=True).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


sitemaps = {
    "home": HomeSitemap,
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "articles": ArticleSitemap,
    "products": ProductSitemap,
}
