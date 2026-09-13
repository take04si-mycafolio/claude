"""ミッション集計のテスト（ステップの最低文字数条件）。

MissionStep.min_body_length を設定すると、本文がその文字数以上の口コミだけが
達成回数にカウントされることを検証する。日本語はマルチバイトのため、
バイト数でなく文字数で数えられることも確認する。
"""
import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.missions import action_current_count, evaluate_mission
from apps.accounts.models import ActionType, Mission, MissionStep
from apps.products.models import Product
from apps.reviews.models import Review, ReviewImage


def _make_user(email):
    User = get_user_model()
    return User.objects.create(email=email, username=email.split("@")[0])


def _make_review(user, product, body, approved=True):
    return Review.objects.create(
        user=user, product=product, rating=5, title="t", body=body,
        is_approved=approved,
    )


def _png_upload(name="t.png"):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class MinBodyLengthCountTests(TestCase):
    def setUp(self):
        self.user = _make_user("min@example.com")
        self.product = Product.objects.create(name="商品m", slug="m1")

    def test_review_count_filters_by_min_body_length(self):
        _make_review(self.user, self.product, "あ" * 30)
        p2 = Product.objects.create(name="商品m2", slug="m2")
        _make_review(self.user, p2, "い" * 100)

        self.assertEqual(
            action_current_count(self.user, ActionType.REVIEW), 2
        )
        self.assertEqual(
            action_current_count(
                self.user, ActionType.REVIEW, min_body_length=50
            ),
            1,
        )
        # 境界値: ちょうど最低文字数なら数える
        self.assertEqual(
            action_current_count(
                self.user, ActionType.REVIEW, min_body_length=100
            ),
            1,
        )
        self.assertEqual(
            action_current_count(
                self.user, ActionType.REVIEW, min_body_length=101
            ),
            0,
        )

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_photo_review_count_filters_by_min_body_length(self):
        short = _make_review(self.user, self.product, "あ" * 30)
        ReviewImage.objects.create(review=short, image=_png_upload())
        p2 = Product.objects.create(name="商品m3", slug="m3")
        long = _make_review(self.user, p2, "い" * 100)
        ReviewImage.objects.create(review=long, image=_png_upload())

        self.assertEqual(
            action_current_count(self.user, ActionType.REVIEW_WITH_PHOTO), 2
        )
        self.assertEqual(
            action_current_count(
                self.user, ActionType.REVIEW_WITH_PHOTO, min_body_length=50
            ),
            1,
        )

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_evaluate_mission_uses_step_min_body_length(self):
        mission = Mission.objects.create(title="写真付き100文字", is_active=True)
        MissionStep.objects.create(
            mission=mission, action_type=ActionType.REVIEW_WITH_PHOTO,
            target_count=1, min_body_length=100,
        )
        short = _make_review(self.user, self.product, "あ" * 50)
        ReviewImage.objects.create(review=short, image=_png_upload())

        data = evaluate_mission(self.user, mission)
        self.assertFalse(data["is_complete"])
        self.assertEqual(data["steps"][0]["current"], 0)

        p2 = Product.objects.create(name="商品m4", slug="m4")
        long = _make_review(self.user, p2, "い" * 100)
        ReviewImage.objects.create(review=long, image=_png_upload())

        data = evaluate_mission(self.user, mission)
        self.assertTrue(data["is_complete"])
        self.assertEqual(data["steps"][0]["current"], 1)


