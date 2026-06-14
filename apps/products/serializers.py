"""ネイティブアプリ連携API用シリアライザ (Phase 3: 商品・カテゴリ)。

既存の Web 用 views.py / models.py には一切手を加えず、API 専用にここで定義する。
すべて読み取り専用。

重要: MVP ではアフィリエイト系URL（affiliate_url / rakuten_url / amazon_url /
official_url）は一切レスポンスに含めない。
"""
from rest_framework import serializers

from .models import Category, Product


def _abs_media_url(field_file, external_url, request):
    """画像の絶対URLを返す。アプリから直接開ける形式にする。

    - ImageField(image) があればその URL を採用。
    - 無ければ外部URL(image_url)。WP移行データ等で "/media/..." という
      サイト相対パスが入っている場合があるため、"/" 始まりは絶対URL化する。
    - http(s):// で始まる外部絶対URLはそのまま返す。
    - どちらも無ければ None。
    """
    if field_file:
        url = field_file.url
    elif external_url:
        url = external_url
    else:
        return None
    if url.startswith("/") and request is not None:
        return request.build_absolute_uri(url)
    return url


class CategoryMiniSerializer(serializers.ModelSerializer):
    """商品にぶら下げる軽量カテゴリ表現。"""

    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class CategorySerializer(serializers.ModelSerializer):
    """GET /api/categories/ 用。

    ※ Category には is_published 等の公開フラグが存在しない。
      可視性に関わるフィールドは show_in_header のみ（ヘッダーナビ表示可否）。
    image_url は image(アップロード) を優先し、無ければ外部 image_url を返す。
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "image_url", "sort_order")

    def get_image_url(self, obj):
        return _abs_media_url(obj.image, obj.image_url, self.context.get("request"))


class ProductListSerializer(serializers.ModelSerializer):
    """商品一覧・検索用。アフィリエイトURLは含めない。"""

    image_url = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    product_type = CategoryMiniSerializer(read_only=True)
    categories = CategoryMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "price",
            "image_url",
            "average_rating",
            "review_count",
            "product_type",
            "categories",
        )

    def get_image_url(self, obj):
        return _abs_media_url(obj.image, obj.image_url, self.context.get("request"))

    def get_average_rating(self, obj):
        # ビュー側で annotate(avg_rating=...) 済み。未集計時/レビュー無しは 0。
        val = getattr(obj, "avg_rating", None)
        return round(val, 1) if val is not None else 0

    def get_review_count(self, obj):
        return getattr(obj, "review_count_annot", 0) or 0


class ProductDetailSerializer(ProductListSerializer):
    """商品詳細用。一覧項目に説明・特徴・スペックを追加。

    MVP につきアフィリエイト/EC/公式URLは一切含めない。
    """

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description",
            "features",
            "specifications",
        )
