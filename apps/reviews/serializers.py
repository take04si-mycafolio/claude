"""ネイティブアプリ連携API用シリアライザ (Phase 4: 口コミ投稿 第1段階=画像なし)。

既存の Web 用 forms.py / views.py / models.py には一切手を加えず、API 専用に
ここで定義する。画像(ReviewImage)は本段階では扱わない。
"""
from django.db import IntegrityError
from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import _abs_media_url

from .models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    """口コミ投稿（画像なし）。

    既存 ReviewForm に合わせた項目のみ受け付ける。
    - 必須: product / rating / title / body
    - 任意: usage_period / effectiveness / skin_type / cospa / control /
            safety / expression / icon
    - user は request.user を自動設定（リクエストからは受け取らない）。
    - is_approved はリクエストから受け取らず、サーバ側で False(承認待ち)を設定。
      ※ 既存Webフォーム投稿はモデル既定(True=即承認)のままで挙動不変。
    - product は is_published=True の商品のみ許可（非公開/不存在は 400）。
    """

    # 公開商品のみを許可対象にする。非公開/不存在の id は does_not_exist で弾かれる。
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_published=True)
    )

    class Meta:
        model = Review
        fields = (
            "id",
            "product",
            "rating",
            "title",
            "body",
            "usage_period",
            "effectiveness",
            "skin_type",
            "cospa",
            "control",
            "safety",
            "expression",
            "icon",
            "is_approved",
        )
        # is_approved はリクエストから受け取らず、サーバ側で False を設定して返すのみ。
        read_only_fields = ("id", "is_approved")

    def validate(self, attrs):
        # 1商品1ユーザー1口コミ。事前チェックで分かりやすいエラーにする
        # （DB の UniqueConstraint は競合時の最終防衛として create 内でも捕捉）。
        request = self.context.get("request")
        user = getattr(request, "user", None)
        product = attrs.get("product")
        if user is not None and product is not None:
            if Review.objects.filter(product=product, user=user).exists():
                raise serializers.ValidationError(
                    {"detail": "この商品にはすでに口コミを投稿済みです。"}
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["user"] = request.user  # user は必ずサーバ側で設定
        # アプリAPI経由の投稿は承認待ちにする（キャンペーン/ランキング連動のため）。
        # 既存Webフォーム投稿(forms.ReviewForm)はこの経路を通らず、
        # モデル既定(is_approved=True=即承認)のままで挙動は変わらない。
        validated_data["is_approved"] = False
        try:
            return Review.objects.create(**validated_data)
        except IntegrityError:
            # 競合（同時押下など）でユニーク制約に触れた場合も重複として返す。
            raise serializers.ValidationError(
                {"detail": "この商品にはすでに口コミを投稿済みです。"}
            )


class ReviewListSerializer(serializers.ModelSerializer):
    """GET /api/reviews/my/ 用。自分の投稿履歴。"""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_image_url = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "product",
            "product_name",
            "product_image_url",
            "rating",
            "title",
            "body",
            "is_approved",
            "created_at",
            "updated_at",
            "image_count",
        )

    def get_product_image_url(self, obj):
        p = obj.product
        return _abs_media_url(p.image, p.image_url, self.context.get("request"))

    def get_image_count(self, obj):
        # ビューで annotate(image_count_annot=...) があればそれを使い、無ければ count()。
        annotated = getattr(obj, "image_count_annot", None)
        return annotated if annotated is not None else obj.images.count()
