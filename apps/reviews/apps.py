from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    label = "reviews"

    def ready(self):
        # 口コミ画像は ReviewImage.save() 内で自前で WebP 圧縮（リサイズ込み）する。
        # 全 ImageField 共通の WebP 変換シグナル（apps.products.signals_webp）が
        # ReviewImage にも繋がっており二重エンコードになるため、これだけ無効化する。
        # apps.reviews は apps.products の後に読み込まれるため、接続済みを確実に外せる。
        from django.db.models.signals import pre_save
        ReviewImage = self.get_model("ReviewImage")
        pre_save.disconnect(
            sender=ReviewImage,
            dispatch_uid="webp_convert_reviews.ReviewImage",
        )
