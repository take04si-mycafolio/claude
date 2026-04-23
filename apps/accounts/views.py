from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .forms import EmailAuthenticationForm, SignUpForm
from .models import User
from .tokens import email_verification_token


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification_email(request, user)
            login(request, user)
            messages.success(
                request,
                "仮登録が完了しました。確認メールを送信しましたので、メール内のリンクをクリックして本登録を完了してください。",
            )
            return redirect("products:list")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


def _send_verification_email(request, user):
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verify_url = request.build_absolute_uri(
        reverse("accounts:verify_email", kwargs={"uidb64": uid, "token": token})
    )
    body = render_to_string(
        "accounts/emails/verify_email.txt",
        {"user": user, "verify_url": verify_url, "site_name": settings.SITE_NAME},
    )
    send_mail(
        subject=f"[{settings.SITE_NAME}] メールアドレスの確認",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None
    if user and email_verification_token.check_token(user, token):
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        messages.success(request, "メール認証が完了しました。")
        return redirect("accounts:profile")
    messages.error(request, "認証リンクが無効です。再度メール送信を試みてください。")
    return redirect("products:list")


@login_required
def resend_verification(request):
    if request.user.email_verified:
        messages.info(request, "既にメール認証済みです。")
        return redirect("accounts:profile")
    _send_verification_email(request, request.user)
    messages.success(request, "確認メールを再送しました。")
    return redirect("accounts:profile")


@login_required
def profile(request):
    reviews = request.user.reviews.select_related("product").order_by("-created_at")
    return render(request, "accounts/profile.html", {"reviews": reviews})


class EmailLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "accounts/login.html"


class AppLogoutView(LogoutView):
    next_page = "products:list"
