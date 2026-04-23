from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Product

from .forms import ReviewForm
from .models import Review


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
            messages.success(
                request,
                "口コミを投稿しました。ありがとうございます！これで他の口コミも閲覧できます。",
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
    """全商品の口コミ一覧(ゲート対象)"""
    if not request.user.is_authenticated:
        messages.info(request, "口コミを閲覧するにはログインが必要です。")
        return redirect("accounts:login")
    if not request.user.reviews.exists():
        messages.info(
            request,
            "口コミを閲覧するには、ご自身で1件以上の口コミを投稿してください。",
        )
        return redirect("products:list")
    reviews = (
        Review.objects.filter(is_approved=True)
        .select_related("product", "user")
        .order_by("-created_at")[:100]
    )
    return render(request, "reviews/review_list.html", {"reviews": reviews})
