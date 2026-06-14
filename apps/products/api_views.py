"""ネイティブアプリ連携API用ビュー (Phase 3: 商品・カテゴリ)。

すべて読み取り専用・認証不要(AllowAny)。
既存の Web 用 views.py の集計ロジック(_annotate 相当)に揃える。
"""
from django.db.models import Avg, Count, Q
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class ProductPagination(PageNumberPagination):
    """商品一覧/検索のページング。グローバル settings は変更せずビュー単位で設定。"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _annotated_published_products():
    """is_published=True の商品に、既存サイトと同じ評価集計を付与した queryset。

    avg_rating / review_count_annot は serializers が参照する名前に合わせる。
    並び順は Product.Meta の既定（sort_order, -created_at）を踏襲。
    """
    return (
        Product.objects.filter(is_published=True)
        .select_related("product_type")
        .prefetch_related("categories")
        .annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            review_count_annot=Count("reviews", filter=Q(reviews__is_approved=True)),
        )
    )


class CategoryListView(ListAPIView):
    """GET /api/categories/ — カテゴリ一覧。

    ※ Category に公開フラグ(is_published)は存在しないため全カテゴリを返す。
      並び順は Category.Meta の既定（sort_order, name）。
    """

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None  # カテゴリ数は少ないので全件返す

    def get_queryset(self):
        return Category.objects.all().order_by("sort_order", "name")


class ProductListView(ListAPIView):
    """GET /api/products/ — 公開商品一覧。

    クエリ:
      - type=<product_type slug>  : 製品タイプで絞り込み
      - category=<category slug>  : 機能カテゴリ(M2M)で絞り込み
      - page / page_size          : ページング
    """

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = _annotated_published_products()
        type_slug = self.request.query_params.get("type", "").strip()
        category_slug = self.request.query_params.get("category", "").strip()
        if type_slug:
            qs = qs.filter(product_type__slug=type_slug, product_type__parent__isnull=True)
        if category_slug:
            qs = qs.filter(categories__slug=category_slug)
        return qs.distinct()


class ProductSearchView(ListAPIView):
    """GET /api/products/search/?q= — 公開商品を商品名・ブランド名で検索。

    q が空のときは 400（誤って全件を返さないための安全側）。
    """

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination

    def list(self, request, *args, **kwargs):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response(
                {"detail": "検索キーワード(q)を指定してください。"}, status=400
            )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        qs = _annotated_published_products()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q))
        return qs.distinct()


class ProductDetailView(RetrieveAPIView):
    """GET /api/products/{id}/ — 公開商品の詳細。非公開/不存在は 404。"""

    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return _annotated_published_products()
