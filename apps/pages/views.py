from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ContactForm
from .models import LegalDocument


def _legal(request, doc_type):
    """規約・ポリシー共通ビュー。管理画面で編集された LegalDocument を描画する。
    WEBとアプリ(API)が同じレコードを参照し内容のズレを無くす。"""
    doc = get_object_or_404(LegalDocument, doc_type=doc_type, is_published=True)
    return render(request, "pages/legal.html", {"doc": doc})


def terms(request):
    return _legal(request, "terms")


def privacy(request):
    return _legal(request, "privacy")


def community_guidelines(request):
    return _legal(request, "community")


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            cm = form.save(commit=False)
            cm.ip = _get_ip(request)
            cm.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            cm.save()
            _try_notify_admin(cm, request)
            messages.success(request, "お問い合わせを受け付けました。返信は通常2〜3営業日以内にお送りいたします。")
            return redirect("pages:contact_thanks")
    else:
        form = ContactForm()
    return render(request, "pages/contact.html", {"form": form})


def contact_thanks(request):
    return render(request, "pages/contact_thanks.html")


def _get_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _try_notify_admin(cm, request):
    """管理者にメール通知(SMTP設定があれば)"""
    try:
        admin_email = getattr(settings, "CONTACT_NOTIFY_TO", None) or getattr(settings, "DEFAULT_FROM_EMAIL", None)
        if not admin_email:
            return
        admin_url = request.build_absolute_uri(
            reverse("admin:pages_contactmessage_change", args=[cm.pk])
        )
        send_mail(
            subject=f"[TUSHOU お問い合わせ] {cm.subject}",
            message=(
                f"差出人: {cm.name or '(匿名)'} <{cm.email}>\n"
                f"受信日時: {cm.created_at:%Y-%m-%d %H:%M:%S}\n"
                f"\n--- 内容 ---\n{cm.body}\n\n"
                f"管理画面で確認: {admin_url}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception:
        pass


def post_review_lp(request):
    """口コミ投稿促進LP"""
    return render(request, "pages/post_review_lp.html")
