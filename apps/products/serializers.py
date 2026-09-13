"""ネイティブアプリ連携API用シリアライザ (Phase 3: 商品・カテゴリ)。

既存の Web 用 views.py / models.py には一切手を加えず、API 専用にここで定義する。
すべて読み取り専用。

アフィリエイト系URL（official_url / affiliate_url / rakuten_url / amazon_url）は
商品詳細API（ProductDetailSerializer）でのみ返す。一覧/検索（ProductListSerializer）
には含めない。アプリ側は値があるURLだけボタン表示し、「PR / アフィリエイトリンクを
含みます」表記を必ず添える想定。Yahoo!ショッピングURLはモデルに存在しないため返さない。
"""
from rest_framework import serializers

from . import spec_schema
from .models import Category, Product


def _abs_media_url(field_file, external_url, request):
    """画像の絶対URLを返す。アプリから直接開ける形式にする。

    - ImageField(image) があればその URL を採用。
    - 無ければ外部URL(image_url)。WP移行データ等で "/media/..." という
      サイト相対パスが入っている場合があるため、"/" 始まりは絶対URL化する。
    - http(s):// で始まる外部絶対URLはそのまま返す。
    - どちらも無ければ None。
    """
    if field_file:
        url = field_file.url
    elif external_url:
        url = external_url
    else:
        return None
    if url.startswith("/") and request is not None:
        return request.build_absolute_uri(url)
    return url


class CategoryMiniSerializer(serializers.ModelSerializer):
    """商品にぶら下げる軽量カテゴリ表現。"""

    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class CategorySerializer(serializers.ModelSerializer):
    """GET /api/categories/ 用。

    ※ Category には is_published 等の公開フラグが存在しない。
      可視性に関わるフィールドは show_in_header のみ（ヘッダーナビ表示可否）。
    image_url は image(アップロード) を優先し、無ければ外部 image_url を返す。
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "image_url", "sort_order")

    def get_image_url(self, obj):
        return _abs_media_url(obj.image, obj.image_url, self.context.get("request"))


class ProductListSerializer(serializers.ModelSerializer):
    """商品一覧・検索用。アフィリエイトURLは含めない。

    is_discontinued:
      生産終了フラグ(Webの「生産終了」バッジと同一ソース)。アプリ側は true の
      商品にバッジ表示する想定。生産終了でも公開中(is_published=True)なら返る。
    """

    image_url = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    product_type = CategoryMiniSerializer(read_only=True)
    categories = CategoryMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "brand",
            "price",
            "image_url",
            "average_rating",
            "review_count",
            "product_type",
            "categories",
            "is_discontinued",
        )

    def get_image_url(self, obj):
        return _abs_media_url(obj.image, obj.image_url, self.context.get("request"))

    def get_average_rating(self, obj):
        # ビュー側で annotate(avg_rating=...) 済み。未集計時/レビュー無しは 0。
        val = getattr(obj, "avg_rating", None)
        return round(val, 1) if val is not None else 0

    def get_review_count(self, obj):
        return getattr(obj, "review_count_annot", 0) or 0


class ProductDetailSerializer(ProductListSerializer):
    """商品詳細用。一覧項目に説明・特徴・スペックと購入/アフィリエイトURLを追加。

    購入系URLはモデル既存フィールド名をそのまま使う（新フィールドは作らない）:
      - official_url  : 公式サイトURL
      - affiliate_url : アフィリエイトURL（PC版では主ボタン「公式サイトで見る」）
      - rakuten_url   : 楽天URL（「楽天で見る」）
      - amazon_url    : AmazonURL（「Amazonで見る」）
    値が無い商品では空文字で返る（URLField(blank=True)）。アプリ側は非空のものだけ
    ボタン表示する。この詳細APIのみに含め、一覧/検索には返さない。

    spec_table:
      製品タイプ別スキーマ(spec_schema)で整形済みの仕様表。アプリはこれをそのまま
      セクション表示できる。形式:
        [{"group":"基本情報",
          "rows":[{"key","label","value","unit","is_url"}, ...]}, ...]
      - label は日本語表示名、value は表示用文字列、unit は補足単位(値に内包済みなら空)
      - is_url=true の行(メーカー公式)はリンクとして描画する想定
      - 値のある項目だけが入る。未対応カテゴリや未収集商品では空配列。
    specifications:
      正規化キーの生スペック(内部メモ _internal は除外)。独自表示したいアプリ向け。
    discontinued_at:
      生産終了日(YYYY-MM-DD)。未設定なら null。is_discontinued=true でも日付
      未入力の商品はあるため、表示は is_discontinued を主・日付を補足にする。
    """

    specifications = serializers.SerializerMethodField()
    spec_table = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description",
            "features",
            "specifications",
            "spec_table",
            "official_url",
            "affiliate_url",
            "rakuten_url",
            "amazon_url",
            "discontinued_at",
        )

    def get_specifications(self, obj):
        return spec_schema.public_specifications(obj.specifications)

    def get_spec_table(self, obj):
        slug = obj.product_type.slug if obj.product_type_id else None
        specs = obj.specifications if isinstance(obj.specifications, dict) else {}
        return spec_schema.spec_table_data(slug, specs)
