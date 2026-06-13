from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class ProductArticleKeyword(models.Model):
    """商品ごとの記事生成用ターゲットキーワード"""
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE,
        related_name="article_keywords",
        verbose_name="商品",
    )
    keyword = models.CharField("キーワード", max_length=200)
    search_volume = models.IntegerField("月間検索ボリューム", null=True, blank=True)
    difficulty = models.IntegerField("難易度(1-100)", null=True, blank=True)
    priority = models.IntegerField("優先度", default=0, db_index=True,
        help_text="数値が大きいほど優先")
    is_generated = models.BooleanField("記事生成済み", default=False, db_index=True)
    notes = models.TextField("メモ", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "商品キーワード"
        verbose_name_plural = "商品キーワード"
        ordering = ["-priority", "-created_at"]
        unique_together = [("product", "keyword")]

    def __str__(self):
        return f"{self.product.name} - {self.keyword}"


class ProductArticle(models.Model):
    """AI生成の商品記事"""
    STATUS_CHOICES = [
        ("draft", "下書き(AI生成直後)"),
        ("pending_review", "人間確認待ち"),
        ("approved", "承認済(未公開)"),
        ("published", "公開中"),
        ("rejected", "却下"),
    ]

    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE,
        related_name="ai_articles",
        verbose_name="対象商品",
    )
    keyword = models.CharField("ターゲットキーワード", max_length=200, db_index=True)
    title = models.CharField("記事タイトル", max_length=300)
    content = models.TextField("記事本文(HTML)")
    excerpt = models.TextField("抜粋", blank=True, max_length=500)

    # 薬機法チェック
    yakkihou_check = models.JSONField(
        "薬機法チェック結果", default=dict, blank=True,
        help_text='例: {"violations": [], "warnings": ["XXX"], "ok": true}'
    )
    yakkihou_passed = models.BooleanField("薬機法OK", default=False)

    # ステータス管理
    status = models.CharField("公開ステータス", max_length=20,
                              choices=STATUS_CHOICES, default="draft", db_index=True)
    ai_generated_at = models.DateTimeField("AI生成日時", null=True, blank=True, db_index=True)
    human_reviewed_at = models.DateTimeField("人間確認日時", null=True, blank=True)
    human_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_product_articles",
        verbose_name="確認者",
    )

    # 公開記事との紐付け(承認後にArticleとして繋がる)
    published_article = models.OneToOneField(
        "products.Article", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ai_source",
        verbose_name="公開記事",
        help_text="承認後、公開Article(products.Article)として登録するリンク",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI生成記事"
        verbose_name_plural = "AI生成記事"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title[:40]}"


