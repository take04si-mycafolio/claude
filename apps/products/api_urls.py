"""products アプリの API ルート (Phase 3: 商品・カテゴリ)。

config/api_urls.py から include される。
重要: products/search/ は products/<int:pk>/ より前に置く（pk に search が
飲まれないようにする）。
"""
from django.urls import path

from . import api_views

urlpatterns = [
    path("categories/", api_views.CategoryListView.as_view(), name="api_categories"),
    path("products/", api_views.ProductListView.as_view(), name="api_products"),
    path(
        "products/search/",
        api_views.ProductSearchView.as_view(),
        name="api_products_search",
    ),
    path(
        "products/<int:pk>/",
        api_views.ProductDetailView.as_view(),
        name="api_product_detail",
    ),
]
