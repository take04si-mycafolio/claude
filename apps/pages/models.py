from django.db import models
from django.utils.html import strip_tags


class LegalDocument(models.Model):
    """利用規約・プライバシーポリシー・コミュニティガイドライン等の法的文書。

    WEB(テンプレート描画)とネイティブアプリ(API)の双方が、この単一レコードを
    参照することで内容のズレを無くす。本文はセマンティックHTML(h2/h3/p/ol/ul/li/a)
    で保持し、WEBはCSSで装飾、アプリは body_html もしくは body_text を描画する。
    class属性は不要(WEB側CSSで一括装飾)。
    """

    DOC_TYPES = [
        ("terms", "利用規約"),
        ("privacy", "プライバシーポリシー"),
        ("community", "コミュニティガイドライン"),
    ]

    doc_type = models.SlugField(
        "種別", max_length=20, unique=True, choices=DOC_TYPES,
        help_text="WEB/アプリはこの種別で文書を取得します。",
    )
    eyebrow = models.CharField(
        "英字ラベル", max_length=40, blank=True,
        help_text="見出し上の小さな英字(例: Terms)。空欄可。",
    )
    title = models.CharField("タイトル", max_length=100)
    body = models.TextField(
        "本文(HTML)",
        help_text="セマンティックHTML。見出しは <h2>、小見出しは <h3>、段落は <p>、"
                  "箇条書きは <ul><li>、番号付きは <ol><li>、リンクは <a href> を使用。"
                  "class属性は不要(自動でデザインが適用されます)。",
    )
    enacted_on = models.DateField("制定日", null=True, blank=True)
    revised_on = models.DateField("最終改定日", null=True, blank=True)
    is_published = models.BooleanField(
        "公開", default=True,
        help_text="オフにするとWEB・アプリ双方で非表示(404)になります。",
    )
    updated_at = models.DateTimeField("最終更新", auto_now=True)

    class Meta:
        verbose_name = "規約・ポリシー"
        verbose_name_plural = "規約・ポリシー"
        ordering = ["doc_type"]

    def __str__(self):
        return self.get_doc_type_display()

    @property
    def body_text(self):
        """タグを除いたプレーンテキスト(アプリのフォールバック表示・検索用)。"""
        return strip_tags(self.body)


class ContactMessage(models.Model):
    name = models.CharField("お名前", max_length=100, blank=True)
    email = models.EmailField("メールアドレス")
    subject = models.CharField("件名", max_length=200)
    body = models.TextField("お問い合わせ内容")
    is_read = models.BooleanField("既読", default=False, db_index=True)
    is_replied = models.BooleanField("返信済み", default=False, db_index=True)
    admin_notes = models.TextField("管理メモ", blank=True, help_text="ユーザーには見えない管理用メモ")
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=500, blank=True)
    created_at = models.DateTimeField("受信日時", auto_now_add=True, db_index=True)
    replied_at = models.DateTimeField("返信日時", null=True, blank=True)

    class Meta:
        verbose_name = "お問い合わせ"
        verbose_name_plural = "お問い合わせ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.subject} - {self.email}"
