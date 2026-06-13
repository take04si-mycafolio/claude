"""ミッション進捗の評価・達成確定（遅延再計算）。

シグナルで逐次更新せず、会員がミッションページ/マイページを開いた時点で
既存の集計から現在値を再計算して達成判定する。達成は UserMissionCompletion に
永続化し、配布コードを確定（ロック）する。
"""
from django.db import transaction
from django.utils import timezone

from .models import (
    ActionType,
    CodeMode,
    CompletionStatus,
    Mission,
    MissionRewardCode,
    UserMissionCompletion,
)


def _profile_complete(user) -> bool:
    return bool(user.nickname and user.age_range and user.skin_type)


def _window(qs, since, until):
    """created_at をキャンペーン期間 [since, until] で絞り込む。"""
    if since is not None:
        qs = qs.filter(created_at__gte=since)
    if until is not None:
        qs = qs.filter(created_at__lte=until)
    return qs


def action_current_count(user, action_type: str, since=None, until=None) -> int:
    """指定アクションの達成回数を算出する。

    カウント系（口コミ・参考になった・気になる）は実イベントを created_at で
    期間（since〜until）に絞って数える。状態系（メール認証・プロフィール完成・
    SNS連携）は「現在その状態か」を真偽で返す（期間の概念なし）。
    """
    if action_type == ActionType.REVIEW:
        return _window(
            user.reviews.filter(is_approved=True), since, until
        ).count()
    if action_type == ActionType.REVIEW_WITH_PHOTO:
        return _window(
            user.reviews.filter(is_approved=True, images__isnull=False),
            since, until,
        ).distinct().count()
    if action_type == ActionType.HELPFUL:
        from apps.reviews.models import ReviewHelpful
        return _window(
            ReviewHelpful.objects.filter(
                review__user=user, review__is_approved=True
            ),
            since, until,
        ).count()
    if action_type == ActionType.BOOKMARK:
        return _window(user.bookmarks, since, until).count()
    if action_type == ActionType.EMAIL_VERIFIED:
        return 1 if user.email_verified else 0
    if action_type == ActionType.PROFILE_COMPLETE:
        return 1 if _profile_complete(user) else 0
    if action_type == ActionType.SNS_TWITTER:
        return 1 if user.twitter else 0
    if action_type == ActionType.SNS_INSTAGRAM:
        return 1 if user.instagram else 0
    if action_type == ActionType.SNS_TIKTOK:
        return 1 if user.tiktok else 0
    if action_type == ActionType.SNS_YOUTUBE:
        return 1 if user.youtube_url else 0
    return 0


def evaluate_mission(user, mission) -> dict:
    """1ミッションの進捗を評価して、テンプレ用の構造化データを返す。"""
    steps = []
    done_steps = 0
    since, until = mission.starts_at, mission.ends_at
    for step in mission.steps.all():
        current = action_current_count(user, step.action_type, since, until)
        target = step.target_count
        is_done = current >= target
        if is_done:
            done_steps += 1
        steps.append({
            "label": step.display_label(),
            "current": min(current, target),
            "target": target,
            "is_done": is_done,
            "percent": 100 if is_done else (
                int(current * 100 / target) if target else 0
            ),
        })
    total = len(steps)
    is_complete = total > 0 and done_steps == total
    return {
        "mission": mission,
        "steps": steps,
        "done_steps": done_steps,
        "total_steps": total,
        "is_complete": is_complete,
        "percent": int(done_steps * 100 / total) if total else 0,
    }


