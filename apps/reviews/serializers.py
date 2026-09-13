"""ネイティブアプリ連携API用シリアライザ (Phase 4: 口コミ投稿 第1段階=画像なし)。

既存の Web 用 forms.py / views.py / models.py には一切手を加えず、API 専用に
ここで定義する。画像(ReviewImage)は本段階では扱わない。
"""
from django.db import IntegrityError
from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import _abs_media_url

from .models import (
    ProductUseLog,
    ProductUseLogReport,
    Review,
    ReviewReport,
)


class ReviewReportSerializer(serializers.ModelSerializer):
    """POST /api/reviews/{id}/report/ 用。

    入力は reason（必須・choices）と comment（任意・最大1000文字）のみ。
    review / reporter / status はサーバ側（view）で設定するため read_only。
    自分の口コミ通報・二重通報・不存在口コミの判定は view 側で行い、明確な
    ステータスコードを返す。
    """

    review = serializers.PrimaryKeyRelatedField(read_only=True)
    comment = serializers.CharField(
        required=False, allow_blank=True,
        max_length=ReviewReport.COMMENT_MAX_LEN,
    )

    class Meta:
        model = ReviewReport
        fields = ("id", "review", "reason", "comment", "status", "created_at")
        read_only_fields = ("id", "review", "status", "created_at")


