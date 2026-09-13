"""口コミの承認制＋薬機法・景表法ゲートのテスト。

確認したい不変条件:
- 新規投稿(Web/API)は必ず承認待ち(is_approved=False)で作成される。
- NG表現を含む投稿はWebはフォームエラー、APIは400(compliance付き)で弾かれる。
- findings には該当箇所(match)・理由(reason)・言い換え例(example)が入る。
- 全該当箇所が機械置換できる場合のみ suggested_* に言い換え済み全文が入る。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.products.models import Product
from apps.reviews import compliance
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review


def _user(email):
    return get_user_model().objects.create(
        email=email, username=email.split("@")[0], nickname=email.split("@")[0],
    )


def _product(slug):
    return Product.objects.create(name=f"商品{slug}", slug=slug, is_published=True)


CLEAN_BODY = "1ヶ月使ってみて、私の肌には合っているように感じます。使い心地も良いです。"
NG_BODY_CRITICAL = "使い始めてからシミが消えました。本当にすごいです。"
NG_BODY_DROPIN = "絶対おすすめです。完全に気に入りました。"


class ComplianceModuleTests(TestCase):
    def test_detects_critical_with_reason_and_example(self):
        findings = compliance.find_violations(NG_BODY_CRITICAL)
        self.assertTrue(findings)
        f = findings[0]
        self.assertEqual(f["severity"], "CRITICAL")
        self.assertIn("シミ", f["match"])
        self.assertTrue(f["reason"])
        self.assertTrue(f["example"])

    def test_clean_text_passes(self):
        self.assertEqual(compliance.find_violations(CLEAN_BODY), [])

    def test_suggest_full_text_when_all_replaceable(self):
        suggested = compliance.suggest_full_text(NG_BODY_DROPIN)
        self.assertIsNotNone(suggested)
        self.assertNotIn("絶対", suggested)
        self.assertNotIn("完全に", suggested)
        # 言い換え後は再検査もクリアしている
        self.assertEqual(compliance.find_violations(suggested), [])

    def test_no_suggestion_when_structural_fix_needed(self):
        self.assertIsNone(compliance.suggest_full_text(NG_BODY_CRITICAL))


class ReviewFormGateTests(TestCase):
    def _form(self, body, title="使ってみた感想"):
        return ReviewForm(data={"rating": 5, "title": title, "body": body})

    def test_ng_body_blocks_submission_with_findings(self):
        form = self._form(NG_BODY_CRITICAL)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.compliance_findings)
        self.assertEqual(form.compliance_findings[0]["field"], "body")
        self.assertIn("body", form.errors)

    def test_dropin_body_gets_full_suggestion(self):
        form = self._form(NG_BODY_DROPIN)
        self.assertFalse(form.is_valid())
        self.assertIsNotNone(form.suggested_body)
        self.assertNotIn("絶対", form.suggested_body)

    def test_clean_body_passes_gate(self):
        form = self._form(CLEAN_BODY)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.compliance_findings, [])


class WebApprovalFlowTests(TestCase):
    def setUp(self):
        self.user = _user("alice@example.com")
        self.product = _product("p1")
        self.client.force_login(self.user)

    def test_new_review_is_pending(self):
        res = self.client.post(
            f"/reviews/new/{self.product.slug}/",
            {"rating": 5, "title": "使ってみた感想", "body": CLEAN_BODY},
        )
        self.assertEqual(res.status_code, 302)
        review = Review.objects.get(user=self.user, product=self.product)
        self.assertFalse(review.is_approved)

    def test_edit_resets_approval(self):
        Review.objects.create(
            user=self.user, product=self.product, rating=4,
            title="t", body="b", is_approved=True,
        )
        res = self.client.post(
            f"/reviews/new/{self.product.slug}/",
            {"rating": 5, "title": "使ってみた感想", "body": CLEAN_BODY},
        )
        self.assertEqual(res.status_code, 302)
        review = Review.objects.get(user=self.user, product=self.product)
        self.assertFalse(review.is_approved)

    def test_ng_body_rerenders_form_with_panel(self):
        res = self.client.post(
            f"/reviews/new/{self.product.slug}/",
            {"rating": 5, "title": "使ってみた感想", "body": NG_BODY_CRITICAL},
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "掲載できない表現")
        self.assertFalse(
            Review.objects.filter(user=self.user, product=self.product).exists()
        )


class ApiGateTests(APITestCase):
    def setUp(self):
        self.user = _user("alice@example.com")
        self.product = _product("p1")
        self.client.force_authenticate(self.user)

    def test_ng_body_returns_400_with_compliance(self):
        res = self.client.post(
            "/api/reviews/",
            {"product": self.product.id, "rating": 5,
             "title": "使ってみた感想", "body": NG_BODY_CRITICAL},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        comp = res.json()["compliance"]
        self.assertTrue(comp["findings"])
        f = comp["findings"][0]
        self.assertEqual(f["field"], "body")
        self.assertTrue(f["reason"])
        self.assertTrue(f["example"])
        self.assertIsNone(comp["suggested_body"])

    def test_dropin_body_returns_suggestion(self):
        res = self.client.post(
            "/api/reviews/",
            {"product": self.product.id, "rating": 5,
             "title": "使ってみた感想", "body": NG_BODY_DROPIN},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        suggested = res.json()["compliance"]["suggested_body"]
        self.assertIsNotNone(suggested)
        self.assertNotIn("絶対", suggested)

    def test_clean_post_creates_pending_review(self):
        res = self.client.post(
            "/api/reviews/",
            {"product": self.product.id, "rating": 5,
             "title": "使ってみた感想", "body": CLEAN_BODY},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.json()["is_approved"])
        review = Review.objects.get(user=self.user, product=self.product)
        self.assertFalse(review.is_approved)

    def test_use_log_gate(self):
        res = self.client.post(
            f"/api/products/{self.product.id}/use-logs/",
            {"body": NG_BODY_CRITICAL},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertTrue(res.json()["compliance"]["findings"])