class MinBodyLengthLabelTests(TestCase):
    def _step(self, **kwargs):
        mission = Mission.objects.create(title="L", is_active=True)
        return MissionStep.objects.create(mission=mission, **kwargs)

    def test_display_label_includes_min_body_length(self):
        step = self._step(
            action_type=ActionType.REVIEW_WITH_PHOTO, min_body_length=100,
        )
        self.assertEqual(
            step.display_label(), "写真付きで口コミを投稿する（100文字以上）"
        )

    def test_display_label_combines_length_and_count(self):
        step = self._step(
            action_type=ActionType.REVIEW, target_count=2, min_body_length=50,
        )
        self.assertEqual(
            step.display_label(), "口コミを投稿する（50文字以上・2回）"
        )

    def test_display_label_ignores_length_for_non_review_actions(self):
        step = self._step(
            action_type=ActionType.BOOKMARK, min_body_length=100,
        )
        self.assertEqual(step.display_label(), "「気になる」に登録する")

    def test_custom_label_wins(self):
        step = self._step(
            action_type=ActionType.REVIEW_WITH_PHOTO, min_body_length=100,
            label="写真つきレビューを書こう",
        )
        self.assertEqual(step.display_label(), "写真つきレビューを書こう")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CategoryBadgeTests(TestCase):
    """カテゴリバッジ(「◯◯マスター」)の付与条件テスト。

    条件: カテゴリごとに写真付き口コミ10商品以上 かつ 「参考になった」が
    口コミ1件あたり平均50以上。境界値(ちょうど10件・平均ちょうど50)で付与、
    どちらか片方でも下回ると付与しない。
    """

    @classmethod
    def setUpTestData(cls):
        from apps.products.models import Category
        from apps.reviews.models import ReviewHelpful, ReviewImage

        User = get_user_model()
        cls.owner = _make_user("badge@example.com")
        cls.ptype = Category.objects.create(name="美顔器")
        # 写真付き承認済み口コミ×10商品
        cls.reviews = []
        for i in range(10):
            p = Product.objects.create(
                name=f"美顔器{i}", slug=f"bg{i}", product_type=cls.ptype,
            )
            r = _make_review(cls.owner, p, "使い心地の記録です", approved=True)
            ReviewImage.objects.create(review=r, image=_png_upload(f"b{i}.png"))
            cls.reviews.append(r)
        # 「参考になった」500件(平均ちょうど50)。bulk_create でシグナルを発火させない。
        voters = User.objects.bulk_create(
            User(username=f"v{i}", email=f"v{i}@example.com") for i in range(500)
        )
        ReviewHelpful.objects.bulk_create(
            ReviewHelpful(user=voters[i], review=cls.reviews[i // 50])
            for i in range(500)
        )

    def _fresh_owner(self):
        # cached_property を避けるため毎回取り直す
        return get_user_model().objects.get(pk=self.owner.pk)

    def test_badge_awarded_at_exact_thresholds(self):
        user = self._fresh_owner()
        self.assertEqual(user.category_badges, ["美顔器マスター"])
        self.assertEqual(user.category_badge, "美顔器マスター")

    def test_no_badge_when_average_below_50(self):
        from apps.reviews.models import ReviewHelpful
        ReviewHelpful.objects.filter(review=self.reviews[0]).first().delete()
        user = self._fresh_owner()  # 499 / 10 = 49.9
        self.assertEqual(user.category_badges, [])
        self.assertIsNone(user.category_badge)

    def test_no_badge_with_nine_photo_reviews(self):
        # 写真を1件分消すと写真付きは9商品(平均は50のまま) → 付与しない
        self.reviews[0].images.all().delete()
        user = self._fresh_owner()
        self.assertEqual(user.category_badges, [])

    def test_average_counts_all_reviews_in_category(self):
        # 写真なしの11件目を足すと平均が 500/11 < 50 に下がる → 付与しない
        p = Product.objects.create(
            name="美顔器x", slug="bgx", product_type=self.ptype,
        )
        _make_review(self.owner, p, "写真なしの口コミ", approved=True)
        user = self._fresh_owner()
        self.assertEqual(user.category_badges, [])

    def test_unapproved_reviews_do_not_count(self):
        # 未承認の口コミは分母にも分子にも入らない(平均50を維持)
        p = Product.objects.create(
            name="美顔器y", slug="bgy", product_type=self.ptype,
        )
        _make_review(self.owner, p, "承認待ちの口コミ", approved=False)
        user = self._fresh_owner()
        self.assertEqual(user.category_badges, ["美顔器マスター"])

    def test_old_rule_three_reviews_no_longer_grants(self):
        # 旧条件(カテゴリ3件で付与)の回帰確認: 写真・参考になったが無ければ付与しない
        other = _make_user("old-rule@example.com")
        for i in range(3):
            p = Product.objects.create(
                name=f"旧基準{i}", slug=f"old{i}", product_type=self.ptype,
            )
            _make_review(other, p, "テキストのみ", approved=True)
        user = get_user_model().objects.get(pk=other.pk)
        self.assertEqual(user.category_badges, [])
        self.assertIsNone(user.category_badge)


class RewardApprovalTests(TestCase):
    """ミッション特典の運営承認制のテスト。

    達成時点ではコードを発行せず「承認待ち」で記録し、approve_completion で
    コード発行、send_reward_code_email でメール案内することを検証する。
    """

    def setUp(self):
        self.user = _make_user("reward@example.com")
        self.product = Product.objects.create(name="商品r", slug="r1")

    def _shared_mission(self, code="COUPON10"):
        mission = Mission.objects.create(
            title="口コミ1件", is_active=True,
            shared_code=code,
        )
        MissionStep.objects.create(
            mission=mission, action_type=ActionType.REVIEW, target_count=1,
        )
        return mission

    def test_claim_creates_waiting_without_code(self):
        from apps.accounts.missions import claim_if_complete
        from apps.accounts.models import CompletionStatus

        mission = self._shared_mission()
        review = _make_review(self.user, self.product, "とても良い", approved=True)
        completion = claim_if_complete(self.user, mission)

        self.assertEqual(completion.status, CompletionStatus.WAITING)
        self.assertEqual(completion.assigned_code, "")
        self.assertIsNone(completion.approved_at)
        # 承認待ちの時点で口コミは消費済み（別キャンペーンへの二重算入防止）
        review.refresh_from_db()
        self.assertIsNotNone(review.campaign_consumed_at)

    def test_approve_assigns_shared_code_and_email(self):
        from django.core import mail

        from apps.accounts.missions import (
            approve_completion,
            claim_if_complete,
            send_reward_code_email,
        )
        from apps.accounts.models import CompletionStatus

        mission = self._shared_mission()
        _make_review(self.user, self.product, "とても良い", approved=True)
        completion = claim_if_complete(self.user, mission)

        completion = approve_completion(completion)
        self.assertEqual(completion.status, CompletionStatus.AWARDED)
        self.assertEqual(completion.assigned_code, "COUPON10")
        self.assertIsNotNone(completion.approved_at)
        self.assertIsNone(completion.seen_at)  # ポップアップ再表示

        self.assertTrue(send_reward_code_email(completion))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("COUPON10", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["reward@example.com"])
        self.assertIsNotNone(completion.code_sent_at)
        # 二重送信しない
        self.assertFalse(send_reward_code_email(completion))
        self.assertEqual(len(mail.outbox), 1)

    def test_approve_with_empty_pool_stays_pending_then_awarded(self):
        from apps.accounts.missions import approve_completion, claim_if_complete
        from apps.accounts.models import (
            CodeMode,
            CompletionStatus,
            MissionRewardCode,
        )

        mission = Mission.objects.create(
            title="個別コード", is_active=True, code_mode=CodeMode.UNIQUE,
        )
        MissionStep.objects.create(
            mission=mission, action_type=ActionType.REVIEW, target_count=1,
        )
        _make_review(self.user, self.product, "とても良い", approved=True)
        completion = claim_if_complete(self.user, mission)

        # プールが空 → 承認しても準備中
        completion = approve_completion(completion)
        self.assertEqual(completion.status, CompletionStatus.PENDING)
        self.assertEqual(completion.assigned_code, "")

        # コード補充後に再実行 → 発行
        MissionRewardCode.objects.create(mission=mission, code="SERIAL-1")
        completion = approve_completion(completion)
        self.assertEqual(completion.status, CompletionStatus.AWARDED)
        self.assertEqual(completion.assigned_code, "SERIAL-1")

    def test_approve_is_idempotent_for_awarded(self):
        from apps.accounts.missions import approve_completion, claim_if_complete
        from apps.accounts.models import CompletionStatus

        mission = self._shared_mission()
        _make_review(self.user, self.product, "とても良い", approved=True)
        completion = approve_completion(claim_if_complete(self.user, mission))
        again = approve_completion(completion)
        self.assertEqual(again.status, CompletionStatus.AWARDED)
        self.assertEqual(again.assigned_code, "COUPON10")

    def test_review_approval_triggers_mission_completion(self):
        """口コミは投稿時でなく承認時点でミッション完了処理が走る。"""
        from apps.accounts.models import CompletionStatus, UserMissionCompletion

        mission = self._shared_mission()
        # 投稿時点(承認待ち)では達成記録は作られない
        with self.captureOnCommitCallbacks(execute=True):
            review = _make_review(
                self.user, self.product, "とても良い", approved=False
            )
        self.assertFalse(
            UserMissionCompletion.objects.filter(
                user=self.user, mission=mission
            ).exists()
        )
        # 運営承認(保存)でシグナル→達成記録(承認待ち)が作られる
        with self.captureOnCommitCallbacks(execute=True):
            review.is_approved = True
            review.save(update_fields=["is_approved"])
        completion = UserMissionCompletion.objects.get(
            user=self.user, mission=mission
        )
        self.assertEqual(completion.status, CompletionStatus.WAITING)
