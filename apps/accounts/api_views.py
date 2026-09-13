"""ネイティブアプリ連携API用ビュー (Phase 2: 認証)。

既存の Web 用 views.py には手を加えず、API 専用にここで定義する。
認証は JWT（settings の DEFAULT_AUTHENTICATION_CLASSES = JWTAuthentication）。
"""
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.reviews.api_views import MyReviewPagination

from .models import User
from .serializers import (
    CustomTokenObtainPairSerializer,
    DeviceRegisterSerializer,
    MissionSerializer,
    ProfileUpdateSerializer,
    PublicBookmarkSerializer,
    PublicUserPhotoSerializer,
    PublicUserSerializer,
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
    """/api/me/ — ログイン中ユーザー（request.user）自身の情報。

    GET   : プロフィール表示用の項目を返す（従来通り・変更なし）。
    PATCH : プロフィールの安全な5項目のみ部分更新する。
            更新対象は常に request.user。他ユーザーは指定できない。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        # request.user のみを更新対象にする（他人のユーザーは指定不可）。
        # partial=True で送られた項目だけ部分更新。未許可項目は無視される。
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)  # 不正値は 400
        serializer.save()
        # 更新後は GET と同等の最新 UserSerializer を返す。
        return Response(
            UserSerializer(request.user, context={"request": request}).data
        )


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


def _get_public_user_or_404(request, pk):
    """公開ユーザーページの対象を取得する。PC版 user_detail と同じ可視性ルール。

    - 不存在は 404。
    - 他人の staff/superuser ページは 404（自分自身のページは閲覧可）。
    - is_active=False（WP取り込みの投稿者アカウント等）は閲覧可（PC版と同じ）。
    """
    user = get_object_or_404(User, pk=pk)
    is_own = request.user.is_authenticated and request.user.pk == user.pk
    if not is_own and (user.is_staff or user.is_superuser):
        raise Http404("ページが見つかりません")
    return user


class PublicUserDetailView(APIView):
    """GET /api/users/<id>/ — 他ユーザーから見える公開プロフィール。

    ログイン不要（PC版 user_detail と同じく公開）。email 等の非公開情報は返さない。
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        user = _get_public_user_or_404(request, pk)
        return Response(
            PublicUserSerializer(user, context={"request": request}).data
        )


class UserReviewListView(ListAPIView):
    """GET /api/users/<id>/reviews/ — 指定ユーザーの承認済み口コミ（新しい順・ページング）。

    商品名/商品画像/投稿写真URL付き。reviews アプリの ReviewListSerializer を再利用する。
    """

    permission_classes = [AllowAny]
    pagination_class = MyReviewPagination

    def get_serializer_class(self):
        from apps.reviews.serializers import ReviewListSerializer
        return ReviewListSerializer

    def get_queryset(self):
        from apps.reviews.models import Review
        user = _get_public_user_or_404(self.request, self.kwargs["pk"])
        return (
            Review.objects.filter(user=user, is_approved=True)
            .select_related("product")
            .prefetch_related("images")  # image_urls の N+1 回避
            .annotate(image_count_annot=Count("images"))
            .order_by("-created_at")
        )


class UserPhotoListView(ListAPIView):
    """GET /api/users/<id>/photos/ — 指定ユーザーの投稿写真（新しい順・ページング）。"""

    permission_classes = [AllowAny]
    serializer_class = PublicUserPhotoSerializer
    pagination_class = MyReviewPagination

    def get_queryset(self):
        from apps.reviews.models import ReviewImage
        user = _get_public_user_or_404(self.request, self.kwargs["pk"])
        return (
            ReviewImage.objects.filter(
                review__user=user, review__is_approved=True
            )
            .select_related("review", "review__product")
            .order_by("-id")
        )


class UserBookmarkListView(ListAPIView):
    """GET /api/users/<id>/bookmarks/ — 指定ユーザーの「気になる」商品（新しい順・ページング）。"""

    permission_classes = [AllowAny]
    serializer_class = PublicBookmarkSerializer
    pagination_class = MyReviewPagination

    def get_queryset(self):
        user = _get_public_user_or_404(self.request, self.kwargs["pk"])
        return (
            user.bookmarks
            .select_related("product", "product__product_type")
            .order_by("-created_at")
        )


class DeviceRegisterView(APIView):
    """POST /api/devices/ — Expo Push Token 等の通知先端末を登録/更新する。

    同じ (request.user, push_token) が既に存在すれば新規作成せず更新（upsert）。
    更新項目: platform / app_version / device_name / is_active(True) /
    last_seen_at・updated_at(auto_now)。

    他ユーザーの端末は参照・操作不可（常に request.user に紐づけて検索する）。
    新規作成時は 201、既存更新時は 200 を返し、レスポンスに created を含める。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        device, created = request.user.devices.update_or_create(
            push_token=data["push_token"],
            defaults={
                "platform": data["platform"],
                "app_version": data.get("app_version", ""),
                "device_name": data.get("device_name", ""),
                "is_active": True,
            },
        )

        out = DeviceRegisterSerializer(device, context={"request": request}).data
        out["created"] = created
        return Response(
            out,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