class ArticleGenerationLog(models.Model):
    """AI生成の監査ログ - 何を入力に何を出力したか完全追跡可能に"""
    article = models.ForeignKey(
        ProductArticle, on_delete=models.CASCADE,
        related_name="generation_logs",
        verbose_name="生成記事",
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE,
        related_name="generation_logs",
        verbose_name="対象商品",
    )
    keyword = models.CharField("キーワード", max_length=200)

    # 入力スナップショット - 「DB情報以外を使っていないこと」の証跡
    source_snapshot = models.JSONField(
        "商品情報スナップショット", default=dict,
        help_text="生成時の商品DB情報の完全コピー(後から検証可能)",
    )
    prompt_template = models.CharField("プロンプトテンプレ", max_length=100, blank=True)
    full_prompt = models.TextField("最終プロンプト", blank=True,
        help_text="AIに渡した最終プロンプト全文")

    # AI 情報
    ai_provider = models.CharField("AIプロバイダ", max_length=50, blank=True,
        help_text="anthropic / openai / google 等")
    ai_model = models.CharField("AIモデル", max_length=100, blank=True,
        help_text="claude-sonnet-4-6 / gpt-4o 等")
    ai_temperature = models.DecimalField("Temperature", max_digits=4, decimal_places=2,
                                          null=True, blank=True)

    # 出力
    raw_output = models.TextField("AI生出力", blank=True)
    parsed_title = models.CharField("解析タイトル", max_length=300, blank=True)
    parsed_content = models.TextField("解析本文", blank=True)

    # メトリクス
    tokens_input = models.IntegerField("入力トークン", null=True, blank=True)
    tokens_output = models.IntegerField("出力トークン", null=True, blank=True)
    duration_ms = models.IntegerField("実行時間ms", null=True, blank=True)
    cost_usd = models.DecimalField("コストUSD", max_digits=10, decimal_places=6,
                                    null=True, blank=True)

    # 品質チェック
    hallucination_check = models.JSONField(
        "ハルシネーション検査", default=dict,
        help_text="DBに無い情報が出力に混入していないかの検査結果",
    )
    yakkihou_check_log = models.JSONField("薬機法チェックログ", default=dict)

    success = models.BooleanField("成功", default=True, db_index=True)
    error_message = models.TextField("エラー詳細", blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "生成ログ"
        verbose_name_plural = "生成ログ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.product.name} - {self.keyword}"



class SeoKeywordStrategy(models.Model):
    """SEOキーワード戦略管理"""
    ARTICLE_TYPE_CHOICES = [
        ("review", "口コミ・レビュー記事"),
        ("effect", "効果・検証記事"),
        ("comparison", "比較記事"),
        ("ranking", "おすすめ・ランキング記事"),
        ("howto", "使い方記事"),
        ("faq", "疑問解決記事"),
    ]
    STATUS_CHOICES = [
        ("idea", "候補"),
        ("planned", "作成予定"),
        ("writing", "執筆中"),
        ("generated", "AI生成済み"),
        ("checking", "薬機法/SEO確認中"),
        ("published", "公開済み"),
        ("rewrite", "リライト対象"),
        ("hold", "保留"),
    ]

    category = models.CharField("カテゴリ名", max_length=100, db_index=True,
        help_text="例: 美顔器, ドライヤー, 脱毛器")
    keyword = models.CharField("対策キーワード", max_length=200, db_index=True)
    search_intent = models.TextField("検索意図", blank=True,
        help_text="このキーワードで検索するユーザーが何を求めているか")
    article_type = models.CharField("記事タイプ", max_length=20,
        choices=ARTICLE_TYPE_CHOICES, default="review", db_index=True)
    search_volume = models.PositiveIntegerField("月間検索ボリューム", default=0)
    commercial_intent_score = models.PositiveSmallIntegerField(
        "商用意図スコア", default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=情報収集 5=購入直前",
    )
    competition_score = models.PositiveSmallIntegerField(
        "競合強度", default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=狙いやすい 5=超激戦",
    )
    priority_score = models.FloatField("優先度スコア", default=0, db_index=True,
        help_text="自動計算: 検索ボリューム × 商用意図 / 競合強度")
    status = models.CharField("ステータス", max_length=20,
        choices=STATUS_CHOICES, default="idea", db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_seo_keywords", verbose_name="担当者",
    )
    target_url = models.URLField("公開URL", blank=True, max_length=500,
        help_text="公開予定 or 公開済みURL")
    related_product = models.ForeignKey(
        "products.Product", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_keywords", verbose_name="関連商品",
    )
    related_article = models.ForeignKey(
        "products.Article", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_keywords", verbose_name="関連記事",
    )
    parent_keyword = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="children", verbose_name="親キーワード",
        help_text="例: 「美顔器 おすすめ」が「美顔器 効果」の親",
    )
    internal_link_targets = models.ManyToManyField(
        "self", blank=True, symmetrical=False,
        related_name="incoming_links", verbose_name="内部リンク先",
    )
    link_anchor_text = models.CharField("推奨アンカーテキスト", max_length=200, blank=True)
    memo = models.TextField("メモ", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEOキーワード戦略"
        verbose_name_plural = "SEOキーワード戦略"
        ordering = ["-priority_score", "-updated_at"]
        indexes = [
            models.Index(fields=["status", "-priority_score"]),
            models.Index(fields=["category", "article_type"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.keyword}"

    def save(self, *args, **kwargs):
        # priority_score を自動計算 (競合強度0回避)
        c_score = max(int(self.competition_score or 1), 1)
        ci_score = int(self.commercial_intent_score or 1)
        sv = int(self.search_volume or 0)
        self.priority_score = (sv * ci_score) / c_score
        super().save(*args, **kwargs)



class NgExpressionRule(models.Model):
    """薬機法・景品表示法のNG表現ルール"""
    RISK_CATEGORIES = [
        ("yakuji", "薬機法違反"),
        ("keihyo", "景品表示法違反"),
        ("medical", "医療表現"),
        ("absolute", "断定表現"),
        ("exaggeration", "誇張・優位表現"),
        ("comparison", "比較優位"),
        ("other", "その他"),
    ]
    SEVERITY_CHOICES = [
        ("high", "高(必ず修正)"),
        ("medium", "中(要確認)"),
        ("low", "低(可能なら修正)"),
    ]
    pattern = models.CharField("NGワード/正規表現", max_length=200, unique=True)
    is_regex = models.BooleanField("正規表現として扱う", default=False)
    risk_category = models.CharField("リスク分類", max_length=20,
        choices=RISK_CATEGORIES, db_index=True)
    severity = models.CharField("深刻度", max_length=10,
        choices=SEVERITY_CHOICES, default="high", db_index=True)
    reason = models.TextField("理由")
    suggestion = models.TextField("推奨言い換え", blank=True)
    is_active = models.BooleanField("有効", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NG表現ルール"
        verbose_name_plural = "NG表現ルール"
        ordering = ["-severity", "risk_category", "pattern"]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.pattern}"
