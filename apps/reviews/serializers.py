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
    - is_approved はリクエストから受け取らず、モデル既定(True=即承認)に任せる。
      ※ PC版Webフォーム投稿もモデル既定(True)で即承認のため挙動が一致する。
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
        # is_approved はリクエストから受け取らず、モデル既定(True)の値を返すのみ。
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
        # is_approved は明示設定せず、モデル既定(True=即承認)に任せる。
        # これにより PC版Webフォーム投稿(forms.ReviewForm)と同じく即承認となり、
        # ミッション集計(is_approved=True のみカウント)にも反映され体験が一致する。
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
    # 選択肢系は値に加えて表示ラベルも返す（PC版Webの get_xxx_display と一致）。
    # blank("") のときは null を返し、アプリ側で非表示にしやすくする。
    usage_period_display = serializers.SerializerMethodField()
    effectiveness_display = serializers.SerializerMethodField()
    skin_type_display = serializers.SerializerMethodField()

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
            # 詳細評価（1〜5・未入力は null）。アプリ側で星表示する。
            "cospa",
            "control",
            "safety",
            "expression",
            # あなたの情報（choice系は値＋表示ラベル、icon は番号）。
            "usage_period",
            "usage_period_display",
            "effectiveness",
            "effectiveness_display",
            "skin_type",
            "skin_type_display",
            "icon",
            "is_approved",
            "created_at",
            "updated_at",
            "image_count",
        )

    def get_product_image_url(self, obj):
        p = obj.product
        return _abs_media_url(p.image, p.image_url, self.context.get("request"))

    def get_usage_period_display(self, obj):
        return obj.get_usage_period_display() if obj.usage_period else None

    def get_effectiveness_display(self, obj):
        return obj.get_effectiveness_display() if obj.effectiveness else None

    def get_skin_type_display(self, obj):
        return obj.get_skin_type_display() if obj.skin_type else None

    def get_image_count(self, obj):
        # ビューで annotate(image_count_annot=...) があればそれを使い、無ければ count()。
        annotated = getattr(obj, "image_count_annot", None)
        return annotated if annotated is not None else obj.images.count()


class ProductReviewSerializer(ReviewListSerializer):
    """GET /api/products/{id}/reviews/ 用。商品ページで全ユーザーの口コミを表示する。

    ReviewListSerializer（投稿履歴用）を継承し、口コミ本体・詳細評価・あなたの情報・
    表示ラベルをそのまま再利用したうえで、PC版Web口コミカードに合わせた投稿者情報を
    追加する。email は公開しない（表示名は nickname、未設定時は「匿名」）。
    詳細評価は数値(1〜5)のまま返し、星表示はアプリ側で行う。
    """

    user_id = serializers.IntegerField(read_only=True)
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)
    user_display_name = serializers.SerializerMethodField()
    user_review_level = serializers.IntegerField(source="user.review_level", read_only=True)
    user_category_badge = serializers.CharField(
        source="user.category_badge", read_only=True
    )
    # age_range / gender は PC版Webカードでも公開表示している項目（新規の情報公開ではない）。
    # アプリ表示では必須ではないが互換のため表示ラベルを返す（未設定は null）。
    user_age_range_display = serializers.SerializerMethodField()
    user_gender_display = serializers.SerializerMethodField()

    class Meta(ReviewListSerializer.Meta):
        fields = ReviewListSerializer.Meta.fields + (
            "user_id",
            "user_nickname",
            "user_display_name",
            "user_review_level",
            "user_category_badge",
            "user_age_range_display",
            "user_gender_display",
        )

    def get_user_display_name(self, obj):
        # email は公開しない。nickname 未設定時は PC版Web同様「匿名」。
        return obj.user.nickname or "匿名"

    def get_user_age_range_display(self, obj):
        return obj.user.get_age_range_display() if obj.user.age_range else None

    def get_user_gender_display(self, obj):
        return obj.user.get_gender_display() if obj.user.gender else None
