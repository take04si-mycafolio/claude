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
    # 表示用に追加（read-only）。display_name は nickname 優先、無ければ email。
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "display_name",
            "nickname",
            "bio",
            "gender",
            "age_range",
            "skin_type",
            "hair_type",
            "review_level",
            "category_badge",
            "review_count",
            "helpful_count",
            "avatar_url",
            "email_verified",
            "created_at",
        )
        read_only_fields = fields

    def get_display_name(self, obj):
        # Web の {{ user.nickname|default:user.email }} と同義の表示名。
        return obj.nickname or obj.email

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


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/me/ 用。アプリのプロフィール編集で更新できる安全項目のみ。

    Web の ProfileEditForm のうち、画像(avatar)や SNS リンクを除いた
    nickname / bio / age_range / skin_type / hair_type / gender の6項目だけを許可する。
    email / password / avatar / review_level / category_badge / email_verified
    などはフィールドに含めないため、リクエストに混入しても無視される（更新されない）。
    更新対象は常に View が渡す request.user 自身のみ（他ユーザーは指定不可）。

    choices・空文字可否は既存 User モデル定義（= Web の ProfileEditForm）に合わせる:
      - 6項目すべて model 側 blank=True のため allow_blank=True（空文字で消去可）。
      - age_range / skin_type / hair_type / gender は TextChoices を choices に流用し、
        範囲外の値は 400 を返す。
      - nickname(max_length=50) / bio(max_length=300) は超過で 400。
    PATCH のため required=False（送られた項目だけ部分更新）。
    """

    nickname = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    bio = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )
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
    hair_type = serializers.ChoiceField(
        choices=User._meta.get_field("hair_type").choices,
        required=False,
        allow_blank=True,
    )
    gender = serializers.ChoiceField(
        choices=User._meta.get_field("gender").choices,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = User
        fields = ("nickname", "bio", "age_range", "skin_type", "hair_type", "gender")


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

    # アプリのミッション一覧向け 互換フィールド（read-only, 既存値から導出）
    #   既存フィールドは一切変更せず、追加のみ。Web版はシリアライザ非経由のため無影響。
    status = serializers.SerializerMethodField()
    condition_text = serializers.SerializerMethodField()
    current = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    # プレゼント補足文（PC版 templates/accounts/missions.html の固定表示と同一文言）
    reward_condition_text = serializers.SerializerMethodField()

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

    def get_status(self, obj):
        """進捗状態を単一文字列で返す（既存の真偽フラグから導出）。"""
        if obj.get("not_started"):
            return "not_started"
        if obj.get("ended"):
            return "ended"
        if obj.get("is_complete"):
            return "completed"
        return "in_progress"

    def get_condition_text(self, obj):
        """達成条件を steps[].label を「／」で結合した文章として返す。"""
        steps = obj.get("steps") or []
        labels = [
            str(s.get("label")) for s in steps
            if isinstance(s, dict) and s.get("label")
        ]
        return "／".join(labels)

    def get_current(self, obj):
        """全ステップの現在値の合計（steps 欠落・値欠けでも例外にしない）。"""
        steps = obj.get("steps") or []
        return sum(
            (s.get("current") or 0) for s in steps if isinstance(s, dict)
        )

    def get_target(self, obj):
        """全ステップの目標値の合計（steps 欠落・値欠けでも例外にしない）。"""
        steps = obj.get("steps") or []
        return sum(
            (s.get("target") or 0) for s in steps if isinstance(s, dict)
        )

    def get_reward_condition_text(self, obj):
        """プレゼントの受け取り条件の補足文。

        モデルには保存されておらず、PC版Web（templates/accounts/missions.html）で
        固定文として表示されている文言と同一の定数を表示用に返す（read-only）。
        """
        return "すべてのアクションを達成すると受け取れます。"


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
