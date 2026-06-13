from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import EmailAuthenticationForm, ProfileEditForm, SignUpForm
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
    from apps.reviews.models import Review
    reviews = request.user.reviews.select_related("product").order_by("-created_at")
    bookmarks = (
        request.user.bookmarks
        .select_related("product", "product__product_type")
        .order_by("-created_at")
    )
    helpful_reviews = (
        Review.objects.filter(helpfuls__user=request.user, is_approved=True)
        .select_related("product", "user")
        .order_by("-helpfuls__created_at")
    )
    from .missions import mission_summary
    return render(request, "accounts/profile.html", {
        "reviews": reviews,
        "bookmarks": bookmarks,
        "helpful_reviews": helpful_reviews,
        "mission_summary": mission_summary(request.user),
    })


@login_required
def user_detail(request, pk):
    """他の会員が閲覧できる公開ユーザーページ。

    マイページの公開サブセット（プロフィール・実績・投稿口コミ）を表示する。
    メールアドレス・気になる・ミッション等の非公開情報は出さない。
    """
    # is_active=False はWP取り込みの投稿者アカウント（ログイン不可）も含むため、
    # 公開ページ自体はそれらも閲覧できるようにする。
    # 他人の staff/superuser ページは非公開にするが、自分のページは常に閲覧可。
    profile_user = get_object_or_404(User, pk=pk)
    is_own = request.user.pk == profile_user.pk
    if not is_own and (profile_user.is_staff or profile_user.is_superuser):
        raise Http404("ページが見つかりません")
    reviews = (
        profile_user.reviews.filter(is_approved=True)
        .select_related("product", "product__product_type")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    from apps.reviews.models import ReviewImage
    photos = (
        ReviewImage.objects.filter(
            review__user=profile_user, review__is_approved=True
        )
        .select_related("review", "review__product")
        .order_by("-id")
    )
    bookmarks = (
        profile_user.bookmarks
        .select_related("product", "product__product_type")
        .order_by("-created_at")
    )
    return render(request, "accounts/user_detail.html", {
        "profile_user": profile_user,
        "reviews": reviews,
        "photos": photos,
        "bookmarks": bookmarks,
        "is_own": is_own,
    })


@login_required
def missions(request):
    from .missions import user_mission_overview
    overview = user_mission_overview(request.user)
    return render(request, "accounts/missions.html", {
        "missions": overview,
        "completed_count": sum(1 for d in overview if d["is_complete"]),
        "total_count": len(overview),
    })


@login_required
@require_POST
def mission_alerts_seen(request):
    """お祝いポップアップ表示後に達成記録を既読化する（JSから呼ぶ）。"""
    from .missions import mark_completions_seen
    ids = request.POST.getlist("ids")
    ids = [int(i) for i in ids if i.isdigit()]
    mark_completions_seen(request.user, ids or None)
    return JsonResponse({"ok": True})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "プロフィールを更新しました。")
            return redirect("accounts:profile")
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


class EmailLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "accounts/login.html"


class AppLogoutView(LogoutView):
    next_page = "products:list"
