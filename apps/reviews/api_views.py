"""ネイティブアプリ連携API用ビュー (Phase 4: 口コミ投稿 第1段階=画像なし)。

既存の Web 用 views.py には手を加えず、API 専用にここで定義する。
認証は JWT（IsAuthenticated）。
"""
from django.db.models import Count
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewListSerializer


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
