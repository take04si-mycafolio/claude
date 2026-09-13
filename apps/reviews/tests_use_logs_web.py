"""使用記録の PC版Web（商品詳細ページ）UI/投稿/削除/通報の動作確認テスト。

- 商品詳細ページに使用記録セクション・一覧・投稿フォームが出るか（ログイン/未ログイン）。
- 投稿/削除/通報の各 POST が既存口コミと同じ作法で動くか。
- 星評価フォームが無いこと・既存集計に影響しないこと。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Category, Product
from apps.reviews.models import (
    ProductUseLog, ProductUseLogReport, Review,
)


def _user(email, pw="pw12345!"):
    u = get_user_model().objects.create(
        email=email, username=email.split("@")[0], nickname=email.split("@")[0],
    )
    u.set_password(pw)
    u.save()
    return u


def _product(slug):
    cat = Category.objects.get_or_create(slug="cat", defaults={"name": "カテゴリ"})[0]
    return Product.objects.create(
        name=f"商品{slug}", slug=slug, is_published=True, product_type=cat,
    )


class UseLogWebTests(TestCase):
    def setUp(self):
        self.alice = _user("alice@e.com")
        self.bob = _user("bob@e.com")
        self.p = _product("p1")
        self.detail_url = self.p.get_absolute_url()
        self.create_url = reverse("reviews:use_log_create", args=[self.p.slug])

    # ---- 表示 ----
    def test_detail_renders_section_and_form_for_logged_in(self):
        self.client.force_login(self.alice)
        r = self.client.get(self.detail_url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("使用記録", html)
        self.assertIn(self.create_url, html)          # 投稿フォームの action
        self.assertIn('name="body"', html)
        # 星評価フォームが無い（使用記録フォーム領域に rating/star ラジオを出さない）
        self.assertNotIn('name="rating"', html)

    def test_detail_hides_form_for_anonymous(self):
        r = self.client.get(self.detail_url)
        self.assertEqual(r.status_code, 200)          # 未ログインでも商品詳細は閲覧可
        html = r.content.decode()
        self.assertIn("使用記録", html)               # セクション見出しは出る
        self.assertNotIn(self.create_url, html)        # 投稿フォームは出さない
        self.assertIn("ログイン", html)

    def test_detail_lists_use_logs(self):
        # 承認制: 他人の投稿は承認後に見える。
        ProductUseLog.objects.create(
            product=self.p, user=self.bob, body="昨日使った感想です",
            is_approved=True,
        )
        self.client.force_login(self.alice)            # 別ユーザーでも一覧は見える
        html = self.client.get(self.detail_url).content.decode()
        self.assertIn("昨日使った感想です", html)

    def test_detail_hides_unapproved_log_of_others_but_shows_own(self):
        # 他人の承認待ちは見えない。自分の承認待ちは「承認待ち」バッジ付きで見える。
        ProductUseLog.objects.create(
            product=self.p, user=self.bob, body="他人の承認待ち記録",
        )
        mine = ProductUseLog.objects.create(
            product=self.p, user=self.alice, body="自分の承認待ち記録",
        )
        self.client.force_login(self.alice)
        html = self.client.get(self.detail_url).content.decode()
        self.assertNotIn("他人の承認待ち記録", html)
        self.assertIn("自分の承認待ち記録", html)
        self.assertIn("承認待ち", html)
        # 承認されるとバッジが消えて全員に見える
        mine.is_approved = True
        mine.save(update_fields=["is_approved"])
        self.client.force_login(self.bob)
        html = self.client.get(self.detail_url).content.decode()
        self.assertIn("自分の承認待ち記録", html)

    # ---- 投稿 ----
    def test_post_create_text_only(self):
        self.client.force_login(self.alice)
        r = self.client.post(self.create_url, {"body": "1週間使いました", "next": self.detail_url})
        self.assertEqual(r.status_code, 302)
        log = ProductUseLog.objects.get(product=self.p, user=self.alice)
        self.assertEqual(log.body, "1週間使いました")
        self.assertEqual(log.images.count(), 0)
        # 複数投稿OK
        self.client.post(self.create_url, {"body": "2週間目"})
        self.assertEqual(ProductUseLog.objects.filter(product=self.p, user=self.alice).count(), 2)

    def test_post_with_title(self):
        self.client.force_login(self.alice)
        self.client.post(self.create_url, {"title": "2週間使ってみて", "body": "良い感じ"})
        log = ProductUseLog.objects.get(product=self.p, user=self.alice)
        self.assertEqual(log.title, "2週間使ってみて")
        # 一覧カードにタイトルが出る
        html = self.client.get(self.detail_url).content.decode()
        self.assertIn("2週間使ってみて", html)

    def test_post_without_title_ok(self):
        self.client.force_login(self.alice)
        self.client.post(self.create_url, {"body": "タイトル無しでも投稿できる"})
        log = ProductUseLog.objects.get(product=self.p, user=self.alice)
        self.assertEqual(log.title, "")

    def test_post_empty_body_errors(self):
        self.client.force_login(self.alice)
        r = self.client.post(self.create_url, {"body": "   ", "next": self.detail_url}, follow=True)
        self.assertEqual(ProductUseLog.objects.count(), 0)
        msgs = [m.message for m in r.context["messages"]]
        self.assertTrue(any("使用記録を投稿しました" not in m for m in msgs))

    def test_post_requires_login(self):
        r = self.client.post(self.create_url, {"body": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(ProductUseLog.objects.count(), 0)

    def test_create_links_own_review_when_present(self):
        rv = Review.objects.create(product=self.p, user=self.alice, rating=5, title="t", body="b", is_approved=True)
        self.client.force_login(self.alice)
        self.client.post(self.create_url, {"body": "経過", "review_id": rv.id})
        log = ProductUseLog.objects.get(product=self.p, user=self.alice)
        self.assertEqual(log.review_id, rv.id)

    # ---- 削除 ----
    def test_delete_own_soft_deletes(self):
        log = ProductUseLog.objects.create(product=self.p, user=self.alice, body="x")
        self.client.force_login(self.alice)
        r = self.client.post(reverse("reviews:use_log_delete", args=[log.id]))
        self.assertEqual(r.status_code, 302)
        log.refresh_from_db()
        self.assertTrue(log.is_deleted)
        self.assertEqual(ProductUseLog.objects.count(), 0)
        self.assertEqual(ProductUseLog.all_objects.count(), 1)

    def test_delete_others_404(self):
        log = ProductUseLog.objects.create(product=self.p, user=self.bob, body="x")
        self.client.force_login(self.alice)
        r = self.client.post(reverse("reviews:use_log_delete", args=[log.id]))
        self.assertEqual(r.status_code, 404)
        log.refresh_from_db()
        self.assertFalse(log.is_deleted)

    # ---- 通報 ----
    def test_report_other_then_double(self):
        log = ProductUseLog.objects.create(product=self.p, user=self.bob, body="x")
        self.client.force_login(self.alice)
        url = reverse("reviews:use_log_report", args=[log.id])
        r = self.client.post(url, {"reason": "other", "next": self.detail_url})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ProductUseLogReport.objects.filter(use_log=log).count(), 1)
        self.client.post(url, {"reason": "other"})       # 二重通報は増えない
        self.assertEqual(ProductUseLogReport.objects.filter(use_log=log).count(), 1)

    def test_report_own_blocked(self):
        log = ProductUseLog.objects.create(product=self.p, user=self.alice, body="x")
        self.client.force_login(self.alice)
        r = self.client.post(reverse("reviews:use_log_report", args=[log.id]), {"reason": "other"})
        self.assertEqual(ProductUseLogReport.objects.count(), 0)

    # ---- 既存集計への非影響 ----
    def test_use_logs_do_not_affect_aggregates(self):
        Review.objects.create(product=self.p, user=self.alice, rating=4, title="t", body="b", is_approved=True)
        base = self.p.review_stats()
        for i in range(3):
            ProductUseLog.objects.create(product=self.p, user=self.alice, body=f"log{i}")
        self.assertEqual(self.p.review_stats(), base)    # 平均・件数 不変
        u = get_user_model().objects.get(pk=self.alice.pk)
        self.assertEqual(u.review_count, 1)              # review_count に混ざらない
