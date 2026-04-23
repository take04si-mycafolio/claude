def gate_status(request):
    """テンプレートで {{ can_view_reviews }} を使えるようにする"""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"can_view_reviews": False, "has_written_review": False}
    has_written = user.reviews.exists()
    return {"can_view_reviews": has_written, "has_written_review": has_written}
