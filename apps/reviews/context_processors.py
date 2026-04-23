def gate_status(request):
    """テンプレート共通で使う閲覧権限情報"""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {
            "unlocked_product_type_ids": frozenset(),
            "has_any_review": False,
        }
    # ユーザーが投稿済みレビューの製品タイプIDセット
    type_ids = frozenset(
        user.reviews.filter(product__product_type__isnull=False)
        .values_list("product__product_type_id", flat=True)
        .distinct()
    )
    return {
        "unlocked_product_type_ids": type_ids,
        "has_any_review": user.reviews.exists(),
    }
