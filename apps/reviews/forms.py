from django import forms

from . import compliance
from .imaging import MAX_UPLOAD_BYTES
from .models import (
    ProductUseLog,
    ProductUseLogImage,
    ProductUseLogReport,
    Review,
    ReviewImage,
    ReviewReport,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """複数ファイルをまとめて受け取り、各ファイルを画像として検証する。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(attrs={"accept": "image/*", "multiple": True}),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned = []
        for f in files:
            if f.size > MAX_UPLOAD_BYTES:
                mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                raise forms.ValidationError(
                    f"画像1枚あたり{mb}MBまでです。「{f.name}」が大きすぎます。"
                )
            cleaned.append(single_clean(f, initial))
        return cleaned


def _star_choices():
    return [(i, f"{i}") for i in range(1, 6)]


def _icon_choices():
    return [(i, f"#{i}") for i in range(1, 10)]


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="総合評価", choices=_star_choices(), coerce=int,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    cospa = forms.TypedChoiceField(
        label="コスパ", choices=_star_choices(), coerce=int, required=False,
        empty_value=None,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    control = forms.TypedChoiceField(
        label="操作性", choices=_star_choices(), coerce=int, required=False,
        empty_value=None,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    safety = forms.TypedChoiceField(
        label="安全性", choices=_star_choices(), coerce=int, required=False,
        empty_value=None,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    expression = forms.TypedChoiceField(
        label="表情の変化", choices=_star_choices(), coerce=int, required=False,
        empty_value=None,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    icon = forms.TypedChoiceField(
        label="表示アイコン", choices=_icon_choices(),
        coerce=int, empty_value=None,
        widget=forms.RadioSelect(attrs={"data-icons": "1"}),
        required=False,
    )
    images = MultipleImageField(
        label="写真", required=False,
        help_text=f"最大{ReviewImage.MAX_PER_REVIEW}枚。自動で圧縮して保存します。",
    )

    def clean_images(self):
        files = self.cleaned_data.get("images") or []
        if len(files) > ReviewImage.MAX_PER_REVIEW:
            raise forms.ValidationError(
                f"画像は最大{ReviewImage.MAX_PER_REVIEW}枚までです。"
            )
        return files

    def clean(self):
        cleaned = super().clean()
        # 薬機法・景表法ゲート。findings と言い換え案はテンプレートが
        # form.compliance_findings / suggested_* で表示する。
        findings = compliance.check_fields(
            title=cleaned.get("title") or "",
            body=cleaned.get("body") or "",
        )
        self.compliance_findings = findings
        self.compliance_hint = compliance.WRITING_HINT
        self.suggested_title = None
        self.suggested_body = None
        if findings:
            title_findings = [f for f in findings if f["field"] == "title"]
            body_findings = [f for f in findings if f["field"] == "body"]
            if title_findings:
                self.suggested_title = compliance.suggest_full_text(
                    cleaned.get("title") or "", title_findings
                )
                self.add_error(
                    "title", "タイトルに掲載できない表現があります。上の指摘をご確認ください。"
                )
            if body_findings:
                self.suggested_body = compliance.suggest_full_text(
                    cleaned.get("body") or "", body_findings
                )
                self.add_error(
                    "body", "本文に掲載できない表現があります。上の指摘をご確認ください。"
                )
        return cleaned

    class Meta:
        model = Review
        fields = (
            "rating", "title", "body",
            "cospa", "control", "safety", "expression",
            "usage_period", "effectiveness", "skin_type", "icon",
        )
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6, "placeholder": "実際に使った感想を詳しくお書きください。良かった点・気になった点・どんな方に向いていそうか、など…"}),
            "title": forms.TextInput(attrs={"placeholder": "例: 1ヶ月使って肌のハリが変わりました"}),
        }


class ReviewReportForm(forms.ModelForm):
    """口コミ通報フォーム（PC版Web）。reason 必須・comment 任意。

    review / reporter / status 等はサーバ側（view）で設定し、フォームからは
    受け取らない。comment の最大長はモデルの MaxLengthValidator(1000) で担保しつつ、
    ここでも明示する。
    """

    class Meta:
        model = ReviewReport
        fields = ("reason", "comment")
        widgets = {
            "reason": forms.Select(),
            "comment": forms.Textarea(attrs={
                "rows": 4,
                "maxlength": ReviewReport.COMMENT_MAX_LEN,
                "placeholder": "状況を具体的にお書きください（任意）。例: 注文番号が画像に写っています。",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # reason は空選択を許さず、必ずいずれかを選ばせる。
        self.fields["reason"].required = True
        self.fields["comment"].required = False


class ProductUseLogForm(forms.ModelForm):
    """使用記録の投稿フォーム（PC版Web）。星評価なし・本文必須・画像任意。

    画像の処理（複数受け取り・サイズ/形式検証・枚数上限・圧縮）は通常口コミと同一の
    MultipleImageField / ReviewImage 系を流用する（圧縮は ProductUseLogImage.save 内）。
    """

    title = forms.CharField(
        label="タイトル", required=False, max_length=120,
        widget=forms.TextInput(attrs={
            "maxlength": 120,
            "placeholder": "例: 2週間使ってみて（任意）",
        }),
    )
    body = forms.CharField(
        label="本文", required=True,
        max_length=ProductUseLog.BODY_MAX_LEN,
        widget=forms.Textarea(attrs={
            "rows": 5,
            "maxlength": ProductUseLog.BODY_MAX_LEN,
            "placeholder": "使ってみた感想、変化、気づいたことを記録してください。",
        }),
    )
    images = MultipleImageField(
        label="写真", required=False,
        help_text=f"最大{ProductUseLogImage.MAX_PER_LOG}枚。自動で圧縮して保存します。",
    )

    def clean_images(self):
        files = self.cleaned_data.get("images") or []
        if len(files) > ProductUseLogImage.MAX_PER_LOG:
            raise forms.ValidationError(
                f"画像は最大{ProductUseLogImage.MAX_PER_LOG}枚までです。"
            )
        return files

    def clean(self):
        cleaned = super().clean()
        # 薬機法・景表法ゲート。使用記録はエラーを messages 経由で表示するため、
        # 1件ずつ「該当箇所・理由・言い換え例」を含む文字列エラーにして返す。
        findings = compliance.check_fields(
            title=cleaned.get("title") or "",
            body=cleaned.get("body") or "",
        )
        for f in findings[:5]:
            self.add_error(
                "body" if f["field"] == "body" else "title",
                f"「{f['match']}」は掲載できない表現です。{f['reason']}"
                f" 言い換え例:「{f['example']}」",
            )
        if findings:
            self.add_error(None, compliance.WRITING_HINT)
        return cleaned

    class Meta:
        model = ProductUseLog
        fields = ("title", "body")


class ProductUseLogReportForm(forms.ModelForm):
    """使用記録の通報フォーム（PC版Web）。reason 必須・comment 任意。

    use_log / reporter / status 等はサーバ側（view）で設定する。通常口コミの
    ReviewReportForm と同じ作法。
    """

    class Meta:
        model = ProductUseLogReport
        fields = ("reason", "comment")
        widgets = {
            "reason": forms.Select(),
            "comment": forms.Textarea(attrs={
                "rows": 4,
                "maxlength": ProductUseLogReport.COMMENT_MAX_LEN,
                "placeholder": "状況を具体的にお書きください（任意）。",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = True
        self.fields["comment"].required = False


class GuestReviewForm(forms.ModelForm):
    """商品ページ埋め込みのゲスト口コミフォーム（メディアサイト方針 2026-09-06）。

    会員登録なしで投稿できる簡易版。会員投稿(ReviewForm)と同じ薬機法・景表法
    ゲートを通し、承認制(is_approved=False)も同一。ボット対策はビュー側の
    honeypot / 経過時間 / IPレート制限と、本フォームの最小文字数で構成する。
    """

    rating = forms.TypedChoiceField(
        label="総合評価",
        choices=[(i, f"★{i}") for i in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect(attrs={"data-stars": "1"}),
    )
    guest_name = forms.CharField(
        label="ニックネーム", max_length=40, required=False,
        widget=forms.TextInput(attrs={"placeholder": "空欄なら「匿名」で掲載されます"}),
    )
    # honeypot: 人間には見えない入力欄。値が入っていたらボット扱いで弾く。
    website = forms.CharField(required=False, widget=forms.TextInput(
        attrs={"tabindex": "-1", "autocomplete": "off", "aria-hidden": "true"}))

    class Meta:
        model = Review
        fields = ("rating", "title", "body", "guest_name")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "例）思ったより軽くて毎日使えています"}),
            "body": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "使ってみて感じた良かった点・気になった点を教えてください（15文字以上）",
            }),
        }

    def clean_website(self):
        if (self.cleaned_data.get("website") or "").strip():
            raise forms.ValidationError("送信を受け付けられませんでした。")
        return ""

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if len(body) < 15:
            raise forms.ValidationError("本文は15文字以上で入力してください。")
        return body

    def clean(self):
        cleaned = super().clean()
        # 会員投稿(ReviewForm.clean)と同一の薬機法・景表法ゲート
        findings = compliance.check_fields(
            title=cleaned.get("title") or "",
            body=cleaned.get("body") or "",
        )
        self.compliance_findings = findings
        self.compliance_hint = compliance.WRITING_HINT
        self.suggested_title = None
        self.suggested_body = None
        if findings:
            title_findings = [f for f in findings if f["field"] == "title"]
            body_findings = [f for f in findings if f["field"] == "body"]
            if title_findings:
                self.suggested_title = compliance.suggest_full_text(
                    cleaned.get("title") or "", title_findings)
                self.add_error(
                    "title", "タイトルに掲載できない表現があります。下の指摘をご確認ください。")
            if body_findings:
                self.suggested_body = compliance.suggest_full_text(
                    cleaned.get("body") or "", body_findings)
                self.add_error(
                    "body", "本文に掲載できない表現があります。下の指摘をご確認ください。")
        return cleaned
