"""ネイティブアプリ連携API用ビュー（お問い合わせ）。

POST /api/contact/ — 未ログインでも送信可。ログイン中は送信者情報を管理メモへ記録する
（ContactMessage に user FK を追加しない暫定方式）。受け取った category/message は
Web版と同じ ContactMessage へ保存し、Web版と同じ通知ロジックで管理者にメール通知する。

セキュリティ: token・問い合わせ本文・個人情報をログには出さない（保存は管理画面用のDBのみ）。
"""
from django.http import Http404

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_serializers import (
    CONTACT_CATEGORY_LABELS,
    ContactSerializer,
    LegalDocumentSerializer,
)
from .models import ContactMessage, LegalDocument
from .views import _get_ip, _try_notify_admin


class LegalDocumentListAPIView(generics.ListAPIView):
    """GET /api/legal/ — 公開中の規約・ポリシーを一括取得(本文含む)。

    アプリ起動時にまとめて取得・キャッシュする用途。未ログイン可。
    """

    permission_classes = [AllowAny]
    serializer_class = LegalDocumentSerializer
    pagination_class = None

    def get_queryset(self):
        return LegalDocument.objects.filter(is_published=True).order_by("doc_type")


class LegalDocumentDetailAPIView(generics.RetrieveAPIView):
    """GET /api/legal/<type>/ — 種別(terms/privacy/community)を1件取得。未ログイン可。"""

    permission_classes = [AllowAny]
    serializer_class = LegalDocumentSerializer
    lookup_field = "doc_type"
    lookup_url_kwarg = "doc_type"

    def get_queryset(self):
        return LegalDocument.objects.filter(is_published=True)


class ContactCreateAPIView(APIView):
    """POST /api/contact/ — アプリからのお問い合わせを受け付ける。

    成功時 201 {"message": "お問い合わせを受け付けました。"}。
    入力不正は serializer 検証で 400（{"email": [...], "message": [...]} 形式）。
    未ログイン可（AllowAny）。ログイン中は admin_notes に送信者を記録する。
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        category = data["category"]
        label = CONTACT_CATEGORY_LABELS.get(category, category)

        # category はモデルに専用フィールドが無いため、件名にラベルを埋め込んで
        # 管理画面で種別が分かるようにする（暫定方式・マイグレーション不要）。
        subject = f"【アプリ/{label}】お問い合わせ"

        # ログイン中なら送信者を管理メモに記録（user FK は持たないため文字列で残す）。
        # ログには出さず、管理画面でのみ参照できるDBの admin_notes に保存する。
        notes = [f"アプリからの送信 / 種別コード: {category}"]
        user = request.user if request.user.is_authenticated else None
        if user is not None:
            nickname = getattr(user, "nickname", "") or user.get_username()
            notes.append(
                f"ログインユーザー: {nickname} (id={user.id}, {user.email})"
            )
        admin_notes = "\n".join(notes)

        cm = ContactMessage(
            name=data.get("name", "") or "",
            email=data["email"],
            subject=subject,
            body=data["message"],
            admin_notes=admin_notes,
        )
        cm.ip = _get_ip(request)
        cm.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        cm.save()

        # Web版と同じ宛先・同じロジックで管理者通知（fail_silently のため送信失敗でも例外なし）。
        _try_notify_admin(cm, request)

        return Response(
            {"message": "お問い合わせを受け付けました。"},
            status=status.HTTP_201_CREATED,
        )
