from django.conf import settings
from django.db import models
from django.utils import timezone


class ArticleMetricSnapshot(models.Model):
    """記事パフォーマンス・ダッシュボードの元データ（1取得=1スナップショット）。

    fetch_article_metrics 管理コマンドが GSC / GA4 から取得して保存する。
    管理画面のダッシュボードは「最新スナップショット」を読むだけ（API 認証は cron/root 側）。
    """

    period_start = models.DateField("期間開始", db_index=True)
    period_end = models.DateField("期間終了", db_index=True)
    fetched_at = models.DateTimeField("取得日時", auto_now_add=True, db_index=True)

    # 全体指標
    total_clicks = models.IntegerField("総クリック(GSC)", default=0)
    total_impressions = models.IntegerField("総表示回数(GSC)", default=0)
    avg_ctr = models.FloatField("平均CTR%(GSC)", default=0.0)
    avg_position = models.FloatField("平均掲載順位(GSC)", default=0.0)
    total_sessions = models.IntegerField("総セッション(GA4)", default=0)
    total_page_views = models.IntegerField("総PV(GA4)", default=0)
    avg_bounce_rate = models.FloatField("平均直帰率(GA4)", default=0.0)

    note = models.CharField("メモ", max_length=300, blank=True)

    class Meta:
        verbose_name = "記事パフォーマンス・スナップショット"
        verbose_name_plural = "記事パフォーマンス・スナップショット"
        ordering = ["-fetched_at"]

    def __str__(self):
        return f"{self.period_start}〜{self.period_end}（{self.fetched_at:%Y-%m-%d %H:%M}）"


class ArticleMetric(models.Model):
    """スナップショット内の 1 ページ（記事/商品/その他）の指標 + 流入キーワード。"""

    TYPE_CHOICES = [
        ("article", "記事"),
        ("product", "商品"),
        ("category", "カテゴリ"),
        ("page", "固定ページ"),
        ("other", "その他"),
    ]

    snapshot = models.ForeignKey(
        ArticleMetricSnapshot, on_delete=models.CASCADE, related_name="metrics",
        verbose_name="スナップショット",
    )
    path = models.CharField("パス", max_length=500, db_index=True)
    title = models.CharField("タイトル", max_length=300, blank=True)
    content_type = models.CharField(
        "種別", max_length=12, choices=TYPE_CHOICES, default="other", db_index=True)
    article = models.ForeignKey(
        "products.Article", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="metric_rows", verbose_name="記事",
    )

    # GSC（Search Console / WMT）
    impressions = models.IntegerField("表示回数", default=0, db_index=True)
    clicks = models.IntegerField("クリック", default=0)
    ctr = models.FloatField("CTR%", default=0.0)
    position = models.FloatField("平均順位", default=0.0)

    # GA4（アクセス解析）
    sessions = models.IntegerField("セッション", default=0, db_index=True)
    page_views = models.IntegerField("PV", default=0)
    active_users = models.IntegerField("ユーザー数", default=0)
    bounce_rate = models.FloatField("直帰率", default=0.0)  # 0-1
    avg_duration_sec = models.FloatField("平均滞在秒", default=0.0)

    # このページの流入キーワード一覧（GSC page×query）
    #   [{"query": str, "clicks": int, "impressions": int, "ctr": float, "position": float}, ...]
    keywords = models.JSONField("流入キーワード", default=list, blank=True)

    class Meta:
        verbose_name = "記事パフォーマンス"
        verbose_name_plural = "記事パフォーマンス"
        ordering = ["-impressions"]
        indexes = [models.Index(fields=["snapshot", "-impressions"])]

    def __str__(self):
        return f"{self.path} (imp={self.impressions})"

    @property
    def keyword_count(self):
        return len(self.keywords or [])


