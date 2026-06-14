"""/api/ 配下の集約ルーター (Phase 2: 認証)。

config/urls.py から `path("api/", include("config.api_urls"))` でマウントされる。
catch-all（apps.products の <uslug:slug>/）より必ず前に配置すること。
"""
from django.urls import include, path

from apps.accounts.api_views import (
    DeviceRegisterView,
    MeView,
    MissionListView,
)

urlpatterns = [
    path("auth/", include("apps.accounts.api_urls")),  # signup / login / refresh
    path("me/", MeView.as_view(), name="api_me"),
    path("missions/", MissionListView.as_view(), name="api_missions"),
    path("devices/", DeviceRegisterView.as_view(), name="api_devices"),
    path("", include("apps.products.api_urls")),  # categories / products / search / detail
    path("", include("apps.reviews.api_urls")),  # reviews(投稿) / reviews/my(履歴)
]
