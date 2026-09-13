"""ネイティブアプリ連携API用ビュー (Phase 4: 口コミ投稿)。

既存の Web 用 views.py には手を加えず、API 専用にここで定義する。
認証は JWT（IsAuthenticated）。

第2段階で写真付き投稿に対応:
  - JSON(application/json) の画像なし投稿は従来どおり維持。
  - multipart/form-data の場合のみ images（最大4枚）を受け取る。
  - 画像の枚数/サイズ/形式バリデーションは PC版Web(forms.MultipleImageField /
    ReviewForm.clean_images)と揃える。圧縮は ReviewImage.save 内の compress_image
    （PC版Webと同一）に委譲する。
"""
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    ListAPIView,
    ListCreateAPIView,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.products.models import Product

from django.db import IntegrityError

from . import compliance
from .imaging import MAX_UPLOAD_BYTES
from .models import (
    ProductUseLog,
    ProductUseLogImage,
    ProductUseLogReport,
    Review,
    ReviewImage,
    ReviewReport,
)
from .serializers import (
    ProductReviewSerializer,
    ProductUseLogCreateSerializer,
    ProductUseLogReportSerializer,
    ProductUseLogSerializer,
    ReviewCreateSerializer,
    ReviewListSerializer,
    ReviewReportSerializer,
)


class MyReviewPagination(PageNumberPagination):
    """投稿履歴のページング。1ユーザーの件数は通常少ないが安全側で導入。"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _compliance_gate_response(request):
    """タイトル・本文の薬機法・景表法ゲート。違反があれば 400 Response を返す。

    レスポンス形式は docs/review_compliance_gate_api.md 参照。DRF の
    ValidationError はネストした値をすべて文字列化してしまい、suggested_* の
    null や start/end の数値が壊れるため、素の Response で返す。
    """
    data = request.data
    title = str(data.get("title") or "") if hasattr(data, "get") else ""
    body = str(data.get("body") or "") if hasattr(data, "get") else ""
    findings = compliance.check_fields(title=title, body=body)
    if findings:
        return Response(
            compliance.api_error_payload(title, body, findings),
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


class ReviewCreateView(CreateAPIView):
    """POST /api/reviews/ — ログインユーザーが口コミを投稿（任意で写真付き）。

    成功時 201。重複投稿は serializer 側の ValidationError で 400
    （{"detail": "...投稿済み..."}）。非公開/不存在の商品も product フィールドの
    バリデーションエラーで 400。

    写真付き投稿:
      - Content-Type: application/json … 従来どおり画像なし投稿（images は無視）。
      - Content-Type: multipart/form-data … images（同名キー複数）を最大4枚まで。
    画像は本体テキスト項目と同じく request.data から serializer が読むため、
    multipart でも product/rating 等の既存項目はそのまま保存される。
    画像は request.FILES.getlist("images") で取得し、検証後に ReviewImage へ保存する。
    口コミ本体と画像保存は transaction.atomic でまとめ、画像保存に失敗した場合は
    Review ごとロールバックして中途半端な状態を残さない。
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewCreateSerializer
    # JSON(従来) と multipart(画像付き) の両方を受け付ける。
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # CreateAPIView は get_serializer 経由で context に request を入れるため、
    # serializer 側で request.user を参照できる。

    def _collect_images(self):
        """multipart の場合のみ images を取り出して検証する。

        JSON 投稿では request.FILES は空なので必ず [] を返し、従来挙動を保つ。
        枚数/サイズ/形式は PC版Web(forms.MultipleImageField / clean_images)と同一基準。
        実体が画像か（image/* を詐称した非画像）は圧縮処理(compress_image=PIL)で最終判定し、
        失敗時は perform 内で 400 に変換する。
        """
        images = self.request.FILES.getlist("images")
        if not images:
            return []
        if len(images) > ReviewImage.MAX_PER_REVIEW:
            raise ValidationError(
                {"images": [f"画像は最大{ReviewImage.MAX_PER_REVIEW}枚までです。"]}
            )
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        for f in images:
            if f.size > MAX_UPLOAD_BYTES:
                raise ValidationError(
                    {"images": [f"画像1枚あたり{mb}MBまでです。「{f.name}」が大きすぎます。"]}
                )
            content_type = getattr(f, "content_type", "") or ""
            if not content_type.startswith("image/"):
                raise ValidationError(
                    {"images": [f"画像ファイルのみアップロードできます。「{f.name}」は画像ではありません。"]}
                )
        return images

    def create(self, request, *args, **kwargs):
        # 薬機法・景表法ゲート。違反があれば構造化ペイロード(compliance)付き 400。
        # serializer の ValidationError はネスト値を文字列化してしまうため、
        # ここで素の Response として返す。
        gate = _compliance_gate_response(request)
        if gate is not None:
            return gate

        # 画像は本体保存より前に基本検証（枚数/サイズ/形式）を済ませて 400 を返す。
        images = self._collect_images()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 本体作成と画像保存を1トランザクションに。重複(IntegrityError→ValidationError)や
        # 画像の圧縮失敗が起きた場合は Review ごとロールバックする。
        with transaction.atomic():
            self.perform_create(serializer)  # serializer.create が重複を 400 に変換
            review = serializer.instance
            try:
                for i, f in enumerate(images):
                    # 圧縮(WebP/長辺1600/quality82)は ReviewImage.save 内で実施=PC版Webと同一。
                    ReviewImage.objects.create(review=review, image=f, order=i)
            except ValidationError:
                raise
            except Exception:
                # image/* を詐称した非画像など、PIL が開けないファイルは 400 にする。
                # 例外メッセージにファイル内容が混ざらないよう固定文言のみ返す。
                raise ValidationError(
                    {"images": ["画像を処理できませんでした。画像ファイルか確認してください。"]}
                )

        headers = self.get_success_headers(serializer.data)
        data = dict(serializer.data)
        data["image_count"] = len(images)  # 保存した画像枚数を返す（画像なしは0）。
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


