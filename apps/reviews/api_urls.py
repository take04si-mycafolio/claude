"""reviews アプリの API ルート (Phase 4: 口コミ投稿 第1段階)。

config/api_urls.py から include される。
重要: reviews/my/ は将来 reviews/<...> の詳細URLを追加する場合に備え、
必ず詳細URLより前に置く（my が pk 等に飲まれないようにする）。
"""
from django.urls import path

from . import api_views

urlpatterns = [
    # my/ を先に登録（将来の reviews/<pk>/ 追加時の取り違え防止）。
    path("reviews/my/", api_views.MyReviewListView.as_view(), name="api_my_reviews"),
    path("reviews/", api_views.ReviewCreateView.as_view(), name="api_review_create"),
]
