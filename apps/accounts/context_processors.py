from .missions import unseen_completions


def mission_alerts(request):
    """未表示のミッション達成をテンプレ共通で渡す（お祝いポップアップ用）。

    読み取りのみ。表示済みフラグは、モーダル表示後にJSが叩く
    accounts:mission_alerts_seen で立てる。
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"mission_alerts": []}
    # 管理画面では出さない（消費もしない）
    if request.path.startswith("/admin"):
        return {"mission_alerts": []}
    return {"mission_alerts": unseen_completions(user)}