class AccessLog(models.Model):
    url = models.CharField("URL", max_length=500, db_index=True)
    method = models.CharField("メソッド", max_length=10, default="GET")
    status_code = models.PositiveSmallIntegerField("ステータスコード", null=True, db_index=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=500, blank=True)
    referer = models.CharField("リファラ", max_length=500, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name="ユーザー",
    )
    is_bot = models.BooleanField("Bot判定", default=False, db_index=True)
    created_at = models.DateTimeField("日時", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "アクセスログ"
        verbose_name_plural = "アクセスログ"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at", "url"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.method} {self.url}"


class TriageRun(models.Model):
    """GSC記事トリアージの1回の実行＝1スナップショット。

    run_gsc_triage 管理コマンドが GSC からデータを取得して全ページを4バケットに
    仕分けし、TriageRun を1件と ArticleTriage を複数件作成する。履歴として積む。
    """

    period_start = models.DateField("期間開始", db_index=True)
    period_end = models.DateField("期間終了", db_index=True)
    fetched_at = models.DateTimeField("取得日時", auto_now_add=True, db_index=True)

    total_articles = models.IntegerField("対象ページ数", default=0)

    # 一覧表示用のバケット件数キャッシュ
    count_quick_win = models.IntegerField("quick_win 件数", default=0)
    count_needs_work = models.IntegerField("needs_work 件数", default=0)
    count_performing = models.IntegerField("performing 件数", default=0)
    count_dead = models.IntegerField("dead 件数", default=0)

    sitemap_url = models.CharField("サイトマップURL", max_length=500, blank=True)

    class Meta:
        verbose_name = "GSCトリアージ実行"
        verbose_name_plural = "GSCトリアージ実行"
        ordering = ["-fetched_at"]

    def __str__(self):
        return f"{self.period_start}〜{self.period_end}（{self.fetched_at:%Y-%m-%d %H:%M}）"


class ArticleTriage(models.Model):
    """トリアージ実行内の1ページ（記事/商品/その他）の判定結果。"""

    BUCKET_CHOICES = [
        ("quick_win", "quick_win（あと一歩・最優先）"),
        ("needs_work", "needs_work（検索意図のズレ）"),
        ("performing", "performing（すでに上位）"),
        ("dead", "dead（統合/削除候補）"),
    ]

    run = models.ForeignKey(
        TriageRun, on_delete=models.CASCADE, related_name="articles",
        verbose_name="トリアージ実行",
    )
    article = models.ForeignKey(
        "products.Article", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="triage_rows", verbose_name="記事",
    )
    url = models.CharField("URL", max_length=500, db_index=True)
    bucket = models.CharField(
        "バケット", max_length=12, choices=BUCKET_CHOICES, db_index=True)

    # GSC ページ別合計（表示の「正」）
    impressions = models.IntegerField("表示回数", default=0)
    clicks = models.IntegerField("クリック", default=0)
    ctr = models.FloatField("CTR%", default=0.0)
    avg_position = models.FloatField("平均掲載順位", default=0.0)

    # 最上位クエリ（判定の基準）
    best_query = models.CharField("最上位クエリ", max_length=300, blank=True)
    best_query_position = models.FloatField("最上位クエリ順位", null=True, blank=True)
    best_query_impressions = models.IntegerField("最上位クエリ表示回数", default=0)
    num_queries = models.IntegerField("クエリ数", default=0)
    # このURLが拾っている全クエリ（position昇順）。[{query,position,impressions,clicks}, ...]
    # URL単位・全クエリ考慮のリライト（keepクエリの巻き添え毀損防止）に使う。
    queries = models.JSONField("獲得クエリ一覧", default=list, blank=True)

    in_sitemap = models.BooleanField("サイトマップ掲載", default=False)

    # 観察ステータス（bucket とは独立した第2軸）。実行時の更新日をスナップショット固定。
    OBSERVATION_CHOICES = [
        ("observing", "observing（様子見・反映ラグ中）"),
        ("evaluable", "evaluable（評価中）"),
        ("settled", "settled（判定済み）"),
        ("unknown", "unknown（更新日不明）"),
    ]
    last_updated = models.DateTimeField("更新日(実行時スナップショット)", null=True, blank=True)
    days_since_update = models.IntegerField("更新からの経過日数", null=True, blank=True)
    observation_status = models.CharField(
        "観察ステータス", max_length=12, choices=OBSERVATION_CHOICES,
        null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "記事トリアージ"
        verbose_name_plural = "記事トリアージ"
        ordering = ["bucket", "best_query_position"]
        indexes = [
            models.Index(fields=["run", "bucket"]),
            models.Index(fields=["bucket"]),
            models.Index(fields=["best_query_position"]),
        ]

    def __str__(self):
        return f"[{self.bucket}] {self.url}"


class PlaybookRule(models.Model):
    """「順位に効く要素」のプレイブック項目（機械参照用）。正本は playbook.md。

    build_playbook が生死記事の差分から初版を生成し、パートC（効果測定）で検証・更新する。
    """

    CATEGORY_CHOICES = [
        ("title", "タイトル/H1"),
        ("intent", "検索意図"),
        ("structure", "構成・網羅性"),
        ("internal_link", "内部リンク"),
        ("specificity", "具体性・一次情報"),
        ("anti", "避けるべきパターン"),
    ]

    key = models.SlugField("キー", max_length=60, unique=True)
    category = models.CharField("分類", max_length=16, choices=CATEGORY_CHOICES, db_index=True)
    title = models.CharField("ルール名", max_length=200)
    description = models.TextField("説明", blank=True)
    check_item = models.CharField(
        "チェック項目", max_length=300, blank=True,
        help_text="レビュー画面のチェックリストに出す1行。")
    evidence = models.JSONField(
        "エビデンス", default=dict, blank=True,
        help_text="live/dead の偏在度など根拠データ。")
    priority = models.IntegerField("優先度", default=100, help_text="小さいほど上位")
    is_active = models.BooleanField("有効", default=True)
    is_antipattern = models.BooleanField("避けるべきパターン", default=False)

    # パートC（検証）で更新
    verified = models.BooleanField("実データ検証済み", default=False)
    verification_note = models.TextField("検証メモ", blank=True)

    source_run = models.ForeignKey(
        "analytics.TriageRun", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="playbook_rules", verbose_name="生成元トリアージ実行")
    created_at = models.DateTimeField("作成", auto_now_add=True)
    updated_at = models.DateTimeField("更新", auto_now=True)

    class Meta:
        verbose_name = "プレイブック項目"
        verbose_name_plural = "プレイブック項目"
        ordering = ["priority", "category"]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"


class RewriteDraft(models.Model):
    """quick_win 記事のリライト下書き（指示書→執筆→レビュー→反映の状態機械）。

    アプリはLLMを呼ばない。指示書(instructions)は PlaybookRule から決定論的に生成し、
    実際の本文執筆は Claude Code（アプリ外）が担う。draft_content が入ったらレビュー→承認反映。
    反映は apply_draft の共有関数を再利用し last_rewritten_at が正確に更新される。
    """

    STATUS_CHOICES = [
        ("pending", "未着手"),
        ("instructed", "指示書生成済"),
        ("drafting", "執筆中"),
        ("in_review", "レビュー待ち"),
        ("approved", "承認"),
        ("applied", "反映済"),
        ("rejected", "却下"),
    ]

    article = models.ForeignKey(
        "products.Article", on_delete=models.CASCADE,
        related_name="rewrite_drafts", verbose_name="記事")
    source_triage = models.ForeignKey(
        "analytics.ArticleTriage", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rewrite_drafts", verbose_name="着手時トリアージ")
    # 手動で作業台に追加した下書き（GSCトリアージ由来でない）。
    # make_rewrite_instructions の掃除対象から除外し、次回トリアージで消えないようにする。
    is_manual = models.BooleanField("手動追加", default=False, db_index=True)
    # 基準記事（お手本）: この記事の構成・粒度・トーンを基準に再構築する。指示書冒頭に差し込む。
    reference_article = models.ForeignKey(
        "products.Article", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rewrite_reference_for", verbose_name="基準記事(お手本)")
    target_query = models.CharField("押し上げ対象クエリ(旧・grow代表)", max_length=300, blank=True)
    # 着手時点の順位・表示を固定（source_triage が消えても比較できるように）
    src_best_position = models.FloatField("着手時 順位", null=True, blank=True)
    src_impressions = models.IntegerField("着手時 表示回数", default=0)

    # URL単位・全クエリ考慮のリライト（best_query単体依存をやめる）
    # query_portfolio: このURLの全獲得クエリ [{query,position,impressions,clicks}]（position昇順）
    query_portfolio = models.JSONField("獲得クエリ一覧", default=list, blank=True)
    # target_keep: 維持すべき既存クエリ群 / target_grow: 伸ばしたいクエリ群
    #   初期値は機械提案。最終確定は人間/Claude Code がレビュー画面で行う。
    target_keep = models.JSONField("維持クエリ(keep)", default=list, blank=True)
    target_grow = models.JSONField("成長クエリ(grow)", default=list, blank=True)

    status = models.CharField(
        "状態", max_length=12, choices=STATUS_CHOICES, default="pending", db_index=True)

    instructions = models.TextField("リライト指示書", blank=True)
    checklist = models.JSONField("チェックリスト", default=list, blank=True)
    playbook_refs = models.JSONField("参照プレイブック項目", default=list, blank=True)

    draft_title = models.CharField("案タイトル", max_length=500, blank=True)
    draft_content = models.TextField("案本文(HTML)", blank=True)
    diff_summary = models.TextField("変更点の要約", blank=True)
    reviewer_note = models.TextField("レビューメモ", blank=True)

    created_at = models.DateTimeField("作成", auto_now_add=True)
    instructed_at = models.DateTimeField("指示書生成", null=True, blank=True)
    reviewed_at = models.DateTimeField("レビュー", null=True, blank=True)
    applied_at = models.DateTimeField("反映", null=True, blank=True)

    # ── 効果測定（パートC）: applied_at 起点・21日経過後に順位軸で判定 ──
    # observation_status とは別時計。measure_rewrites が反映後最新runから after を取得して更新。
    EVAL_STATUS_CHOICES = [
        ("pending_eval", "結果待ち"),
        ("improved", "改善"),
        ("reached_p1", "1ページ目到達"),
        ("flat", "横ばい"),
        ("declined", "悪化"),
    ]
    eval_status = models.CharField(
        "効果判定", max_length=14, choices=EVAL_STATUS_CHOICES,
        default="pending_eval", db_index=True)
    days_since_applied = models.IntegerField("反映後経過日数", null=True, blank=True)
    grow_before = models.FloatField("grow反映前順位", null=True, blank=True)
    grow_after = models.FloatField("grow反映後順位", null=True, blank=True)
    keep_damaged = models.BooleanField("keep毀損", default=False, db_index=True)
    keep_detail = models.JSONField("keep毀損詳細", default=list, blank=True)
    measured_at = models.DateTimeField("測定実行日時", null=True, blank=True)

    # ── 学習ループ（パートD）: 何を変えたかの構造化記録と、判定確定後の学び ──
    # applied_tactics: 反映時に適用した戦術スラッグのリスト（learning.TACTICS の語彙）。
    #   Claude Code が反映時に記録する。空なら learn_rewrites が diff_summary から補完抽出。
    applied_tactics = models.JSONField("適用した戦術", default=list, blank=True)
    # lesson: 21日判定の確定後に learn_rewrites が起票する「この記事の学び」。
    #   決定論スケルトン（数値事実）＋ Claude Code/人間の分析追記。次回指示書に供給される。
    lesson = models.TextField("学び(判定確定後)", blank=True)
    lesson_recorded_at = models.DateTimeField("学び記録日時", null=True, blank=True)

    # ── 検品(リン様) ─────────────────────────────────────────────
    # 反映前に検品担当が記録する。{"date","verdict":"passed|fixed|failed","fixes":[],"notes","gates"}
    # verdict が passed/fixed でない下書きは承認センターで反映できない(2026-09-08)。
    qa_result = models.JSONField("検品結果", default=dict, blank=True)

    class Meta:
        verbose_name = "リライト下書き"
        verbose_name_plural = "リライト下書き"
        ordering = ["-src_impressions", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["article", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.article.slug} ← {self.target_query}"

    @property
    def checklist_done(self):
        items = self.checklist or []
        return sum(1 for c in items if c.get("ok"))


class CompletedRewriteDraft(RewriteDraft):
    """反映済(applied)＝リライト完了ぶんの表示専用プロキシ。
    作業台(RewriteDraft)の一覧を「まだ作業中のもの」だけに保ち、
    完了ぶんは管理画面「リライト完了一覧」に分けて振り分けるためのビュー。
    実テーブルは RewriteDraft と同一（proxy）。"""

    class Meta:
        proxy = True
        verbose_name = "リライト完了"
        verbose_name_plural = "リライト完了一覧"


class RewriteEval(RewriteDraft):
    """リライト効果測定の表示専用プロキシ（applied のみを効果測定ビューで扱う）。
    実テーブルは RewriteDraft と同一。measure_rewrites が更新した eval_* を可視化する。"""

    class Meta:
        proxy = True
        verbose_name = "リライト効果測定"
        verbose_name_plural = "リライト効果測定"


class RewriteTactic(models.Model):
    """リライト戦術の成績集計（学習ループの中核テーブル）。

    learn_rewrites が「判定確定済み RewriteDraft × applied_tactics」から
    毎回ゼロから再計算する（増分更新ではないので冪等・自己修復的）。
    make_rewrite_instructions がここを読んで、実測に基づく学習を指示書へ差し込む。
    """

    slug = models.SlugField("戦術キー", max_length=60, unique=True)
    label = models.CharField("戦術名", max_length=200)
    description = models.CharField("説明", max_length=300, blank=True)

    n_reached_p1 = models.IntegerField("1ページ目到達", default=0)
    n_improved = models.IntegerField("改善", default=0)
    n_flat = models.IntegerField("横ばい", default=0)
    n_declined = models.IntegerField("悪化", default=0)
    n_keep_damaged = models.IntegerField("keep毀損 同時発生", default=0)

    # [{draft_id, slug, outcome, delta}] 根拠（直近最大20件）
    samples = models.JSONField("根拠サンプル", default=list, blank=True)
    note = models.TextField("所見(人間/Claude Code追記)", blank=True)
    updated_at = models.DateTimeField("更新", auto_now=True)

    class Meta:
        verbose_name = "リライト戦術 成績"
        verbose_name_plural = "リライト戦術 成績（学習ループ）"
        ordering = ["-n_reached_p1", "-n_improved"]

    @property
    def n_total(self):
        return self.n_reached_p1 + self.n_improved + self.n_flat + self.n_declined

    @property
    def win_rate(self):
        """勝率%（reached_p1+improved / 判定総数）。判定なしは None。"""
        if not self.n_total:
            return None
        return round(100.0 * (self.n_reached_p1 + self.n_improved) / self.n_total, 1)

    def __str__(self):
        wr = f"{self.win_rate}%" if self.win_rate is not None else "—"
        return f"{self.label}（{wr} / n={self.n_total}）"


class ContentGap(models.Model):
    """needs_work 記事の「上位比較(コンテンツギャップ)」最小構成。

    競合本文の自動取得(スクレイピング)はしない。競合URLは人が管理画面で貼り、
    競合の中身は人と Claude Code が実際に読んで判断する。アプリは自記事の見出し等
    (self_outline)を決定論的に用意するだけ（LLM不使用）。
    """

    STATUS_CHOICES = [
        ("pending", "未着手"),
        ("urls_set", "競合URL設定済"),
        ("analyzed", "ギャップ記入済"),
        ("reviewed", "採否確定済"),
    ]

    rewrite_draft = models.OneToOneField(
        "analytics.RewriteDraft", on_delete=models.CASCADE,
        related_name="content_gap", verbose_name="リライト下書き")
    target_query = models.CharField("対象クエリ(grow代表)", max_length=300, blank=True)
    competitor_urls = models.JSONField(
        "競合URL(人が貼る・記録用)", default=list, blank=True,
        help_text='上位表示の競合URL 2〜3本。どの競合と戦うかの記録。')
    competitor_bodies = models.JSONField(
        "競合ページ本文(URLごと・人がコピペ)", default=dict, blank=True,
        help_text="{URL: 本文} の辞書。競合URLの数だけ本文欄が出るので、各URLのページ本文をコピペする。"
                  "bot取得はブロックされるサイトが多いため、人が貼ったこの本文を Claude Code が分析する。")
    external_analysis = models.TextField(
        "GPT分析結果(貼り付け)", blank=True,
        help_text="作業台の「GPTに渡すプロンプト」をコピーしてGPT(ブラウジング可)に投げ、"
                  "返答をここへそのまま貼り付ける。ギャップ分析と指示書がこの内容も材料にする。")
    self_outline = models.JSONField(
        "自記事アウトライン", default=dict, blank=True,
        help_text="H2/H3見出し・FAQ有無をアプリが決定論抽出したもの。")
    gap_findings = models.TextField(
        "ギャップ(欠けている本質要素)", blank=True,
        help_text="Claude Code/人が競合を読んで記入。1行1要素。増量の全列挙ではなく本質要素のみ。")
    gap_decisions = models.JSONField(
        "採否", default=list, blank=True,
        help_text='[{"item":..., "reflect":true/false, "primary_info":true/false}] '
                  '反映すると選んだ項目だけが指示書に渡る（増量の歯止め）。')
    status = models.CharField(
        "状態", max_length=12, choices=STATUS_CHOICES, default="pending", db_index=True)
    created_at = models.DateTimeField("作成", auto_now_add=True)
    updated_at = models.DateTimeField("更新", auto_now=True)

    class Meta:
        verbose_name = "コンテンツギャップ(上位比較)"
        verbose_name_plural = "コンテンツギャップ(上位比較)"

    def __str__(self):
        return f"[{self.get_status_display()}] gap: {self.rewrite_draft.article.slug}"


class WorkReport(models.Model):
    """Claude / 運用作業の報告。ターミナルではなく管理画面で作業内容を確認するための記録。

    機能には影響しない純粋なログ用テーブル。post_report 管理コマンド or admin から登録する。
    """

    STATUS_CHOICES = [
        ("success", "完了"),
        ("info", "情報"),
        ("warning", "注意"),
        ("error", "エラー"),
    ]

    title = models.CharField("作業タイトル", max_length=200)
    status = models.CharField(
        "状態", max_length=10, choices=STATUS_CHOICES, default="success", db_index=True,
    )
    summary = models.CharField(
        "概要", max_length=500, blank=True,
        help_text="一覧に表示する1行サマリー。",
    )
    body = models.TextField(
        "作業報告", blank=True,
        help_text="詳細レポート。Markdownで記述すると整形表示される。",
    )
    files_changed = models.TextField(
        "変更ファイル", blank=True,
        help_text="1行1ファイル。",
    )
    created_at = models.DateTimeField("報告日時", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "作業報告"
        verbose_name_plural = "作業報告"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.title}"


class RevenueEntry(models.Model):
    """月次の収益実績記録(2026-09-06新設)。

    アフィリエイト管理画面(楽天/Amazon等)の確定額はAPIで取れないため、
    運営が管理画面で月次入力する。編集長AIが週次ダイジェストで
    目標(2026年12月に月10万円)との差分を検証・報告する。
    """

    SOURCE_CHOICES = [
        ("rakuten", "楽天アフィリエイト"),
        ("amazon", "Amazonアソシエイト"),
        ("adsense", "AdSense"),
        ("other", "その他"),
    ]

    year_month = models.CharField(
        "対象月", max_length=7, db_index=True,
        help_text="YYYY-MM 形式(例: 2026-09)")
    source = models.CharField("収益源", max_length=16, choices=SOURCE_CHOICES)
    amount = models.PositiveIntegerField("金額(円)")
    is_confirmed = models.BooleanField(
        "確定額", default=True,
        help_text="OFF=速報値/見込み。確定したら金額を直してONにする")
    memo = models.CharField("メモ", max_length=200, blank=True)
    created_at = models.DateTimeField("入力日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "収益記録"
        verbose_name_plural = "収益記録"
        ordering = ["-year_month", "source"]
        constraints = [
            models.UniqueConstraint(
                fields=["year_month", "source"], name="unique_revenue_month_source")
        ]

    def __str__(self):
        return f"{self.year_month} {self.get_source_display()} ¥{self.amount:,}"


class EditorNote(models.Model):
    """人（運営）が承認前の記事に付ける修正指示（2026-09-08新設）。

    承認センターの「レビューページ」で本文の該当箇所をマウス選択し、
    「ここをこう直して」を書き込む。指示は担当AI社員へ差し戻され、
    担当が修正したうえで resolution（対応内容）を記録する。

    さらに category 別の集計と lesson を learning.build_editor_note_digest() が
    指示書へ還流させる。つまり「1回の指摘 → その記事の修正」だけで終わらせず、
    以後の執筆で同じ指摘を繰り返さないための学習材料として蓄積する。
    """

    KIND_CHOICES = [
        ("rewrite", "リライト案"),
        ("article", "新規記事"),
        ("product_v2", "商品記事v2"),
    ]
    # 指摘の種類。学習還流のときに「どこで繰り返し転んでいるか」を数えるための軸。
    CATEGORY_CHOICES = [
        ("reader_value", "読者価値・切り口"),
        ("structure", "構成・見出しの流れ"),
        ("tone", "文章表現・トーン"),
        ("fact", "事実・数値の正確さ"),
        ("seo", "タイトル・メタ・SEO"),
        ("product", "商品選定・価格"),
        ("links", "内部リンク・回遊"),
        ("compliance", "薬機法・景表法"),
        ("format", "書式・レイアウト"),
        ("other", "その他"),
    ]
    STATUS_CHOICES = [
        ("open", "対応待ち"),
        ("fixed", "修正済"),
        ("dismissed", "対応不要"),
    ]
    # 差し戻し先の担当（AI社員キー = agents/characters.json のキー）
    ASSIGNEE_CHOICES = [
        ("writer", "新規執筆担当（ふみちゃん）"),
        ("product_writer", "商品記事v2担当（アズ）"),
        ("followup", "修正対応・リライト後続処理（なお姉）"),
        ("qa", "検品担当（リン様）"),
    ]

    # 指摘の出どころ。human=人が承認センターで書いた指示、
    # qa=検品担当(リン様)の要差戻し(verdict=failed)を担当AIのキューに載せたもの(2026-09-09新設)。
    SOURCE_CHOICES = [
        ("human", "運営（人）"),
        ("qa", "検品担当（リン様）"),
    ]

    kind = models.CharField("対象", max_length=12, choices=KIND_CHOICES, db_index=True)
    target_id = models.IntegerField("対象ID", db_index=True,
                                    help_text="RewriteDraft.id / Article.id / Product.pk")
    source = models.CharField("出どころ", max_length=8, choices=SOURCE_CHOICES,
                              default="human", db_index=True)
    slug = models.CharField("スラッグ", max_length=500, blank=True)
    target_title = models.CharField("対象タイトル", max_length=500, blank=True)

    quote = models.TextField("指摘箇所（本文からの引用）", blank=True,
                             help_text="空＝記事全体への指摘")
    comment = models.TextField("修正指示")
    category = models.CharField("指摘の種類", max_length=16,
                                choices=CATEGORY_CHOICES, default="other", db_index=True)
    assignee = models.CharField("担当", max_length=16, choices=ASSIGNEE_CHOICES, blank=True)

    status = models.CharField("状態", max_length=10, choices=STATUS_CHOICES,
                              default="open", db_index=True)
    sent_back_at = models.DateTimeField("担当へ差し戻し", null=True, blank=True)
    resolved_at = models.DateTimeField("対応完了", null=True, blank=True)
    resolution = models.TextField("担当の対応内容", blank=True)
    # 次回以降の執筆に効かせる一般化した学び（担当AIが記録し、指示書へ還流する）
    lesson = models.TextField("次に活かす学び", blank=True)

    created_at = models.DateTimeField("作成", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "記事の修正指示"
        verbose_name_plural = "記事の修正指示（レビュー）"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "target_id"]),
            models.Index(fields=["status", "assignee"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] /{self.slug}/ {self.comment[:40]}"

    @property
    def review_url(self):
        return f"/admin/approvals/review/{self.kind}/{self.target_id}/"


class ArticleWorkLog(models.Model):
    """記事1本ごとの作業履歴（誰が・いつ・何をしたか）。2026-09-09新設。

    承認センターに記事が上がるまでに、どの社員がどの工程を通したのかを残す。
    検品が空振りしていたのに気づけなかった事故（qa.shのlock timeout）を受けて、
    「工程が飛んでいること」を人が一目で見つけられるようにするための記録。

    - AI社員は各工程の完了時に `manage.py worklog` で自分の作業を記録する（義務）
    - 人の操作（差し戻し・承認反映・公開）はアプリが自動で記録する
    - 記録が無い＝その工程を通っていない、と読めることが重要なので、
      「やっていないのに記録する」ことは絶対にしない
    """

    KIND_CHOICES = EditorNote.KIND_CHOICES
    AGENT_CHOICES = [
        ("desk", "編集長（レイカさん）"),
        ("researcher", "リサーチ担当（しおりん）"),
        ("writer", "新規執筆担当（ふみちゃん）"),
        ("product_writer", "商品記事v2担当（アズ）"),
        ("qa", "検品担当（リン様）"),
        ("followup", "修正対応・リライト後続（なお姉）"),
        ("observe", "観測cron（ミオ）"),
        ("human", "運営（人）"),
    ]
    ACTION_CHOICES = [
        ("researched", "リサーチ"),
        ("written", "執筆"),
        ("queued", "承認キューに投入"),
        ("revised", "修正対応"),
        ("qa_passed", "検品 合格(無修正)"),
        ("qa_fixed", "検品 合格(調整あり)"),
        ("qa_failed", "検品 要差戻し"),
        ("note_added", "人が修正指示を記入"),
        ("sent_back", "人が差し戻し"),
        ("applied", "本番へ反映・公開"),
        ("other", "その他"),
    ]

    kind = models.CharField("対象", max_length=12, choices=KIND_CHOICES, db_index=True)
    target_id = models.IntegerField("対象ID", db_index=True)
    slug = models.CharField("スラッグ", max_length=500, blank=True)
    agent = models.CharField("担当", max_length=16, choices=AGENT_CHOICES)
    action = models.CharField("作業", max_length=16, choices=ACTION_CHOICES)
    summary = models.CharField("何をしたか(1行)", max_length=300)
    detail = models.TextField("詳細", blank=True)
    created_at = models.DateTimeField("記録日時", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "記事の作業履歴"
        verbose_name_plural = "記事の作業履歴"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind", "target_id", "created_at"])]

    def __str__(self):
        return (f"{self.created_at:%m/%d %H:%M} /{self.slug}/ "
                f"{self.get_agent_display()} {self.get_action_display()}")


def log_article_work(kind, target_id, slug, agent, action, summary, detail=""):
    """作業履歴を1件残す（アプリ内から呼ぶ共通関数）。記録失敗で本処理は止めない。"""
    try:
        return ArticleWorkLog.objects.create(
            kind=kind, target_id=target_id, slug=slug or "", agent=agent,
            action=action, summary=summary[:300], detail=detail)
    except Exception:
        return None


class DeskDecision(models.Model):
    """編集長（レイカさん）が人に求める判断（2026-09-14新設）。

    これまで「要対応(人)」は週次ダイジェスト(WorkReport)の本文に文章で書かれるだけで、
    答える場所が無かった。そのため人はターミナルで指示するしかなく、答えないと
    同じ論点が毎週「3週目」と持ち越されていた。

    流れ:
      1. 編集長が `manage.py desk_decision add` で1論点1件登録（選択肢と推奨案つき）
      2. 人が承認センター「編集長からの判断待ち」でボタンを押して回答（コメント可）
         - 選択肢に action があれば、その場で実行（例: 生産終了フラグの変更）
      3. 回答で triggers/desk-decision-<id>.json を置く → dispatch_revision.sh が
         編集長を「判断反映モード」で起動し、queue.md 等へ反映して done にする
      4. コード変更が要る回答は dev_pending（開発作業待ち）として承認センターに残る
    """

    CATEGORY_CHOICES = [
        ("discontinued", "生産終了・商品データ"),
        ("cannibal", "カニバリ・統合"),
        ("revenue", "収益・成約"),
        ("seo", "タイトル・SEO"),
        ("quality", "品質・検品"),
        ("policy", "方針・戦略"),
        ("other", "その他"),
    ]
    STATUS_CHOICES = [
        ("open", "回答待ち"),
        ("answered", "回答済み・編集長が反映中"),
        ("dev_pending", "開発作業待ち"),
        ("done", "完了"),
        ("withdrawn", "取り下げ"),
    ]

    # 同じ論点を毎週登録し直しても1件にまとめるためのキー（例: cannibal:datsumouki-cool:datsumouki-itami）
    key = models.CharField("論点キー", max_length=200, db_index=True)
    category = models.CharField("種類", max_length=16, choices=CATEGORY_CHOICES,
                                default="other", db_index=True)
    title = models.CharField("判断してほしいこと", max_length=200)
    background = models.TextField("背景・根拠", blank=True, help_text="Markdown可")
    recommendation = models.TextField("編集長の推奨案", blank=True)
    # [{"key": "merge", "label": "統合する", "detail": "...", "recommended": true,
    #   "action": {"type": "set_discontinued", "products": ["slug"], "value": true},
    #   "needs_dev": false}]
    options = models.JSONField("選択肢", default=list, blank=True)
    slugs = models.CharField("関係するslug", max_length=500, blank=True)
    source_report = models.ForeignKey(
        "WorkReport", verbose_name="出典の報告", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions")

    status = models.CharField("状態", max_length=12, choices=STATUS_CHOICES,
                              default="open", db_index=True)
    times_raised = models.PositiveIntegerField("提起回数", default=1)
    first_raised_at = models.DateTimeField("初回提起", default=timezone.now)
    last_raised_at = models.DateTimeField("最終提起", default=timezone.now)

    choice = models.CharField("選んだ選択肢", max_length=40, blank=True)
    choice_label = models.CharField("選んだ選択肢(表示名)", max_length=200, blank=True)
    answer_comment = models.TextField("回答コメント", blank=True)
    answered_by = models.CharField("回答者", max_length=150, blank=True)
    answered_at = models.DateTimeField("回答日時", null=True, blank=True)
    action_result = models.TextField("回答時に実行した処理", blank=True)

    handled_note = models.TextField("編集長の反映内容", blank=True)
    handled_at = models.DateTimeField("反映日時", null=True, blank=True)

    created_at = models.DateTimeField("作成", auto_now_add=True)

    class Meta:
        verbose_name = "編集長からの判断待ち"
        verbose_name_plural = "編集長からの判断待ち"
        ordering = ["-last_raised_at"]

    def __str__(self):
        return f"判断#{self.pk} [{self.get_status_display()}] {self.title}"

    @property
    def days_open(self):
        return (timezone.now() - self.first_raised_at).days

    def option(self, key):
        return next((o for o in (self.options or []) if o.get("key") == key), None)


class OutboundClick(models.Model):
    """購入リンク（楽天・Amazon等）が押された記録（2026-09-14新設）。

    楽天リンクは楽天へ直接飛ぶため、どのページのどのボタンから何回押されたかを
    自社では追えなかった（9/7からクリックが約10倍になっても、発生元を切り分けられなかった）。
    リンクは一切変えず、押された瞬間にページ内スクリプトが sendBeacon で記録を送る。

    JavaScriptを実行しないボットは記録されない。
    つまり「楽天のクリック数 − ここの件数」がボット等の非人間クリックの目安になる。
    """

    NETWORK_CHOICES = [
        ("rakuten", "楽天"),
        ("amazon", "Amazon"),
        ("other", "その他"),
    ]

    created_at = models.DateTimeField("クリック日時", auto_now_add=True, db_index=True)
    network = models.CharField("リンク先", max_length=10, choices=NETWORK_CHOICES, db_index=True)
    page = models.CharField("押されたページ", max_length=500, db_index=True)
    href = models.URLField("リンクURL", max_length=1000)
    product_slug = models.CharField("商品slug", max_length=255, blank=True, db_index=True,
                                    help_text="リンクURLが商品のaffiliate/rakuten/amazon URLと一致した場合")
    link_text = models.CharField("ボタン文言", max_length=120, blank=True)
    section = models.CharField("直前の見出し", max_length=200, blank=True)
    container = models.CharField("置き場所（周囲のclass）", max_length=200, blank=True)
    device = models.CharField("端末", max_length=10, blank=True)  # mobile / pc
    referrer = models.CharField("流入元", max_length=300, blank=True)
    ip_hash = models.CharField("IPハッシュ", max_length=16, blank=True, db_index=True)
    user_agent = models.CharField("UA", max_length=300, blank=True)
    is_bot = models.BooleanField("Bot判定", default=False, db_index=True)
    is_staff = models.BooleanField("運営のクリック", default=False, db_index=True)

    class Meta:
        verbose_name = "購入リンクのクリック"
        verbose_name_plural = "購入リンクのクリック"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["network", "created_at"])]

    def __str__(self):
        return f"{self.created_at:%m/%d %H:%M} {self.get_network_display()} {self.page}"
