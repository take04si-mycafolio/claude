from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, models
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.products.models import Category, Product

from .forms import ReviewForm
from .models import Review, ReviewHelpful, ReviewImage


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
    existing = Review.objects.filter(product=product, user=request.user).first()
    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES, instance=existing)
        if form.is_valid():
            new_files = form.cleaned_data.get("images") or []
            # 編集時に削除対象としてチェックされた既存画像のID
            delete_ids = set()
            if existing:
                delete_ids = {
                    img.id for img in existing.images.all()
                    if str(img.id) in request.POST.getlist("delete_images")
                }
            kept = (existing.images.count() - len(delete_ids)) if existing else 0
            if kept + len(new_files) > ReviewImage.MAX_PER_REVIEW:
                form.add_error(
                    "images",
                    f"画像は1件の口コミにつき最大{ReviewImage.MAX_PER_REVIEW}枚までです。",
                )
            else:
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                try:
                    review.save()
                except IntegrityError:
                    messages.error(request, "すでにこの商品には口コミを投稿済みです。")
                    return redirect(product.get_absolute_url())
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
                    f"口コミを投稿しました。ありがとうございます！ これで「{type_name}」カテゴリの口コミを閲覧できます。",
                )
                return redirect(product.get_absolute_url())
    else:
        form = ReviewForm(instance=existing)
    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "product": product, "existing": existing},
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
