"""ネイティブアプリ連携API用シリアライザ（お問い合わせ）。

Web版の ContactForm（ハニーポット/送信時刻チェック付き ModelForm）は JSON API には
不向きなため、アプリ用に専用の Serializer を定義する。受け取った category/message は
既存 ContactMessage モデルへマッピングして保存する（マイグレーション不要の暫定方式）。
エラー文言はアプリ仕様の固定文言に揃える。
"""
from rest_framework import serializers

from .models import LegalDocument


class LegalDocumentSerializer(serializers.ModelSerializer):
    """GET /api/legal/ ・ /api/legal/<doc_type>/ の出力。

    WEBと同一の単一ソース(LegalDocument)を返す。アプリは body_html を WebView/HTML
    レンダラで、もしくは body_text(タグ除去済プレーンテキスト)で表示できる。
    内容のズレを無くすことが目的のため、本文・改定日・タイトルを揃えて返す。
    """

    type = serializers.CharField(source="doc_type")
    type_label = serializers.CharField(source="get_doc_type_display")
    body_html = serializers.CharField(source="body")
    body_text = serializers.CharField()

    class Meta:
        model = LegalDocument
        fields = [
            "type", "type_label", "eyebrow", "title",
            "body_html", "body_text",
            "enacted_on", "revised_on", "updated_at",
        ]


# アプリ仕様の6種別。コード→日本語ラベル。subject への埋め込みと管理メモに使う。
CONTACT_CATEGORIES = [
    ("general", "一般的なお問い合わせ"),
    ("bug", "不具合報告"),
    ("review", "口コミ・投稿について"),
    ("rights", "権利侵害・削除依頼"),
    ("privacy", "個人情報について"),
    ("other", "その他"),
]
CONTACT_CATEGORY_LABELS = dict(CONTACT_CATEGORIES)


class ContactSerializer(serializers.Serializer):
    """POST /api/contact/ の入力検証。

    name は任意（100字）。email/category/message は必須。message は5000字以内。
    Web版の EmailField と同等の形式チェックを DRF の EmailField で行う。
    """

    name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        error_messages={"max_length": "お名前は100文字以内で入力してください。"},
    )
    email = serializers.EmailField(
        max_length=254,
        error_messages={
            "required": "メールアドレスを入力してください。",
            "blank": "メールアドレスを入力してください。",
            "invalid": "有効なメールアドレスを入力してください。",
            "max_length": "メールアドレスは254文字以内で入力してください。",
        },
    )
    category = serializers.ChoiceField(
        choices=[c[0] for c in CONTACT_CATEGORIES],
        error_messages={
            "required": "お問い合わせ種別を選択してください。",
            "blank": "お問い合わせ種別を選択してください。",
            "invalid_choice": "お問い合わせ種別を選択してください。",
        },
    )
    message = serializers.CharField(
        max_length=5000,
        error_messages={
            "required": "お問い合わせ内容を入力してください。",
            "blank": "お問い合わせ内容を入力してください。",
            "max_length": "お問い合わせ内容は5000文字以内で入力してください。",
        },
    )

    def validate_message(self, value):
        # 空白のみの内容も未入力として扱う。
        if not value.strip():
            raise serializers.ValidationError("お問い合わせ内容を入力してください。")
        return value
