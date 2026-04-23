from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="星評価",
        choices=[(i, f"{i}★") for i in range(5, 0, -1)],
        coerce=int,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Review
        fields = ("rating", "title", "body", "usage_period", "effectiveness", "skin_type")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6, "placeholder": "実際に使った感想を詳しくお書きください"}),
            "title": forms.TextInput(attrs={"placeholder": "例: 1ヶ月使って肌が明るくなりました"}),
        }
