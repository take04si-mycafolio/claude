from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    """階層型カテゴリ。parent=NULL は製品タイプ（美顔器、ドライヤー等）"""

    name = models.CharField("カテゴリ名", max_length=500, unique=True)
    slug = models.SlugField("スラッグ", max_length=500, unique=True, allow_unicode=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="親カテゴリ (製品タイプ)",
    )
    description = models.TextField("説明", blank=True)
    image = models.ImageField(
        "カテゴリ画像(イラスト等)", upload_to="categories/",
        blank=True, null=True,
        help_text="カテゴリTOPに表示するイラスト・アイキャッチ画像"
    )
    image_url = models.URLField(
        "カテゴリ画像URL", max_length=500, blank=True,
        help_text="外部URLで画像を指定する場合に使用(image欄が空のとき有効)"
    )
    landing_html = models.TextField(
        "ランディングHTML(SEO)", blank=True,
        help_text="カテゴリTOPのSEOランディングページのHTML本文。空ならデフォルト表示"
    )
    meta_title = models.CharField("SEOタイトル", max_length=200, blank=True)
    meta_description = models.CharField("SEOディスクリプション", max_length=300, blank=True)
    sort_order = models.IntegerField("表示順", default=0)
    show_in_header = models.BooleanField(
        "ヘッダーに表示", default=True,
        help_text="OFFにするとヘッダーのカテゴリナビから非表示になります"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "カテゴリ"
        verbose_name_plural = "カテゴリ"
        ordering = ["sort_order", "name"]

    def __str__(self):
        if self.parent_id:
            return f"{self.parent.name} > {self.name}"
        return self.name

    @property
    def is_product_type(self):
        return self.parent_id is None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField("商品名", max_length=500)
    slug = models.SlugField("スラッグ", max_length=500, unique=True, allow_unicode=True)
    brand = models.CharField("メーカー", max_length=500, blank=True)
    product_type = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products_of_type",
        verbose_name="製品タイプ",
        help_text="美顔器、ドライヤー等の製品タイプ",
        limit_choices_to={"parent__isnull": True},
    )
    categories = models.ManyToManyField(
        Category, related_name="products", blank=True, verbose_name="機能カテゴリ"
    )
    price = models.PositiveIntegerField("参考価格(円)", null=True, blank=True)
    image = models.ImageField("画像", upload_to="products/", blank=True, null=True)
    image_url = models.URLField("画像URL(外部)", max_length=1000, blank=True)
    description = models.TextField("商品説明", blank=True)
    features = models.TextField("特徴", blank=True, help_text="箇条書きで記載")
    official_url = models.URLField("公式サイトURL", max_length=1000, blank=True)
    affiliate_url = models.URLField("アフィリエイトURL", max_length=1000, blank=True)
    rakuten_url = models.URLField("楽天URL", max_length=1000, blank=True)
    amazon_url = models.URLField("AmazonURL", max_length=1000, blank=True)
    # ===== EC API 連携 (Amazon / 楽天) =====
    asin = models.CharField("Amazon ASIN", max_length=20, blank=True, db_index=True, null=True)
    rakuten_item_code = models.CharField("楽天 itemCode", max_length=100, blank=True, db_index=True)
    amazon_synced_at = models.DateTimeField("Amazon 同期日時", null=True, blank=True)
    rakuten_synced_at = models.DateTimeField("楽天 同期日時", null=True, blank=True)
    api_data = models.JSONField("API 生データ", default=dict, blank=True,
                                help_text="Amazon/楽天 APIレスポンス保管(画像複数・スペック等)")
    source = models.CharField("登録経路", max_length=20, default="manual",
                              choices=[("manual","手動"),("amazon","Amazon"),("rakuten","楽天"),("wp","WP移行")])
    wp_post_id = models.IntegerField(
        "WordPress投稿ID", null=True, blank=True, unique=True
    )
    specifications = models.JSONField(
        "スペック", default=dict, blank=True,
        help_text='構造化スペック例: {"weight": "300g", "size": "100x50mm", "battery": "2400mAh"}'
    )
    cautions = models.TextField(
        "注意事項", blank=True,
        help_text="使用時の注意点・禁忌事項。AI記事生成時に必ず含める内容"
    )
    meta_title = models.CharField(
        "SEOタイトル(<title>)", max_length=100, blank=True,
        help_text="検索結果のタイトル(全角30文字程度推奨)。空欄なら商品名が使われます。"
    )
    meta_description = models.CharField(
        "SEOディスクリプション", max_length=200, blank=True,
        help_text="検索結果のスニペット(120-160文字推奨)。空欄なら商品説明の冒頭が使われます。"
    )
    last_verified_at = models.DateField(
        "最終確認日", null=True, blank=True,
        help_text="商品情報を公式から最終確認した日(古い情報での生成防止)"
    )
    sort_order = models.IntegerField("表示順", default=0, db_index=True)
    is_discontinued = models.BooleanField(
        "生産終了", default=False,
        help_text="チェックすると商品ページに「生産終了」表示+類似商品案内が出ます"
    )
    discontinued_at = models.DateField("生産終了日", null=True, blank=True)
    is_published = models.BooleanField("公開", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "美顔器"
        verbose_name_plural = "美顔器"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.product_type_id:
            return reverse("products:detail", kwargs={
                "type_slug": self.product_type.slug,
                "slug": self.slug,
            })
        return "/"

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        return self.image_url or ""

    def review_stats(self):
        stats = self.reviews.filter(is_approved=True).aggregate(
            avg=Avg("rating"), count=Count("id")
        )
        return {
            "average": round(stats["avg"], 1) if stats["avg"] else 0,
            "count": stats["count"] or 0,
        }


class Article(models.Model):
    """WordPressからインポートする記事コンテンツ (SEO用の読み物ページ)"""

    title = models.CharField("タイトル", max_length=500)
    slug = models.SlugField("スラッグ", max_length=500, unique=True, allow_unicode=True)
    content = models.TextField("本文(HTML)")
    excerpt = models.TextField("抜粋", blank=True)
    thumbnail = models.ImageField(
        "アイキャッチ画像", upload_to="articles/",
        blank=True, null=True,
        help_text="アップロード優先。空ならURL欄、それも空なら本文先頭の画像が使われます。"
    )
    thumbnail_url = models.URLField(
        "アイキャッチ画像URL", max_length=500, blank=True,
        help_text="外部URLを使う場合に入力。アップロード画像が優先されます。"
    )
    product_type = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="articles_in_type",
        verbose_name="カテゴリ(製品タイプ)",
        limit_choices_to={"parent__isnull": True},
    )
    seo_keyword = models.CharField(
        "SEOターゲットキーワード", max_length=100, blank=True,
        help_text="このページの主要キーワード。AI再生成時に使用"
    )
    meta_title = models.CharField(
        "SEOタイトル(<title>)", max_length=100, blank=True,
        help_text="検索結果のタイトル(全角30文字程度推奨)。空欄ならタイトルが使われます。"
    )
    meta_description = models.CharField(
        "SEOディスクリプション", max_length=200, blank=True,
        help_text="検索結果のスニペット(120-160文字推奨)。空欄なら抜粋が使われます。"
    )
    structured_data = models.TextField(
        blank=True,
        verbose_name="構造化データ(JSON-LD)",
        help_text="記事ページの head に script type=\"application/ld+json\" として出力されます。FAQPage / ItemList / Article 等のスキーマを記述してください。"
    )
    seo_check_result = models.JSONField(
        "SEO検査結果", default=dict, blank=True,
        help_text="改稿前後のSEO指標比較"
    )
    related_products = models.ManyToManyField(
        Product, related_name="articles", blank=True, verbose_name="関連商品"
    )
    wp_post_id = models.IntegerField("WordPress投稿ID", null=True, blank=True, unique=True)
    wp_author = models.CharField("WP投稿者", max_length=500, blank=True)
    published_at = models.DateTimeField("公開日", null=True, blank=True)
    is_published = models.BooleanField("公開", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "記事"
        verbose_name_plural = "記事"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def display_thumbnail(self):
        """アイキャッチ画像URLを返す。
        優先順位: アップロード画像 → 外部URL → 本文中の最初の<img>"""
        if self.thumbnail:
            try:
                return self.thumbnail.url
            except ValueError:
                pass
        if self.thumbnail_url:
            return self.thumbnail_url
        import re
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', self.content or "")
        if m:
            return m.group(1)
        return None

    def get_absolute_url(self):
        return reverse("products:article_detail", kwargs={"slug": self.slug})



class ApiCredential(models.Model):
    """EC API の認証情報。シングルトン(DB に 1 レコードのみ)。
    管理画面から編集可能。env 値があれば優先(フォールバック構造はサービス層で実装)。
    """
    # Amazon PA-API v5
    amazon_access_key = models.CharField("Amazon Access Key", max_length=100, blank=True)
    amazon_secret_key = models.CharField("Amazon Secret Key", max_length=200, blank=True)
    amazon_partner_tag = models.CharField(
        "Amazon Partner Tag", max_length=50, blank=True,
        help_text="Associates ID (例: mycafolio-22)",
    )
    amazon_marketplace = models.CharField(
        "マーケットプレイス", max_length=50, default="www.amazon.co.jp"
    )
    is_amazon_enabled = models.BooleanField("Amazon 連携を有効化", default=False)

    # 楽天市場 API
    rakuten_app_id = models.CharField("楽天 アプリID", max_length=100, blank=True)
    rakuten_access_key = models.CharField(
        "楽天 アクセスキー", max_length=200, blank=True,
        help_text="新Open API用 (pk_xxx形式)"
    )
    rakuten_affiliate_id = models.CharField(
        "楽天 アフィリエイトID", max_length=50, blank=True,
        help_text="アフィリエイトリンクが自動付与されます",
    )
    is_rakuten_enabled = models.BooleanField("楽天 連携を有効化", default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API 認証情報"
        verbose_name_plural = "API 認証情報"

    def __str__(self):
        flags = []
        if self.is_amazon_enabled:
            flags.append("Amazon✓")
        if self.is_rakuten_enabled:
            flags.append("楽天✓")
        return "API認証情報" + (" (" + " / ".join(flags) + ")" if flags else "")

    def save(self, *args, **kwargs):
        # シングルトン: 既存があれば常に上書き(pk=1)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 削除不可
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ArticleImage(models.Model):
    """記事内に挿入するイラスト・画像。Adminから記事ごとに管理。"""
    article = models.ForeignKey(
        'Article',
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='記事',
    )
    image = models.ImageField(upload_to='article-images/', verbose_name='画像')
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='代替テキスト(alt)')
    caption = models.CharField(max_length=200, blank=True, verbose_name='キャプション')
    order = models.PositiveIntegerField(default=0, verbose_name='並び順')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = '記事内画像'
        verbose_name_plural = '記事内画像'

    def __str__(self):
        return self.alt_text or (self.image.name if self.image else f"image#{self.pk}")


class SeoWeeklyReport(models.Model):
    # 期間
    period_start = models.DateField('期間開始')
    period_end = models.DateField('期間終了')
    generated_at = models.DateTimeField('生成日時', auto_now_add=True)

    # サマリ指標
    total_clicks = models.IntegerField('総クリック数', default=0)
    total_impressions = models.IntegerField('総表示回数', default=0)
    total_sessions = models.IntegerField('総セッション数', default=0)
    avg_ctr = models.FloatField('平均CTR(%)', default=0.0)
    avg_position = models.FloatField('平均掲載順位', default=0.0)

    # 前週比較
    clicks_change_pct = models.FloatField('クリック前週比(%)', default=0.0)
    sessions_change_pct = models.FloatField('セッション前週比(%)', default=0.0)

    # 詳細データ（後でJSON保存）
    top_pages = models.JSONField('上位ページ', default=list, blank=True)
    top_queries = models.JSONField('上位クエリ', default=list, blank=True)
    winners = models.JSONField('勝者ページ', default=list, blank=True)
    losers = models.JSONField('順位低下ページ', default=list, blank=True)
    rewrite_candidates = models.JSONField('リライト候補（順位11-20）', default=list, blank=True)
    ctr_underperformers = models.JSONField('CTR弱者', default=list, blank=True)
    suggested_actions = models.JSONField('アクション提案', default=list, blank=True)

    # フルレポート（Markdown形式、HTML変換して表示）
    report_markdown = models.TextField('レポート本文(Markdown)', blank=True)

    class Meta:
        verbose_name = '週次SEOレポート'
        verbose_name_plural = '週次SEOレポート'
        ordering = ['-period_end']

    def __str__(self):
        return f"SEOレポート {self.period_start} 〜 {self.period_end}"

