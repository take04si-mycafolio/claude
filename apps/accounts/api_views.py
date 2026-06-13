"""ネイティブアプリ連携API用ビュー (Phase 2: 認証)。

既存の Web 用 views.py には手を加えず、API 専用にここで定義する。
認証は JWT（settings の DEFAULT_AUTHENTICATION_CLASSES = JWTAuthentication）。
"""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CustomTokenObtainPairSerializer,
    MissionSerializer,
    SignupSerializer,
    UserSerializer,
)


class SignupView(APIView):
    """POST /api/auth/signup/ — 会員登録。

    成功時 201 で user とトークン(access/refresh)を返す。

    既存 Web 仕様との差異（Phase 2 時点）:
      - 既存 Web の signup は確認メールを送信し、session login する。
      - 本 API では確認メールは送信しない（send_mail は fail_silently=False で
        SMTP 失敗時に 500 になり得るため、Phase 2 では切り離す）。
      - email_verified は既存と同じく False のまま（本登録は別フローで対応予定）。
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        data = {
            "user": UserSerializer(user, context={"request": request}).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
        return Response(data, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — email + password で JWT を発行。"""

    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class MeView(APIView):
    """GET /api/me/ — ログイン中ユーザーの情報を返す。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(serializer.data)


class MissionListView(APIView):
    """GET /api/missions/ — ログインユーザーが参加可能なミッション一覧。

    既存の missions.user_mission_overview(user) をそのまま使用（ロジック流用）。
    Web のミッションページと同じく request.user 視点で評価し、達成分は確定する。
    開催中（未終了・開始済み）のミッションを上位に並べる。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .missions import user_mission_overview

        overview = user_mission_overview(request.user)
        # 開催中を優先: 終了済み→最後、未開始→後ろ、あとは既定の order, id 順を維持。
        overview.sort(
            key=lambda d: (
                d["ended"],
                d["not_started"],
                d["mission"].order,
                d["mission"].id,
            )
        )
        serializer = MissionSerializer(
            overview, many=True, context={"request": request}
        )
        return Response(serializer.data)