class ReviewCreateSerializer(serializers.ModelSerializer):
    """口コミ投稿（画像なし）。

    既存 ReviewForm に合わせた項目のみ受け付ける。
    - 必須: product / rating / title / body
    - 任意: usage_period / effectiveness / skin_type / cospa / control /
            safety / expression / icon
    - user は request.user を自動設定（リクエストからは受け取らない）。
    - is_approved は常に False で作成（承認制）。運営が管理画面で承認すると掲載される。
      ※ PC版Webフォーム投稿も同じく承認待ちになるため挙動が一致する。
    - 投稿前に薬機法・景表法ゲート(compliance)を通す。違反があれば 400 で
      {"detail", "compliance": {"findings": [...], "suggested_title", "suggested_body",
      "hint"}} を返す（アプリ側はこれをそのまま指摘UIに使える）。
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
        # is_approved はリクエストから受け取らない（常に承認待ちで作成し、値を返すのみ）。
        read_only_fields = ("id", "is_approved")

    def validate(self, attrs):
        # 1商品1ユーザー1口コミ。事前チェックで分かりやすいエラーにする
        # （DB の UniqueConstraint は競合時の最終防衛として create 内でも捕捉）。
        request = self.context.get("request")
        user = getattr(request, "user", None)
        product = attrs.get("product")
        if user is not None and product is not None:
            # 有効な(削除されていない)口コミがある場合のみ重複として弾く。論理削除済みは
            # 下の create() で同じ行を復活させる（created_at を保つ）。
            if Review.objects.filter(product=product, user=user).exists():
                raise serializers.ValidationError(
                    {"detail": "この商品にはすでに口コミを投稿済みです。"}
                )
        # 薬機法・景表法ゲートは view(ReviewCreateView.create) 側で先に実施する。
        # DRF の ValidationError はネスト値を文字列化してしまい、構造化ペイロード
        # (suggested_* の null や start/end の数値)が壊れるため、ここでは行わない。
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["user"] = request.user  # user は必ずサーバ側で設定
        # 承認制: 常に承認待ちで作成する。運営承認後に掲載され、ミッション集計
        # (is_approved=True のみカウント)にも承認後に反映される。PC版Webと同一挙動。
        validated_data["is_approved"] = False
        # 過去に論理削除した口コミがあれば同じ行を復活させる（再投稿でのキャンペーン
        # 期間滑り込みを防ぐため created_at を維持）。
        revived = Review.all_objects.filter(
            product=validated_data["product"], user=validated_data["user"],
            is_deleted=True,
        ).first()
        if revived is not None:
            for field, value in validated_data.items():
                setattr(revived, field, value)
            revived.is_deleted = False
            revived.deleted_at = None
            revived.images.all().delete()  # 旧画像は持ち越さない
            revived.save()
            return revived
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
    # 口コミ投稿画像(ReviewImage)の絶対URL配列。画像なしは空配列[]。
    image_urls = serializers.SerializerMethodField()
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
            "image_urls",
        )

    def get_product_image_url(self, obj):
        p = obj.product
        return _abs_media_url(p.image, p.image_url, self.context.get("request"))

    def get_image_urls(self, obj):
        # 投稿画像を表示順(Meta.ordering=order,id)で絶対URL化。画像なしは []。
        # ビュー側で prefetch_related("images") 済みのため N+1 にならない。
        request = self.context.get("request")
        return [
            url
            for im in obj.images.all()
            if (url := _abs_media_url(im.image, None, request)) is not None
        ]

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

    # ゲスト投稿(user=None・メディアサイト方針 2026-09-06)は user系を null/匿名で返す
    user_id = serializers.IntegerField(read_only=True)
    user_nickname = serializers.SerializerMethodField()
    user_display_name = serializers.SerializerMethodField()
    user_review_level = serializers.SerializerMethodField()
    user_category_badge = serializers.SerializerMethodField()
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

    def get_user_nickname(self, obj):
        return obj.user.nickname if obj.user_id else ""

    def get_user_display_name(self, obj):
        # email は公開しない。nickname 未設定・ゲストは PC版Web同様の表示名。
        return obj.display_name

    def get_user_review_level(self, obj):
        return obj.user.review_level if obj.user_id else None

    def get_user_category_badge(self, obj):
        return obj.user.category_badge if obj.user_id else None

    def get_user_age_range_display(self, obj):
        if not obj.user_id:
            return None
        return obj.user.get_age_range_display() if obj.user.age_range else None

    def get_user_gender_display(self, obj):
        if not obj.user_id:
            return None
        return obj.user.get_gender_display() if obj.user.gender else None


# ======================================================================
# 使用記録（ProductUseLog）用シリアライザ。既存の口コミ用シリアライザには
# 一切手を加えず、ここで独立に定義する。
# ======================================================================
class ProductUseLogReportSerializer(serializers.ModelSerializer):
    """POST /api/use-logs/{id}/report/ 用。入力は reason（必須）と comment（任意）のみ。

    use_log / reporter / status はサーバ側（view）で設定するため read_only。
    自分の使用記録の通報・二重通報・不存在の判定は view 側で行う。
    """

    use_log = serializers.PrimaryKeyRelatedField(read_only=True)
    comment = serializers.CharField(
        required=False, allow_blank=True,
        max_length=ProductUseLogReport.COMMENT_MAX_LEN,
    )

    class Meta:
        model = ProductUseLogReport
        fields = ("id", "use_log", "reason", "comment", "status", "created_at")
        read_only_fields = ("id", "use_log", "status", "created_at")


class ProductUseLogSerializer(serializers.ModelSerializer):
    """GET 用（使用記録一覧）。商品ID単位で取得する想定。

    本文・画像URLは会員限定（view が IsAuthenticated）。review_id は紐付け口コミが
    あれば返し、無ければ null（アプリの「この人の使用記録を見る」導線の余地を残す）。
    """

    product_id = serializers.IntegerField(read_only=True)
    review_id = serializers.IntegerField(read_only=True)
    user = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_report = serializers.SerializerMethodField()
    is_reported_by_me = serializers.SerializerMethodField()

    class Meta:
        model = ProductUseLog
        fields = (
            "id",
            "product_id",
            "review_id",
            "user",
            "title",
            "body",
            "image_urls",
            "is_approved",
            "created_at",
            "updated_at",
            "can_delete",
            "can_report",
            "is_reported_by_me",
        )

    def _request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_user(self, obj):
        # avatar は既存仕様(UserSerializer.avatar_url)に合わせ、絶対URL or null。
        request = self.context.get("request")
        avatar_url = None
        if obj.user.avatar:
            url = obj.user.avatar.url
            avatar_url = request.build_absolute_uri(url) if request else url
        return {
            "id": obj.user_id,
            "nickname": obj.user.nickname or "匿名",
            "avatar_url": avatar_url,
        }

    def get_image_urls(self, obj):
        # 表示順(Meta.ordering=order,id)で絶対URL化。画像なしは []。
        # view 側で prefetch_related("images") 済みのため N+1 にならない。
        request = self.context.get("request")
        return [
            url
            for im in obj.images.all()
            if (url := _abs_media_url(im.image, None, request)) is not None
        ]

    def get_can_delete(self, obj):
        u = self._request_user()
        return bool(u and u.is_authenticated and obj.user_id == u.id)

    def get_can_report(self, obj):
        u = self._request_user()
        # 自分の使用記録は通報不可。
        return bool(u and u.is_authenticated and obj.user_id != u.id)

    def get_is_reported_by_me(self, obj):
        u = self._request_user()
        if not (u and u.is_authenticated):
            return False
        return ProductUseLogReport.objects.filter(
            use_log=obj, reporter=u
        ).exists()


class ProductUseLogCreateSerializer(serializers.ModelSerializer):
    """POST 用（使用記録投稿）。

    - body 必須・最大 ProductUseLog.BODY_MAX_LEN(5000)文字。
    - review_id 任意。指定時は同じ商品・同じ投稿者の通常口コミのみ許可（他人/別商品は400）。
    - rating は受け付けない。送られた場合は 400。
    - product は view から context で渡す（URL の product_id）。
    - images は view 側で受け取り保存する（本シリアライザは本文と紐付けのみ扱う）。
    """

    review_id = serializers.PrimaryKeyRelatedField(
        source="review", queryset=Review.objects.all(),
        required=False, allow_null=True,
    )
    title = serializers.CharField(
        max_length=120, required=False, allow_blank=True,
    )
    body = serializers.CharField(
        max_length=ProductUseLog.BODY_MAX_LEN,
        allow_blank=False, trim_whitespace=True,
    )

    class Meta:
        model = ProductUseLog
        fields = ("id", "review_id", "title", "body", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        # rating は使用記録に存在しない。送られたら 400。
        if "rating" in self.initial_data:
            raise serializers.ValidationError(
                {"rating": ["使用記録に星評価はありません。"]}
            )
        request = self.context.get("request")
        user = getattr(request, "user", None)
        product = self.context.get("product")
        review = attrs.get("review")
        if review is not None:
            # 同じ商品・同じ投稿者の口コミにのみ紐付け可（他人/別商品は不可）。
            if user is None or review.user_id != user.id:
                raise serializers.ValidationError(
                    {"review_id": ["自分の口コミにのみ紐付けできます。"]}
                )
            if product is not None and review.product_id != product.id:
                raise serializers.ValidationError(
                    {"review_id": ["この商品の口コミではありません。"]}
                )
        # 薬機法・景表法ゲートは view(ProductUseLogListCreateView.create) 側で
        # 先に実施する（通常口コミと同じ理由・同一レスポンス形式）。
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["user"] = request.user
        validated_data["product"] = self.context.get("product")
        return ProductUseLog.objects.create(**validated_data)
