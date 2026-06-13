import time
from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # ハニーポット: BOTは埋めるが人間には不可視
    website = forms.CharField(
        required=False, label="",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    # 送信時刻チェック: 早すぎ(<3秒)も遅すぎ(>1日)もBOT扱い
    rendered_at = forms.IntegerField(widget=forms.HiddenInput, required=True)

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "body")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "山田 太郎(任意)"}),
            "email": forms.EmailInput(attrs={"placeholder": "[email protected]"}),
            "subject": forms.TextInput(attrs={"placeholder": "お問い合わせの件名"}),
            "body": forms.Textarea(attrs={"rows": 8, "placeholder": "お問い合わせの内容を詳しくお書きください"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["rendered_at"].initial = int(time.time())

    def clean_website(self):
        v = self.cleaned_data.get("website", "")
        if v:
            raise forms.ValidationError("不正な送信が検出されました。")
        return v

    def clean_rendered_at(self):
        rendered = self.cleaned_data.get("rendered_at", 0)
        elapsed = int(time.time()) - rendered
        if elapsed < 3:
            raise forms.ValidationError("送信が早すぎます。少し待ってから再送信してください。")
        if elapsed > 86400:
            raise forms.ValidationError("フォームの有効期限が切れました。ページを再読み込みしてください。")
        return rendered
