"""ネイティブアプリ連携API用シリアライザ (Phase 2: 認証)。

既存の Web 用 forms.py / views.py には一切手を加えず、API 専用にここで定義する。
User モデルは既存定義をそのまま利用（変更しない）。
"""
from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class SignupSerializer(serializers.Serializer):
    """会員登録（API）。

    既存の SignUpForm と同等の項目を扱うが、UserCreationForm ではなく
    DRF の Serializer として実装し、User 作成は create_user を使う。
    ※ hair_type は User モデルに存在しないため受け付けない（既存に合わせる）。
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    nickname = serializers.CharField(max_length=50, required=False, allow_blank=True)
    age_range = serializers.ChoiceField(
        choices=User._meta.get_field("age_range").choices,
        required=False,
        allow_blank=True,
    )
    skin_type = serializers.ChoiceField(
        choices=User._meta.get_field("skin_type").choices,
        required=False,
        allow_blank=True,
    )

    def validate_email(self, value):
        # email は一意。大文字小文字を区別せず重複チェック。
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("このメールアドレスは既に登録されています。")
        return value

    def validate_password(self, value):
        # Django 標準のパスワードバリデーション（settings の AUTH_PASSWORD_VALIDATORS）を通す。
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        # 既存 Web と同様に username=email を設定（USERNAME_FIELD は email だが
        # AbstractUser の username は必須・一意のため埋める）。
        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            nickname=validated_data.get("nickname", ""),
            age_range=validated_data.get("age_range", ""),
            skin_type=validated_data.get("skin_type", ""),
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """/api/me/ 用。既存 User の cached_property をそのまま読む。"""

    avatar_url = serializers.SerializerMethodField()
    category_badge = serializers.SerializerMethodField()
    review_level = serializers.IntegerField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    helpful_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nickname",
            "age_range",
            "skin_type",
            "review_level",
            "category_badge",
            "review_count",
            "helpful_count",
            "avatar_url",
            "email_verified",
        )
        read_only_fields = fields

    def get_avatar_url(self, obj):
        # avatar 未設定なら null。設定済みなら絶対URLで返す（アプリから開けるように）。
        if not obj.avatar:
            return None
        url = obj.avatar.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_category_badge(self, obj):
        # 既存 cached_property。該当なしは None を返す仕様なのでそのまま透過。
        return obj.category_badge


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """email + password でログイン。

    SimpleJWT の TokenObtainPairSerializer は username_field を
    User.USERNAME_FIELD（= "email"）から自動取得するため、追加設定なしで
    email ログインになる。レスポンスに user 情報も添える。
    """

    def validate(self, attrs):
        data = super().validate(attrs)  # access / refresh を生成
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data
