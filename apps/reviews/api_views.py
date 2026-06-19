"""ネイティブアプリ連携API用ビュー (Phase 4: 口コミ投稿 第1段階=画像なし)。

既存の Web 用 views.py には手を加えず、API 専用にここで定義する。
認証は JWT（IsAuthenticated）。
"""
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.products.models import Product

from .models import Review
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
    """POST /api/reviews/ — ログインユーザーが口コミを投稿（画像なし）。

    成功時 201。重複投稿は serializer 側の ValidationError で 400
    （{"detail": "...投稿済み..."}）。非公開/不存在の商品も product フィールドの
    バリデーションエラーで 400。
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewCreateSerializer

    # CreateAPIView は get_serializer 経由で context に request を入れるため、
    # serializer 側で request.user を参照できる。


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
