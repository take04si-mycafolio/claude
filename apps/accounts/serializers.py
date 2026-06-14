"""ネイティブアプリ連携API用シリアライザ (Phase 2: 認証)。

既存の Web 用 forms.py / views.py には一切手を加えず、API 専用にここで定義する。
User モデルは既存定義をそのまま利用（変更しない）。
"""
from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Device, User


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


# =============================================================================
# ミッション/キャンペーン (Phase 5) ※読み取り専用
#   既存の missions.user_mission_overview(user) が返す dict をそのまま整形する。
#   ロジックは一切再実装せず、構造化だけを担う。
# =============================================================================
class MissionStepSerializer(serializers.Serializer):
    """evaluate_mission が返す step dict を整形。"""

    label = serializers.CharField()
    current = serializers.IntegerField()
    target = serializers.IntegerField()
    is_done = serializers.BooleanField()
    percent = serializers.IntegerField()


class MissionSerializer(serializers.Serializer):
    """user_mission_overview(user) の各 dict を整形。

    すべて request.user 視点で計算済みの値であり、他ユーザーの情報は含まない。
    reward_code は「そのユーザー自身に発行された」コードのみ（達成時のみ非空）。
    """

    id = serializers.IntegerField(source="mission.id")
    title = serializers.CharField(source="mission.title")
    description = serializers.CharField(source="mission.description")
    reward_label = serializers.CharField(source="mission.reward_label")
    is_active = serializers.BooleanField(source="mission.is_active")
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    not_started = serializers.BooleanField()
    ended = serializers.BooleanField()

    # 参加ランク条件
    min_review_level = serializers.IntegerField(source="min_level")
    max_review_level = serializers.IntegerField(source="max_level")
    level_label = serializers.CharField()
    is_eligible = serializers.BooleanField(source="eligible")
    below_level = serializers.BooleanField()
    above_level = serializers.BooleanField()

    # 進捗・達成
    progress = serializers.IntegerField(source="percent")
    steps = MissionStepSerializer(many=True)
    is_completed = serializers.BooleanField(source="is_complete")
    completed_at = serializers.SerializerMethodField()

    # 特典（本人分のみ）
    reward_status = serializers.CharField(source="status", allow_blank=True)
    reward_code = serializers.CharField(allow_blank=True)
    code_pending = serializers.BooleanField()
    missed = serializers.BooleanField()

    # 先着・数量限定
    limit = serializers.IntegerField(allow_null=True)
    remaining = serializers.IntegerField(allow_null=True)
    sold_out = serializers.BooleanField()

    def get_completed_at(self, obj):
        completion = obj.get("completion")
        return completion.completed_at if completion is not None else None


# =============================================================================
# 端末登録 / プッシュ通知トークン (Phase 6)
#   POST /api/devices/ で Expo Push Token を登録・更新する。
#   user は request.user を View 側で付与するため入力では受け取らない。
#   push_token は通知用トークンのため一覧返却はしない（登録レスポンスのみ）。
# =============================================================================
PLATFORM_CHOICES = ("ios", "android", "web")


class DeviceRegisterSerializer(serializers.ModelSerializer):
    """端末（通知先）の登録・更新用。

    入力: platform / push_token / app_version(任意) / device_name(任意)
    出力: 自分の端末レコードの安全な項目のみ。
    """

    platform = serializers.ChoiceField(choices=PLATFORM_CHOICES)

    class Meta:
        model = Device
        fields = [
            "id",
            "platform",
            "push_token",
            "app_version",
            "device_name",
            "is_active",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]

    def validate_push_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("push_token は必須です。")
        return value
