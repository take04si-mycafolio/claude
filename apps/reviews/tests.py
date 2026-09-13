"""口コミの論理削除とキャンペーン消費(不正対策)の挙動テスト。

検証する不正対策の柱:
- 論理削除: 削除した口コミはサイト表示・集計から消えるが行は残り運営のみ閲覧可。
- キャンペーン消費: 当選に算入された口コミは次のキャンペーンでカウントされず、
  会員からの削除もできない（当選後に消して賞品だけ残す不正の防止）。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import (
    ActionType,
    Mission,
    MissionStep,
    UserMissionCompletion,
)
from apps.products.models import Product
from apps.reviews.models import Review


def _make_user(email):
    User = get_user_model()
    return User.objects.create(email=email, username=email.split("@")[0])


def _make_product(slug):
    return Product.objects.create(name=f"商品{slug}", slug=slug)


def _make_review(user, product):
    # 承認制導入後の既定は承認待ち(False)。ここでは承認済み口コミを作る。
    return Review.objects.create(
        user=user, product=product, rating=5, title="t", body="b",
        is_approved=True,
    )


def _mission_review(title, target):
    m = Mission.objects.create(title=title, is_active=True)
    MissionStep.objects.create(
        mission=m, action_type=ActionType.REVIEW, target_count=target,
    )
    return m


class SoftDeleteTests(TestCase):
    def setUp(self):
        self.user = _make_user("a@example.com")
        self.product = _make_product("p1")

    def test_soft_delete_hides_from_default_manager(self):
        r = _make_review(self.user, self.product)
        r.soft_delete()
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(Review.all_objects.count(), 1)
        r.refresh_from_db()
        self.assertTrue(r.is_deleted)
        self.assertIsNotNone(r.deleted_at)
        self.assertEqual(r.delete_count, 1)

    def test_soft_delete_drops_review_count(self):
        r = _make_review(self.user, self.product)
        u = get_user_model().objects.get(pk=self.user.pk)
        self.assertEqual(u.review_count, 1)
        r.soft_delete()
        u = get_user_model().objects.get(pk=self.user.pk)
        self.assertEqual(u.review_count, 0)

    def test_consumed_review_cannot_be_soft_deleted(self):
        r = _make_review(self.user, self.product)
        r.campaign_consumed_at = timezone.now()
        r.save(update_fields=["campaign_consumed_at"])
        with self.assertRaises(PermissionError):
            r.soft_delete()


class CampaignConsumeTests(TestCase):
    def setUp(self):
        self.user = _make_user("b@example.com")
        self.p1 = _make_product("c1")
        self.p2 = _make_product("c2")

    def test_completed_mission_consumes_reviews_and_blocks_second(self):
        from apps.accounts.missions import sync_user_missions
        a = _mission_review("A", target=2)
        b = _mission_review("B", target=2)
        _make_review(self.user, self.p1)
        _make_review(self.user, self.p2)

        sync_user_missions(self.user)

        # 片方のミッションだけが当選確定し、その2件が消費される。
        completions = UserMissionCompletion.objects.filter(user=self.user)
        self.assertEqual(completions.count(), 1)
        won = completions.first().mission
        self.assertEqual(
            Review.all_objects.filter(
                user=self.user, campaign_consumed_at__isnull=False
            ).count(),
            2,
        )
        # もう片方のミッションは、同じ口コミが消費済みのため未達成のまま。
        other = b if won == a else a
        self.assertFalse(
            UserMissionCompletion.objects.filter(
                user=self.user, mission=other
            ).exists()
        )

    def test_won_mission_stays_complete_after_consumption(self):
        from apps.accounts.missions import sync_user_missions, evaluate_mission
        a = _mission_review("A", target=2)
        _make_review(self.user, self.p1)
        _make_review(self.user, self.p2)
        sync_user_missions(self.user)
        # 消費後に現在値が0でも、達成済み表示は維持される。
        data = evaluate_mission(self.user, a)
        self.assertTrue(data["is_complete"])

    def test_new_review_after_consumption_counts_for_next_campaign(self):
        from apps.accounts.missions import sync_user_missions
        _mission_review("A", target=2)
        _make_review(self.user, self.p1)
        _make_review(self.user, self.p2)
        sync_user_missions(self.user)
        self.assertEqual(
            UserMissionCompletion.objects.filter(user=self.user).count(), 1
        )
        # 新キャンペーンBと、新しい商品への新規口コミ2件は正当にカウントされる。
        b = _mission_review("B", target=2)
        _make_review(self.user, _make_product("c3"))
        _make_review(self.user, _make_product("c4"))
        sync_user_missions(self.user)
        self.assertTrue(
            UserMissionCompletion.objects.filter(
                user=self.user, mission=b
            ).exists()
        )
