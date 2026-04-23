from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Category, Product

from .forms import ReviewForm
from .models import Review


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
        form = ReviewForm(request.POST, instance=existing)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            try:
                review.save()
            except IntegrityError:
                messages.error(request, "すでにこの商品には口コミを投稿済みです。")
                return redirect(product.get_absolute_url())
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
    """全ユーザーの口コミ一覧（解放されている製品タイプのみ表示）"""
    if not request.user.is_authenticated:
        messages.info(request, "口コミを閲覧するにはログインが必要です。")
        return redirect("accounts:login")

    unlocked_type_ids = _unlocked_type_ids(request.user)

    if not unlocked_type_ids:
        messages.info(
            request,
            "口コミを閲覧するには、まずどれか1つの商品に口コミを投稿してください。投稿したカテゴリの口コミが閲覧できるようになります。",
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
