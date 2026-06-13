from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path("", views.list_view, name="list"),

    # 全記事一覧
    path("articles/", views.article_list, name="article_list"),

    # 全商品一覧
    path("products/", views.all_products, name="all_products"),

    # ブックマーク (POST)
    path("products/<uslug:slug>/bookmark/", views.bookmark_toggle, name="bookmark_toggle"),

    # 2セグメント以上を先に登録 (順序重要)
    path("<uslug:type_slug>/ranking/", views.type_ranking, name="type_ranking"),
    path("<uslug:type_slug>/products/<uslug:slug>/", views.detail, name="detail"),

    # ルート直下 dispatcher: カテゴリTOP or 記事詳細を自動判定
    path("<uslug:slug>/", views.slug_dispatch, name="slug_dispatch"),
    # 別名(同じパス、reverse用) - テンプレ既存の {% url 'products:type_detail' %} 等が動く
    path("<uslug:slug>/", views.slug_dispatch, name="type_detail"),
    path("<uslug:slug>/", views.slug_dispatch, name="article_detail"),
]
