from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products"
    label = "products"

    def ready(self):
        from . import signals_webp
        signals_webp.connect_image_to_webp()
        from . import signals  # noqa: F401  (post_save: Article.related_products 自動同期)
        signals.connect()
