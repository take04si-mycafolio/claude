from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="メールアドレス", required=True)
    nickname = forms.CharField(label="ニックネーム", max_length=50, required=True)

    class Meta:
        model = User
        fields = ("email", "nickname", "age_range", "skin_type", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]
        user.nickname = self.cleaned_data["nickname"]
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="メールアドレス")


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "nickname", "avatar", "bio",
            "age_range", "skin_type", "gender",
            "twitter", "instagram", "tiktok", "youtube_url", "website_url",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "maxlength": 300,
                                         "placeholder": "自己紹介を300字以内で"}),
            "twitter": forms.TextInput(attrs={"placeholder": "yourname"}),
            "instagram": forms.TextInput(attrs={"placeholder": "yourname"}),
            "tiktok": forms.TextInput(attrs={"placeholder": "yourname"}),
            "youtube_url": forms.URLInput(attrs={"placeholder": "https://youtube.com/@..."}),
            "website_url": forms.URLInput(attrs={"placeholder": "https://example.com/"}),
        }

    def clean_twitter(self):
        return self.cleaned_data["twitter"].lstrip("@")

    def clean_instagram(self):
        return self.cleaned_data["instagram"].lstrip("@")

    def clean_tiktok(self):
        return self.cleaned_data["tiktok"].lstrip("@")
