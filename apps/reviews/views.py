from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, models
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.products.models import Category, Product

from .forms import (
    ProductUseLogForm,
    ProductUseLogReportForm,
    ReviewForm,
    ReviewReportForm,
)
from .models import (
    ProductUseLog,
    ProductUseLogImage,
    ProductUseLogReport,
    Review,
    ReviewHelpful,
    ReviewImage,
    ReviewReport,
)


def _unlocked_type_ids(user):
    if not user.is_authenticated:
        return set()
    return set(
        user.reviews.filter(product__product_type__isnull=False)
        .values_list("product__product_type_id", flat=True)
        .distinct()
    )


@login_required
def create(request, slug):
    product = get_object_or_404(Product, slug=slug, is_published=True)
    # 過去に論理削除した口コミも拾い、再投稿時は同じ行を復活させる（created_at を保つ＝
    # 削除→再投稿でキャンペーン期間に滑り込ませる不正を防ぐ）。フォーム表示用には
    # 削除済みは編集対象にせず空フォームを出したいので、表示用 existing は別に持つ。
    existing = Review.all_objects.filter(product=product, user=request.user).first()
    form_instance = existing if (existing and not existing.is_deleted) else None
    reviving = bool(existing and existing.is_deleted)
    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES, instance=(existing or None))
        if form.is_valid():
            new_files = form.cleaned_data.get("images") or []
            # 編集時に削除対象としてチェックされた既存画像のID（復活時は旧画像を全消去）
            delete_ids = set()
            if form_instance:
                delete_ids = {
                    img.id for img in form_instance.images.all()
                    if str(img.id) in request.POST.getlist("delete_images")
                }
            kept = (form_instance.images.count() - len(delete_ids)) if form_instance else 0
            if kept + len(new_files) > ReviewImage.MAX_PER_REVIEW:
                form.add_error(
                    "images",
                    f"画像は1件の口コミにつき最大{ReviewImage.MAX_PER_REVIEW}枚までです。",
                )
            else:
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                # 新規・編集・復活のいずれも承認待ちに戻す（承認制）。
                # 編集で内容が変わった場合も再確認してから公開する。
                review.is_approved = False
                if reviving:
                    # 同じ行を復活（created_at は維持）。旧画像は持ち越さず作り直す。
                    review.is_deleted = False
                    review.deleted_at = None
                try:
                    review.save()
                except IntegrityError:
                    messages.error(request, "すでにこの商品には口コミを投稿済みです。")
                    return redirect(product.get_absolute_url())
                # 復活時は旧画像を実ファイルごと一掃してから新規分を入れる
                if reviving:
                    for img in review.images.all():
                        img.delete()
                # 既存画像の削除（実ファイルも消える）
                if delete_ids:
                    for img in review.images.filter(id__in=delete_ids):
                        img.delete()
                # 新規画像を圧縮して保存（圧縮は ReviewImage.save 内）
                start = (review.images.aggregate(m=models.Max("order"))["m"] or 0) + 1
                for i, f in enumerate(new_files):
                    ReviewImage.objects.create(review=review, image=f, order=start + i)
                type_name = product.product_type.name if product.product_type else "このカテゴリ"
                messages.success(
                    request,
                    "口コミを投稿しました。ありがとうございます！ 内容を確認のうえ掲載されます。"
                    f" 「{type_name}」カテゴリの口コミは今から閲覧できます。",
                )
                return redirect(product.get_absolute_url())
    else:
        form = ReviewForm(instance=form_instance)
    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "product": product, "existing": form_instance},
    )


def list_all(request):
    if not request.user.is_authenticated:
        messages.info(request, "口コミを閲覧するにはログインが必要です。")
        return redirect("accounts:login")

    unlocked_type_ids = _unlocked_type_ids(request.user)
    if not unlocked_type_ids:
        messages.info(
            request,
            "口コミを閲覧するには、まずどれか1つの商品に口コミを投稿してください。",
        )
        return redirect("products:list")

    reviews = (
        Review.objects.filter(
            is_approved=True, product__product_type_id__in=unlocked_type_ids
        )
        .select_related("product", "product__product_type", "user")
        .order_by("-created_at")[:100]
    )
    unlocked_types = Category.objects.filter(id__in=unlocked_type_ids)
    return render(
        request,
        "reviews/review_list.html",
        {"reviews": reviews, "unlocked_types": unlocked_types},
    )


@login_required
@require_POST
def delete(request, review_id):
    # 自分の口コミのみ削除可（他人/不存在は404）。論理削除（運営のみ閲覧可）にする。
    review = get_object_or_404(Review, pk=review_id, user=request.user)
    next_url = request.POST.get("next") or reverse("accounts:profile")
    if review.is_campaign_consumed:
        # キャンペーンの対象として算入済みの口コミは削除させない（当選後に消して賞品だけ
        # 残す不正・期間中の差し替えを防ぐ）。編集は引き続き可能。
        messages.error(
            request,
            "この口コミはキャンペーンの対象になっているため削除できません。内容の編集は可能です。",
        )
        return HttpResponseRedirect(next_url)
    review.soft_delete()
    messages.success(request, "口コミを削除しました。")
    return HttpResponseRedirect(next_url)


