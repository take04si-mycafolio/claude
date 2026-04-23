from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Article, Category, Product


def _product_types():
    return Category.objects.filter(parent__isnull=True).order_by("sort_order", "name")


def _annotate(qs):
    return qs.annotate(
        avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        review_count=Count("reviews", filter=Q(reviews__is_approved=True)),
    )


def list_view(request):
    """トップ = 商品一覧（全製品タイプ）"""
    q = request.GET.get("q", "").strip()
    type_slug = request.GET.get("type", "").strip()
    function_slug = request.GET.get("category", "").strip()

    products = _annotate(
        Product.objects.filter(is_published=True).prefetch_related("categories", "product_type")
    )
    active_type = None
    if type_slug:
        active_type = Category.objects.filter(slug=type_slug, parent__isnull=True).first()
        if active_type:
            products = products.filter(product_type=active_type)
    if function_slug:
        products = products.filter(categories__slug=function_slug)
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q)
        )

    functions = []
    if active_type:
        functions = Category.objects.filter(parent=active_type).order_by("sort_order", "name")

    return render(
        request,
        "products/product_list.html",
        {
            "products": products.distinct(),
            "product_types": _product_types(),
            "active_type": active_type,
            "functions": functions,
            "active_function": function_slug,
            "q": q,
        },
    )


def type_detail(request, type_slug):
    """製品タイプ別ページ（例: /type/bigankiki/）"""
    ptype = get_object_or_404(Category, slug=type_slug, parent__isnull=True)
    q = request.GET.get("q", "").strip()
    function_slug = request.GET.get("category", "").strip()

    products = _annotate(
        Product.objects.filter(is_published=True, product_type=ptype)
        .prefetch_related("categories")
    )
    if function_slug:
        products = products.filter(categories__slug=function_slug)
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q)
        )

    functions = Category.objects.filter(parent=ptype).order_by("sort_order", "name")

    return render(
        request,
        "products/product_list.html",
        {
            "products": products.distinct(),
            "product_types": _product_types(),
            "active_type": ptype,
            "functions": functions,
            "active_function": function_slug,
            "q": q,
        },
    )


def detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("categories", "articles")
        .select_related("product_type"),
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
    can_view = False
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        if product.product_type_id:
            can_view = request.user.reviews.filter(
                product__product_type_id=product.product_type_id
            ).exists()

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
            "product_types": _product_types(),
        },
    )


def article_list(request):
    articles = Article.objects.filter(is_published=True)
    return render(
        request,
        "products/article_list.html",
        {"articles": articles, "product_types": _product_types()},
    )


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    return render(
        request,
        "products/article_detail.html",
        {"article": article, "product_types": _product_types()},
    )
