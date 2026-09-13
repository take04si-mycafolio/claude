"""/api/ 配下の集約ルーター (Phase 2: 認証)。

config/urls.py から `path("api/", include("config.api_urls"))` でマウントされる。
catch-all（apps.products の <uslug:slug>/）より必ず前に配置すること。
"""
from django.urls import include, path

from apps.accounts.api_views import (
    DeviceRegisterView,
    MeView,
    MissionListView,
    PublicUserDetailView,
    UserBookmarkListView,
    UserPhotoListView,
    UserReviewListView,
)
from apps.pages.api_views import (
    ContactCreateAPIView,
    LegalDocumentDetailAPIView,
    LegalDocumentListAPIView,
)

urlpatterns = [
    path("auth/", include("apps.accounts.api_urls")),  # signup / login / refresh
    path("contact/", ContactCreateAPIView.as_view(), name="api_contact"),  # 問い合わせ(未ログイン可)
    # 規約・ポリシー(WEBと同一の単一ソースを返す・未ログイン可)
    path("legal/", LegalDocumentListAPIView.as_view(), name="api_legal_list"),
    path("legal/<slug:doc_type>/", LegalDocumentDetailAPIView.as_view(), name="api_legal_detail"),
    path("me/", MeView.as_view(), name="api_me"),
    path("missions/", MissionListView.as_view(), name="api_missions"),
    path("devices/", DeviceRegisterView.as_view(), name="api_devices"),
    # 公開ユーザーページ（他ユーザーから閲覧可・ログイン不要）。
    path("users/<int:pk>/", PublicUserDetailView.as_view(), name="api_user_detail"),
    path("users/<int:pk>/reviews/", UserReviewListView.as_view(), name="api_user_reviews"),
    path("users/<int:pk>/photos/", UserPhotoListView.as_view(), name="api_user_photos"),
    path("users/<int:pk>/bookmarks/", UserBookmarkListView.as_view(), name="api_user_bookmarks"),
    path("", include("apps.products.api_urls")),  # categories / products / search / detail
    path("", include("apps.reviews.api_urls")),  # reviews(投稿) / reviews/my(履歴)
]
