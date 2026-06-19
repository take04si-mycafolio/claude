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
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.products.models import Product

from .imaging import MAX_UPLOAD_BYTES
from .models import Review, ReviewImage
from .serializers import (
    ProductReviewSerializer,
    ReviewCreateSerializer,
    ReviewListSerializer,
)


class MyReviewPagination(PageNumberPagination):
    """投稿履歴のページング。1ユーザーの件数は通常少ないが安全側で導入。"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


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
            .annotate(image_count_annot=Count("images"))
            .order_by("-created_at")
        )


class ProductReviewListView(ListAPIView):
    """GET /api/products/{id}/reviews/ — 指定商品の承認済み口コミを新しい順で返す。

    商品詳細ページの一般表示用途のため、products 系API（AllowAny・読み取り専用）に
    合わせて公開とする。非公開/不存在の商品は 404（ProductDetailView と同じ挙動）。
    is_approved=True のみ・新しい順。画像(ReviewImage)は本段階では対象外。
    """

    permission_classes = [AllowAny]
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
            .annotate(image_count_annot=Count("images"))
            .order_by("-created_at")
        )
