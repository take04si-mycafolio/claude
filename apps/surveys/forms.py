from django import forms

from .config import get_survey


class SurveyResponseForm(forms.Form):
    """survey_slug の設定に基づき、設問ごとに選択値を検証するフォーム。

    選択式の回答は self.answers({question_key: value}) に組み立てる。
    honeypot（website）に値が入っていれば bot とみなして無効化する。
    """

    reason = forms.CharField(max_length=300, required=False, widget=forms.Textarea)
    website = forms.CharField(required=False)  # honeypot

    def __init__(self, *args, survey_slug=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey_slug = survey_slug
        self.survey = get_survey(survey_slug) or {}
        self.answers = {}

    def clean_website(self):
        if (self.cleaned_data.get("website") or "").strip():
            raise forms.ValidationError("invalid")
        return ""

    def clean_reason(self):
        return (self.cleaned_data.get("reason") or "").strip()

    def clean(self):
        cleaned = super().clean()
        answers = {}
        for key, q in (self.survey.get("questions") or {}).items():
            valid = {v for v, _ in q.get("choices", [])}
            val = (self.data.get(key) or "").strip()
            if val:
                if val not in valid:
                    self.add_error(None, f"「{q.get('label', key)}」の回答が不正です。")
                else:
                    answers[key] = val
            elif q.get("required"):
                self.add_error(None, "必須の質問にお答えください。")
        self.answers = answers
        return cleaned
