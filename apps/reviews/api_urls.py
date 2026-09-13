"""reviews アプリの API ルート (Phase 4: 口コミ投稿 第1段階)。

config/api_urls.py から include される。
重要: reviews/my/ は将来 reviews/<...> の詳細URLを追加する場合に備え、
必ず詳細URLより前に置く（my が pk 等に飲まれないようにする）。
"""
from django.urls import path

from . import api_views

urlpatterns = [
    # my/ を先に登録（reviews/<pk>/ より前に置き取り違えを防ぐ。"my" は int でないため
    # 実際には <int:pk> に飲まれないが、規約として順序を維持する）。
    path("reviews/my/", api_views.MyReviewListView.as_view(), name="api_my_reviews"),
    path("reviews/", api_views.ReviewCreateView.as_view(), name="api_review_create"),
    # 口コミ通報（POST のみ）。reviews/<int:pk>/ より前に置きパス取り違えを防ぐ
    # （/report/ まで含むため実際には衝突しないが、規約として詳細URLより前に置く）。
    path(
        "reviews/<int:pk>/report/",
        api_views.ReviewReportCreateView.as_view(),
        name="api_review_report",
    ),
    # 自分の口コミ削除（DELETE のみ。他人/不存在は 404）。
    path(
        "reviews/<int:pk>/",
        api_views.ReviewDestroyView.as_view(),
        name="api_review_delete",
    ),
    # 商品別の口コミ一覧（公開・承認済みのみ・新しい順）。
    # products/<int:pk>/ 詳細URL とはパスが異なるため衝突しない。
    path(
        "products/<int:product_id>/reviews/",
        api_views.ProductReviewListView.as_view(),
        name="api_product_reviews",
    ),
    # ===== 使用記録（ProductUseLog）。すべてログイン必須。 =====
    # 商品別の使用記録 一覧(GET)＋投稿(POST)。
    path(
        "products/<int:product_id>/use-logs/",
        api_views.ProductUseLogListCreateView.as_view(),
        name="api_product_use_logs",
    ),
    # 使用記録の通報（POST のみ）。use-logs/<int:pk>/ より前に置き取り違えを防ぐ。
    path(
        "use-logs/<int:pk>/report/",
        api_views.ProductUseLogReportCreateView.as_view(),
        name="api_use_log_report",
    ),
    # 自分の使用記録の削除（DELETE のみ。他人/不存在は 404）。
    path(
        "use-logs/<int:pk>/",
        api_views.ProductUseLogDestroyView.as_view(),
        name="api_use_log_delete",
    ),
]