@login_required
@require_POST
def report(request, review_id):
    """口コミ通報を受け付ける（PC版Web）。

    重要: 通報されても口コミの自動削除・非表示は行わない。ReviewReport を作成して
    運営が管理画面で確認できるようにするだけ。
    - login_required + POSTのみ（匿名は通報不可）。
    - 自分の口コミは通報不可。
    - 既に通報済みなら二重登録せず「通報済み」を案内。
    - reason 不正・comment 超過はフォール検証で弾く（messages.error）。
    - token や個人情報、画像内容はログに出さない。
    """
    review = get_object_or_404(Review, pk=review_id)
    next_url = request.POST.get("next") or review.product.get_absolute_url()

    if review.user_id == request.user.id:
        messages.error(request, "自分の口コミは通報できません。")
        return HttpResponseRedirect(next_url)

    if ReviewReport.objects.filter(review=review, reporter=request.user).exists():
        messages.info(request, "この口コミはすでに通報済みです。運営が確認します。")
        return HttpResponseRedirect(next_url)

    form = ReviewReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "通報内容を確認してください。理由の選択が必要です。")
        return HttpResponseRedirect(next_url)

    reportobj = form.save(commit=False)
    reportobj.review = review
    reportobj.reporter = request.user
    try:
        reportobj.save()
    except IntegrityError:
        # 同時押下などで UniqueConstraint に触れた場合も重複として扱う。
        messages.info(request, "この口コミはすでに通報済みです。運営が確認します。")
        return HttpResponseRedirect(next_url)

    messages.success(request, "通報を受け付けました。ご協力ありがとうございます。運営が内容を確認します。")
    return HttpResponseRedirect(next_url)


@login_required
@require_POST
def helpful_toggle(request, review_id):
    review = get_object_or_404(Review, pk=review_id, is_approved=True)
    if review.user_id == request.user.id:
        messages.warning(request, "自分の口コミには「参考になった」できません。")
    else:
        h = ReviewHelpful.objects.filter(user=request.user, review=review).first()
        if h:
            h.delete()
        else:
            ReviewHelpful.objects.create(user=request.user, review=review)
    next_url = request.POST.get("next") or review.product.get_absolute_url()
    return HttpResponseRedirect(next_url)


# =============================================================================
# 使用記録（ProductUseLog）の PC版Web 投稿・削除・通報。
# 既存の口コミ view（create / delete / report）と同じ作法に揃える。
# 商品詳細ページのインラインフォーム/カードから POST され、完了後は詳細ページへ戻す。
# =============================================================================
@login_required
@require_POST
def use_log_create(request, slug):
    """使用記録を投稿する。本文必須・画像任意（最大4枚・既存口コミ画像と同一処理）。

    星評価は持たない（rating は受け取らない）。同じ商品に複数投稿できる。
    ログインユーザーが自分の通常口コミを持っていれば review に自動で紐付ける。
    成功/失敗いずれも messages を出して商品詳細へリダイレクトする。
    """
    product = get_object_or_404(Product, slug=slug, is_published=True)
    next_url = request.POST.get("next") or product.get_absolute_url()
    form = ProductUseLogForm(request.POST, request.FILES)
    if form.is_valid():
        new_files = form.cleaned_data.get("images") or []
        use_log = form.save(commit=False)
        use_log.product = product
        use_log.user = request.user
        # 任意: 同じ商品・同じ投稿者の通常口コミにのみ紐付ける（他人/別商品は無視）。
        review_id = request.POST.get("review_id")
        if review_id:
            rv = Review.objects.filter(
                pk=review_id, user=request.user, product=product
            ).first()
            if rv is not None:
                use_log.review = rv
        use_log.save()
        for i, f in enumerate(new_files):
            ProductUseLogImage.objects.create(use_log=use_log, image=f, order=i)
        messages.success(
            request, "使用記録を投稿しました。内容を確認のうえ掲載されます。"
        )
    else:
        # 本文空・文字数超過・画像エラーを商品詳細ページに表示する。
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect(next_url)


@login_required
@require_POST
def use_log_delete(request, use_log_id):
    """自分の使用記録のみ削除（論理削除）。他人/不存在は 404（URL直叩きでも削除不可）。"""
    use_log = get_object_or_404(ProductUseLog, pk=use_log_id, user=request.user)
    next_url = request.POST.get("next") or use_log.product.get_absolute_url()
    use_log.soft_delete()
    messages.success(request, "使用記録を削除しました。")
    return HttpResponseRedirect(next_url)