@transaction.atomic
def claim_if_complete(user, mission) -> UserMissionCompletion | None:
    """全ステップ達成済みなら達成記録を作成しコードを確定する（冪等）。

    先着・数量限定に対応するため、ミッション行をロックして配布枠を数えてから
    確定する。上限に達していれば status=SOLD_OUT で記録（プレゼント対象外）。
    既に記録があればそれを返す。
    """
    # 参加ランク条件（下限〜上限）外なら確定しない
    if not mission.level_eligible(user.review_level):
        return None

    # 先着カウントを直列化するためミッション行をロック
    mission = Mission.objects.select_for_update().get(pk=mission.pk)

    completion = (
        UserMissionCompletion.objects
        .filter(user=user, mission=mission)
        .first()
    )
    if completion is not None:
        return completion

    # 期間外（開始前・終了後）は新規の達成を確定しない（既存記録は上で保持）
    if not mission.is_open():
        return None

    # 配布上限チェック（獲得＋準備中で確保済みの枠を数える）
    if mission.reward_limit is not None and mission.slots_used() >= mission.reward_limit:
        return UserMissionCompletion.objects.create(
            user=user, mission=mission,
            assigned_code="", status=CompletionStatus.SOLD_OUT,
        )

    # 枠あり → コードを割り当て
    assigned_code = ""
    status = CompletionStatus.AWARDED
    if mission.code_mode == CodeMode.SHARED:
        assigned_code = mission.shared_code
    else:
        pooled = (
            MissionRewardCode.objects
            .select_for_update(skip_locked=True)
            .filter(mission=mission, assigned_to__isnull=True)
            .order_by("id")
            .first()
        )
        if pooled is not None:
            pooled.assigned_to = user
            pooled.assigned_at = timezone.now()
            pooled.save(update_fields=["assigned_to", "assigned_at"])
            assigned_code = pooled.code
        else:
            # 枠はあるがコードプールが空 → 準備中（管理者の補充待ち）
            status = CompletionStatus.PENDING

    return UserMissionCompletion.objects.create(
        user=user, mission=mission,
        assigned_code=assigned_code, status=status,
    )


def user_mission_overview(user) -> list[dict]:
    """公開中の全ミッションを評価し、達成分は確定まで行ってデータを返す。"""
    missions = (
        Mission.objects.filter(is_active=True).prefetch_related("steps")
    )
    overview = []
    for mission in missions:
        data = evaluate_mission(user, mission)
        # 参加ランク条件（下限〜上限の範囲）
        data["min_level"] = mission.min_review_level
        data["max_level"] = mission.max_review_level
        data["level_label"] = mission.level_condition_label()
        data["eligible"] = mission.level_eligible(user.review_level)
        # ランク不足（下限未満）と、ランク超過（上限超え）を区別する
        data["below_level"] = user.review_level < mission.min_review_level
        data["above_level"] = user.review_level > mission.max_review_level
        data["locked"] = not data["eligible"]
        if data["is_complete"] and data["eligible"]:
            completion = claim_if_complete(user, mission)
            data["completion"] = completion
            data["status"] = completion.status if completion else ""
            data["reward_code"] = completion.assigned_code if completion else ""
            data["code_pending"] = bool(
                completion and completion.status == CompletionStatus.PENDING
            )
            data["missed"] = bool(
                completion and completion.status == CompletionStatus.SOLD_OUT
            )
        else:
            data["completion"] = None
            data["status"] = ""
            data["reward_code"] = ""
            data["code_pending"] = False
            data["missed"] = False
        # 先着・数量限定の残数（無制限なら None）
        data["limit"] = mission.reward_limit
        data["remaining"] = mission.slots_remaining()
        data["sold_out"] = mission.is_sold_out()
        # キャンペーン期間の状態
        data["starts_at"] = mission.starts_at
        data["ends_at"] = mission.ends_at
        data["not_started"] = not mission.has_started()
        data["ended"] = mission.has_ended()
        overview.append(data)
    return overview


def sync_user_missions(user) -> None:
    """ユーザーの全公開ミッションを再評価し、達成済みのものを確定する。

    シグナル（口コミ投稿・気になる登録・参考になった獲得・プロフィール更新等）
    から呼ばれ、アクションした瞬間に達成記録を作る。新規達成は seen_at=None で
    作られ、次の画面表示時にお祝いポップアップとして通知される。
    """
    missions = Mission.objects.filter(is_active=True).prefetch_related("steps")
    for mission in missions:
        if evaluate_mission(user, mission)["is_complete"]:
            claim_if_complete(user, mission)


def unseen_completions(user):
    """まだお祝いを表示していない達成記録（新しい順）。"""
    return list(
        user.mission_completions
        .filter(seen_at__isnull=True)
        .select_related("mission")
        .order_by("-completed_at")
    )


def mark_completions_seen(user, ids=None) -> int:
    """達成記録を表示済みにする。ids 指定時はそれだけ、未指定なら未読全件。"""
    qs = user.mission_completions.filter(seen_at__isnull=True)
    if ids:
        qs = qs.filter(id__in=ids)
    return qs.update(seen_at=timezone.now())


def mission_summary(user, limit: int = 3) -> dict:
    """マイページ用サマリ（上位 limit 件 + 達成数/全体数）。"""
    overview = user_mission_overview(user)
    completed = sum(1 for d in overview if d["is_complete"])
    return {
        "items": overview[:limit],
        "completed": completed,
        "total": len(overview),
    }
