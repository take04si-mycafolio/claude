from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Article, Category, Product


def list_view(request):
    q = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()

    products = (
        Product.objects.filter(is_published=True)
        .annotate(
            avg_rating=Avg(
                "reviews__rating", filter=Q(reviews__is_approved=True)
            ),
            review_count=Count(
                "reviews", filter=Q(reviews__is_approved=True)
            ),
        )
        .prefetch_related("categories")
    )
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q)
        )
    if category_slug:
        products = products.filter(categories__slug=category_slug)

    categories = Category.objects.all()

    return render(
        request,
        "products/product_list.html",
        {
            "products": products,
            "categories": categories,
            "q": q,
            "active_category": category_slug,
        },
    )


def detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("categories", "articles"),
        slug=slug,
        is_published=True,
    )
    stats = product.review_stats()
    reviews = (
        product.reviews.filter(is_approved=True)
        .select_related("user")
        .order_by("-created_at")
    )
    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()

    can_view = False
    if request.user.is_authenticated:
        can_view = request.user.reviews.exists()

    # ゲート有効時は2件のみプレビュー表示
    preview_reviews = reviews[:2] if not can_view else None
    full_reviews = reviews if can_view else None

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "stats": stats,
            "reviews": full_reviews,
            "preview_reviews": preview_reviews,
            "user_review": user_review,
            "can_view": can_view,
        },
    )


def article_list(request):
    articles = Article.objects.filter(is_published=True)
    return render(request, "products/article_list.html", {"articles": articles})


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    return render(request, "products/article_detail.html", {"article": article})
