from django import forms

from .imaging import MAX_UPLOAD_BYTES
from .models import Review, ReviewImage


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