@login_required
@require_POST
def use_log_report(request, use_log_id):
    """使用記録を運営へ通報する。自分の使用記録は不可・二重通報は不可。

    通報されても自動削除・非表示はしない（受付レコードのみ作る）。既存の口コミ通報
    view と同じ作法。理由・コメントは ProductUseLogReportForm で検証する。
    """
    use_log = get_object_or_404(ProductUseLog, pk=use_log_id)
    next_url = request.POST.get("next") or use_log.product.get_absolute_url()

    if use_log.user_id == request.user.id:
        messages.error(request, "自分の使用記録は通報できません。")
        return HttpResponseRedirect(next_url)

    if ProductUseLogReport.objects.filter(
        use_log=use_log, reporter=request.user
    ).exists():
        messages.info(request, "この使用記録はすでに通報済みです。運営が確認します。")
        return HttpResponseRedirect(next_url)

    form = ProductUseLogReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "通報内容を確認してください。理由の選択が必要です。")
        return HttpResponseRedirect(next_url)

    reportobj = form.save(commit=False)
    reportobj.use_log = use_log
    reportobj.reporter = request.user
    try:
        reportobj.save()
    except IntegrityError:
        messages.info(request, "この使用記録はすでに通報済みです。運営が確認します。")
        return HttpResponseRedirect(next_url)

    messages.success(request, "通報を受け付けました。ご協力ありがとうございます。運営が内容を確認します。")
    return HttpResponseRedirect(next_url)


# ---- ゲスト口コミ投稿（メディアサイト方針 2026-09-06） ----------------------
# 会員登録なしで商品ページから投稿できる。承認制・薬機法ゲートは会員投稿と同一。
# ボット対策: honeypot(フォーム) + フォーム表示からの最小経過時間(署名付き) +
# IPハッシュのレート制限。生IPは保存しない。

import hashlib
import time as _time

from django.conf import settings
from django.core import signing
from django.utils import timezone as _guest_tz

from .forms import GuestReviewForm

GUEST_MIN_SECONDS = 5          # フォーム表示から送信までの最小秒数（即時送信=ボット）
GUEST_MAX_AGE = 7200           # フォームトークンの有効期限（2時間）
GUEST_DAILY_LIMIT_PER_IP = 3   # 同一IPからの1日の投稿上限


def _client_ip_hash(request):
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR", ""))
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()


def guest_form_token(slug):
    """商品ページ側でフォームに埋め込む署名付きトークン（発行時刻入り）。"""
    return signing.dumps({"slug": slug, "ts": int(_time.time())}, salt="guest-review")


def _check_guest_token(token, slug):
    try:
        data = signing.loads(token, salt="guest-review", max_age=GUEST_MAX_AGE)
    except signing.BadSignature:
        return "フォームの有効期限が切れました。ページを再読み込みしてください。"
    if data.get("slug") != slug:
        return "フォームの有効期限が切れました。ページを再読み込みしてください。"
    if int(_time.time()) - int(data.get("ts", 0)) < GUEST_MIN_SECONDS:
        return "送信が早すぎます。内容をご確認のうえ、もう一度お試しください。"
    return None


@require_POST
def guest_create(request, slug):
    product = get_object_or_404(Product, slug=slug, is_published=True)
    if request.user.is_authenticated:
        # 会員は既存のリッチフォーム（画像・詳細評価つき）へ
        return redirect("reviews:create", slug=product.slug)

    form = GuestReviewForm(request.POST)
    token_error = _check_guest_token(request.POST.get("form_token", ""), product.slug)
    ip_hash = _client_ip_hash(request)

    today = _guest_tz.localdate()
    posted_today = Review.all_objects.filter(
        ip_hash=ip_hash, created_at__date=today)
    rate_error = None
    if posted_today.count() >= GUEST_DAILY_LIMIT_PER_IP:
        rate_error = "本日の投稿上限に達しました。日を改めてお試しください。"
    elif posted_today.filter(product=product).exists():
        rate_error = "この商品には本日すでに投稿いただいています。"

    if form.is_valid() and not token_error and not rate_error:
        review = form.save(commit=False)
        review.product = product
        review.user = None
        review.ip_hash = ip_hash
        review.is_approved = False  # 承認制（承認センターで確認）
        review.save()
        messages.success(
            request,
            "評価を投稿いただきありがとうございます。内容を確認のうえ、このページに掲載されます。")
        return redirect(product.get_absolute_url())

    if token_error:
        messages.error(request, token_error)
    if rate_error:
        messages.error(request, rate_error)
    # 入力内容を失わないよう、専用ページでエラーと言い換え案を表示して再送できるようにする
    return render(request, "reviews/guest_review_form.html", {
        "form": form,
        "product": product,
        "form_token": guest_form_token(product.slug),
    })
