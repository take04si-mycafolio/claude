"""会員のアクション発生時にミッション達成を即時確定するシグナル。

口コミ投稿・「参考になった」獲得・「気になる」登録・プロフィール更新（メール認証含む）
をトリガーに、対象ユーザーのミッションを再評価して達成済みを確定する。新規達成は
seen_at=None で作られ、次の画面表示時にお祝いポップアップとして通知される。

集計（review_count 等）はコミット後の確定状態で行いたいので transaction.on_commit
を使い、ユーザーを pk から取り直して評価する。
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.reviews.models import Review, ReviewHelpful, ReviewImage

from .models import Bookmark
from .missions import sync_user_missions

User = get_user_model()


def _sync_later(user_id):
    """コミット後に最新状態でミッションを再評価（例外はアクションを妨げない）。"""
    def _run():
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return
        try:
            sync_user_missions(user)
        except Exception:  # ミッション処理の失敗で本来のアクションを壊さない
            pass
    transaction.on_commit(_run)


@receiver(post_save, sender=Review, dispatch_uid="mission_sync_on_review")
def _on_review(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _sync_later(instance.user_id)


@receiver(post_save, sender=ReviewImage, dispatch_uid="mission_sync_on_review_image")
def _on_review_image(sender, instance, raw=False, **kwargs):
    # 写真付き投稿ミッションの検知（画像は口コミ保存の後に作られるため）
    if raw:
        return
    _sync_later(instance.review.user_id)


@receiver(post_save, sender=ReviewHelpful, dispatch_uid="mission_sync_on_helpful")
def _on_helpful(sender, instance, raw=False, **kwargs):
    # 「参考になった」は口コミの投稿者の helpful_count を増やす
    if raw:
        return
    _sync_later(instance.review.user_id)


@receiver(post_save, sender=Bookmark, dispatch_uid="mission_sync_on_bookmark")
def _on_bookmark(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _sync_later(instance.user_id)


@receiver(post_save, sender=User, dispatch_uid="mission_sync_on_user")
def _on_user(sender, instance, raw=False, created=False, **kwargs):
    # メール認証・プロフィール完成（profile_complete）の検知
    if raw or created:
        return
    _sync_later(instance.pk)


def connect():
    # ready() から呼ぶ。@receiver で接続済みだが import を確実に通すための明示エントリ。
    return True
