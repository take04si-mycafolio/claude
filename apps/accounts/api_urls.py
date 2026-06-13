"""accounts アプリの API ルート (Phase 2: 認証)。

config/api_urls.py から `path("auth/", include("apps.accounts.api_urls"))` で
マウントされる。namespace は設けず（既存 accounts namespace と分離）フラットに定義。
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api_views

urlpatterns = [
    path("signup/", api_views.SignupView.as_view(), name="api_signup"),
    path("login/", api_views.CustomTokenObtainPairView.as_view(), name="api_login"),
    path("refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
]
