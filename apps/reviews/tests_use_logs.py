"""使用記録(ProductUseLog)API/モデルの最小動作確認テスト。

確認したい不変条件:
- 一覧/投稿/削除/通報はすべてログイン必須（匿名 401）。
- 1ユーザーが同一商品に複数の使用記録を投稿できる。星評価は受け付けない(400)。
- review_id は同じ商品・同じ投稿者の口コミのみ許可（他人/別商品は 400）。
- 削除は本人のみ（他人/不存在は 404）・論理削除。通報は自分不可・二重不可。
- 使用記録は平均評価・ランキング・review_count に一切影響しない。
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.products.models import Product
from apps.reviews.models import ProductUseLog, ProductUseLogReport, Review


def _user(email):
    return get_user_model().objects.create(
        email=email, username=email.split("@")[0], nickname=email.split("@")[0],
    )


def _product(slug):
    return Product.objects.create(name=f"商品{slug}", slug=slug, is_published=True)


class UseLogApiTests(APITestCase):
    def setUp(self):
        self.alice = _user("alice@example.com")
        self.bob = _user("bob@example.com")
        self.p1 = _product("p1")
        self.p2 = _product("p2")
        self.list_url = f"/api/products/{self.p1.id}/use-logs/"

    # ---- 権限（ログイン必須） ----
    def test_list_requires_login(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 401)

    def test_create_requires_login(self):
        self.assertEqual(
            self.client.post(self.list_url, {"body": "x"}).status_code, 401
        )

    def test_report_requires_login(self):
        log = ProductUseLog.objects.create(
            product=self.p1, user=self.bob, body="b"
        )
        self.assertEqual(
            self.client.post(f"/api/use-logs/{log.id}/report/",
                             {"reason": "other"}).status_code,
            401,
        )

    # ---- 投稿 ----
    def test_multiple_logs_same_product(self):
        self.client.force_authenticate(self.alice)
        for i in range(3):
            r = self.client.post(self.list_url, {"body": f"day{i}"})
            self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            ProductUseLog.objects.filter(product=self.p1, user=self.alice).count(), 3
        )

    def test_empty_body_rejected(self):
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.post(self.list_url, {"body": ""}).status_code, 400)
        self.assertEqual(self.client.post(self.list_url, {}).status_code, 400)

    def test_rating_rejected(self):
        self.client.force_authenticate(self.alice)
        r = self.client.post(self.list_url, {"body": "x", "rating": 5})
        self.assertEqual(r.status_code, 400)

    def test_review_link_same_user_same_product_ok(self):
        rv = Review.objects.create(
            product=self.p1, user=self.alice, rating=5, title="t", body="b", is_approved=True,
        )
        self.client.force_authenticate(self.alice)
        r = self.client.post(self.list_url, {"body": "x", "review_id": rv.id})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["review_id"], rv.id)

    def test_review_link_other_user_rejected(self):
        rv = Review.objects.create(
            product=self.p1, user=self.bob, rating=5, title="t", body="b", is_approved=True,
        )
        self.client.force_authenticate(self.alice)
        r = self.client.post(self.list_url, {"body": "x", "review_id": rv.id})
        self.assertEqual(r.status_code, 400)

    def test_review_link_other_product_rejected(self):
        rv = Review.objects.create(
            product=self.p2, user=self.alice, rating=5, title="t", body="b", is_approved=True,
        )
        self.client.force_authenticate(self.alice)
        r = self.client.post(self.list_url, {"body": "x", "review_id": rv.id})
        self.assertEqual(r.status_code, 400)

    # ---- 一覧 ----
    def test_list_returns_logs_newest_first(self):
        # 承認制: 他人の投稿は承認済みのみ見えるため、ここでは承認済みで作る。
        ProductUseLog.objects.create(
            product=self.p1, user=self.bob, body="old", is_approved=True,
        )
        ProductUseLog.objects.create(
            product=self.p1, user=self.alice, body="new", is_approved=True,
        )
        self.client.force_authenticate(self.alice)
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 200)
        bodies = [row["body"] for row in r.data["results"]]
        self.assertEqual(bodies, ["new", "old"])
        # can_delete / can_report の出し分け
        rows = {row["body"]: row for row in r.data["results"]}
        self.assertTrue(rows["new"]["can_delete"])      # 自分のもの
        self.assertFalse(rows["new"]["can_report"])
        self.assertFalse(rows["old"]["can_delete"])     # 他人のもの
        self.assertTrue(rows["old"]["can_report"])

    def test_list_hides_unapproved_of_others_but_shows_own(self):
        # 承認制: 他人の承認待ちは返さない。自分の承認待ちは is_approved=false で返す
        # （アプリ側が「承認待ち」バッジを表示する）。
        ProductUseLog.objects.create(
            product=self.p1, user=self.bob, body="bob-pending",
        )
        ProductUseLog.objects.create(
            product=self.p1, user=self.alice, body="mine-pending",
        )
        self.client.force_authenticate(self.alice)
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 200)
        bodies = [row["body"] for row in r.data["results"]]
        self.assertEqual(bodies, ["mine-pending"])
        self.assertFalse(r.data["results"][0]["is_approved"])

    # ---- 削除（本人のみ・論理削除） ----
    def test_delete_own_soft_deletes(self):
        log = ProductUseLog.objects.create(product=self.p1, user=self.alice, body="b")
        self.client.force_authenticate(self.alice)
        r = self.client.delete(f"/api/use-logs/{log.id}/")
        self.assertEqual(r.status_code, 204)
        log.refresh_from_db()
        self.assertTrue(log.is_deleted)
        self.assertEqual(ProductUseLog.objects.count(), 0)        # 既定マネージャから消える
        self.assertEqual(ProductUseLog.all_objects.count(), 1)    # 行は残る

    def test_delete_others_404(self):
        log = ProductUseLog.objects.create(product=self.p1, user=self.bob, body="b")
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.delete(f"/api/use-logs/{log.id}/").status_code, 404)

    # ---- 通報 ----
    def test_report_other_then_double(self):
        log = ProductUseLog.objects.create(product=self.p1, user=self.bob, body="b")
        self.client.force_authenticate(self.alice)
        r = self.client.post(f"/api/use-logs/{log.id}/report/", {"reason": "other"})
        self.assertEqual(r.status_code, 201, r.content)
        r2 = self.client.post(f"/api/use-logs/{log.id}/report/", {"reason": "other"})
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(ProductUseLogReport.objects.count(), 1)

    def test_report_own_rejected(self):
        log = ProductUseLog.objects.create(product=self.p1, user=self.alice, body="b")
        self.client.force_authenticate(self.alice)
        r = self.client.post(f"/api/use-logs/{log.id}/report/", {"reason": "other"})
        self.assertEqual(r.status_code, 400)

    # ---- 既存集計への非影響 ----
    def test_use_log_does_not_affect_rating_or_review_count(self):
        Review.objects.create(
            product=self.p1, user=self.alice, rating=5, title="t", body="b", is_approved=True,
        )
        ProductUseLog.objects.create(product=self.p1, user=self.alice, body="x")
        ProductUseLog.objects.create(product=self.p1, user=self.alice, body="y")
        stats = self.p1.review_stats()
        self.assertEqual(stats["average"], 5)
        self.assertEqual(stats["count"], 1)   # 使用記録2件は混ざらない
        u = get_user_model().objects.get(pk=self.alice.pk)
        self.assertEqual(u.review_count, 1)    # 使用記録は review_count に入らない