class MyReviewListView(ListAPIView):
    """GET /api/reviews/my/ — 自分の口コミのみを新しい順で返す。"""

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewListSerializer
    pagination_class = MyReviewPagination

    def get_queryset(self):
        return (
            Review.objects.filter(user=self.request.user)
            .select_related("product")
            .prefetch_related("images")  # image_urls の N+1 回避
            .annotate(image_count_annot=Count("images"))
            .order_by("-created_at")
        )


class ReviewDestroyView(DestroyAPIView):
    """DELETE /api/reviews/{id}/ — ログインユーザーが自分の口コミを削除する。

    get_queryset を request.user の口コミに限定するため、他人/不存在の id は 404 になり
    他人の口コミは削除できない。削除は論理削除（運営のみ閲覧可）で行う。
    キャンペーン算入済みの口コミは削除不可（409）。成功時 204（本文なし）。
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # 自分の口コミのみ。これにより他人の id を指定しても 404 で弾かれる。
        return Review.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        if instance.is_campaign_consumed:
            raise ValidationError(
                {"detail": "この口コミはキャンペーンの対象になっているため削除できません。"}
            )
        instance.soft_delete()


class ReviewReportCreateView(CreateAPIView):
    """POST /api/reviews/{id}/report/ — ログインユーザーが口コミを通報する。

    重要: 通報されても口コミの自動削除・非表示は行わない。ReviewReport を作成して
    運営が管理画面で確認できるようにするだけ。

    仕様:
      - IsAuthenticated（匿名は 401）。
      - 不存在の口コミ → 404。
      - 自分の口コミ → 400（{"detail": "..."}）。
      - すでに通報済み → 400。
      - reason 不正・comment 超過 → 400（serializer 検証）。
      - 成功 → 201 {"id","review","reason","status","created_at"}。
    token や個人情報、画像内容はレスポンス／ログに出さない（固定文言のみ）。
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewReportSerializer

    def create(self, request, *args, **kwargs):
        review = get_object_or_404(Review, pk=self.kwargs["pk"])

        if review.user_id == request.user.id:
            return Response(
                {"detail": "自分の口コミは通報できません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ReviewReport.objects.filter(review=review, reporter=request.user).exists():
            return Response(
                {"detail": "この口コミはすでに通報済みです。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(review=review, reporter=request.user)
        except IntegrityError:
            # 同時押下などで UniqueConstraint に触れた場合も重複として返す。
            return Response(
                {"detail": "この口コミはすでに通報済みです。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class ProductReviewListView(ListAPIView):
    """GET /api/products/{id}/reviews/ — 指定商品の承認済み口コミを新しい順で返す。

    口コミ本文・画像URL・投稿者情報は会員限定のため IsAuthenticated（匿名は 401）。
    商品一覧/詳細/カテゴリ API（AllowAny）は従来どおり公開のまま維持する。
    非公開/不存在の商品は 404（ProductDetailView と同じ挙動）。
    is_approved=True のみ・新しい順。画像(ReviewImage)は本段階では対象外。
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProductReviewSerializer
    pagination_class = MyReviewPagination

    def get_queryset(self):
        # 公開商品のみ。不存在/非公開は 404 にして詳細APIと挙動を揃える。
        product = get_object_or_404(
            Product, pk=self.kwargs["product_id"], is_published=True
        )
        return (
            Review.objects.filter(product=product, is_approved=True)
            .select_related("product", "user")
            .prefetch_related("images")  # image_urls の N+1 回避
            .annotate(image_count_annot=Count("images"))
            .order_by("-created_at")
        )


# ======================================================================
# 使用記録（ProductUseLog）API。既存の口コミ API には手を加えず独立に定義する。
# すべて IsAuthenticated（一覧・投稿・削除・通報すべてログイン必須）。
# ======================================================================
def _collect_use_log_images(request):
    """multipart の使用記録投稿から images を取り出して基本検証する。

    枚数/サイズ/形式は既存口コミ画像と同一基準（MAX_PER_LOG=4 / 15MB / image/*）。
    JSON 投稿では request.FILES は空なので [] を返す。
    """
    images = request.FILES.getlist("images")
    if not images:
        return []
    if len(images) > ProductUseLogImage.MAX_PER_LOG:
        raise ValidationError(
            {"images": [f"画像は最大{ProductUseLogImage.MAX_PER_LOG}枚までです。"]}
        )
    mb = MAX_UPLOAD_BYTES // (1024 * 1024)
    for f in images:
        if f.size > MAX_UPLOAD_BYTES:
            raise ValidationError(
                {"images": [f"画像1枚あたり{mb}MBまでです。「{f.name}」が大きすぎます。"]}
            )
        content_type = getattr(f, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValidationError(
                {"images": [f"画像ファイルのみアップロードできます。「{f.name}」は画像ではありません。"]}
            )
    return images


class ProductUseLogListCreateView(ListCreateAPIView):
    """GET/POST /api/products/{product_id}/use-logs/

    GET … 指定商品の使用記録を新しい順で返す（IsAuthenticated・匿名 401）。
    POST … 使用記録を投稿（IsAuthenticated）。1商品に複数件OK・星評価なし・任意で写真付き。
    非公開/不存在の商品は 404。
    """

    permission_classes = [IsAuthenticated]
    pagination_class = MyReviewPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductUseLogCreateSerializer
        return ProductUseLogSerializer

    def _get_product(self):
        # 公開商品のみ。不存在/非公開は 404 にして詳細APIと挙動を揃える。
        return get_object_or_404(
            Product, pk=self.kwargs["product_id"], is_published=True
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["product"] = self._get_product()
        return ctx

    def get_queryset(self):
        from django.db.models import Q

        product = self._get_product()
        # 承認制: 他人の投稿は承認済みのみ。自分の承認待ちは自分にだけ返す
        # （is_approved フィールドでアプリ側が「承認待ち」表示する）。
        return (
            ProductUseLog.objects.filter(product=product)
            .filter(Q(is_approved=True) | Q(user=self.request.user))
            .select_related("product", "user", "review")
            .prefetch_related("images")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        # 薬機法・景表法ゲート（通常口コミと同一ルール・同一レスポンス形式）。
        gate = _compliance_gate_response(request)
        if gate is not None:
            return gate

        # 画像は本体保存より前に基本検証（枚数/サイズ/形式）を済ませて 400 を返す。
        images = _collect_use_log_images(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            use_log = serializer.save()
            try:
                for i, f in enumerate(images):
                    ProductUseLogImage.objects.create(
                        use_log=use_log, image=f, order=i
                    )
            except ValidationError:
                raise
            except Exception:
                # image/* を詐称した非画像など PIL が開けないファイルは 400。
                # 例外メッセージにファイル内容を混ぜず固定文言のみ返す。
                raise ValidationError(
                    {"images": ["画像を処理できませんでした。画像ファイルか確認してください。"]}
                )
        # 作成結果は表示用シリアライザで返す（user/image_urls/can_* を含む）。
        out = ProductUseLogSerializer(use_log, context=self.get_serializer_context())
        headers = self.get_success_headers(serializer.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)


class ProductUseLogDestroyView(DestroyAPIView):
    """DELETE /api/use-logs/{id}/ — 投稿者本人が自分の使用記録を削除する。

    get_queryset を request.user に限定するため、他人/不存在の id は 404。
    削除は既存口コミに合わせて論理削除（運営のみ閲覧可）。成功時 204。
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProductUseLog.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()


class ProductUseLogReportCreateView(CreateAPIView):
    """POST /api/use-logs/{id}/report/ — 使用記録を運営へ通報する。

    通報されても自動削除・非表示はしない（受付レコードのみ）。
    - IsAuthenticated（匿名は 401）。
    - 不存在の使用記録 → 404。
    - 自分の使用記録 → 400。
    - すでに通報済み → 400。
    token や個人情報、通報本文はレスポンス/ログに出さない（固定文言のみ）。
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProductUseLogReportSerializer

    def create(self, request, *args, **kwargs):
        use_log = get_object_or_404(ProductUseLog, pk=self.kwargs["pk"])

        if use_log.user_id == request.user.id:
            return Response(
                {"detail": "自分の使用記録は通報できません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ProductUseLogReport.objects.filter(
            use_log=use_log, reporter=request.user
        ).exists():
            return Response(
                {"detail": "この使用記録はすでに通報済みです。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(use_log=use_log, reporter=request.user)
        except IntegrityError:
            return Response(
                {"detail": "この使用記録はすでに通報済みです。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )
