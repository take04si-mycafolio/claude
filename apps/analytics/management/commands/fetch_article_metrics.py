"""
記事パフォーマンス・ダッシュボードの元データ取得コマンド

GSC（Search Console / WMT）と GA4（アクセス解析）から、ページ別の指標と
「ページごとの流入キーワード一覧」を取得し、ArticleMetricSnapshot /
ArticleMetric として DB に保存する。管理画面のダッシュボードはこの最新
スナップショットを読むだけ（Google API 認証は本コマンド側＝root/cron で完結）。

取得内容:
    - GSC ページ別        : 表示回数 / クリック / CTR / 平均順位
    - GSC ページ×クエリ    : 各ページの流入キーワード一覧
    - GA4 ページ別        : セッション / PV / ユーザー / 直帰率 / 平均滞在

認証:
    ADC（Application Default Credentials）。cron では
    GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json

使い方:
    python manage.py fetch_article_metrics                       # 直近28日
    python manage.py fetch_article_metrics --days=7
    python manage.py fetch_article_metrics --end-date=2026-06-26
    python manage.py fetch_article_metrics --keep=12             # 古いスナップショット保持数
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import google.auth
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.management.commands import fetch_gsc, fetch_ga
from apps.products.models import Article, Product
from apps.analytics.models import ArticleMetricSnapshot, ArticleMetric

SITE_URL = fetch_gsc.SITE_URL  # "https://sc-tsusho.jp/"
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
GA_PAGE_METRICS = [
    "sessions", "screenPageViews", "activeUsers",
    "averageSessionDuration", "bounceRate",
]


def normalize_path(url_or_path: str) -> str:
    """GSC のフル URL / GA4 のパスを '/slug/' 形式のパスに正規化する。"""
    if not url_or_path:
        return ""
    p = url_or_path
    if p.startswith("http"):
        # ドメイン以降を取り出す
        p = "/" + p.split("/", 3)[-1] if p.count("/") >= 3 else "/"
    p = p.split("?")[0].split("#")[0]
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p += "/"
    return p


class Command(BaseCommand):
    help = "GSC/GA4 から記事パフォーマンス指標を取得し DB に保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--days", type=int, default=28, help="取得日数（デフォルト28）")
        parser.add_argument("--end-date", type=str, default=None,
                            help="終了日 YYYY-MM-DD（デフォルト: 今日-3日）")
        parser.add_argument("--keep", type=int, default=12,
                            help="保持するスナップショット数（古いものを削除）")

    def handle(self, *args, **opts) -> None:
        days = opts["days"]
        if opts["end_date"]:
            try:
                end = datetime.strptime(opts["end_date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"--end-date の形式が不正: {opts['end_date']!r}")
        else:
            end = date.today() - timedelta(days=fetch_gsc.GSC_DATA_DELAY_DAYS)
        start = end - timedelta(days=days - 1)

        self.stdout.write(self.style.SUCCESS("=== 記事パフォーマンス取得 ==="))
        self.stdout.write(f"期間: {start} 〜 {end}（{days}日）")

        # --- 認証 ---
        try:
            gsc_creds, _ = google.auth.default(scopes=GSC_SCOPES)
            gsc = build("searchconsole", "v1", credentials=gsc_creds)
            ga_creds, _ = google.auth.default(scopes=GA_SCOPES)
            ga_client = BetaAnalyticsDataClient(credentials=ga_creds)
            self.stdout.write("認証: ADCロード成功（GSC/GA4）")
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"認証/初期化に失敗: {type(e).__name__}: {e}")

        gsc_cmd = fetch_gsc.Command()
        ga_cmd = fetch_ga.Command()

        # --- 取得 ---
        try:
            self.stdout.write("取得: GSC 全体指標 ...")
            totals = gsc_cmd.fetch_overall(gsc, start, end)
            self.stdout.write("取得: GSC ページ別 ...")
            gsc_pages = gsc_cmd.fetch_by_dimension(gsc, start, end, "page", 1000)
            self.stdout.write("取得: GSC ページ×クエリ（流入キーワード）...")
            page_queries = self._fetch_page_queries(gsc, start, end)
            self.stdout.write("取得: GA4 全体指標 ...")
            ga_totals = ga_cmd.fetch_overall(ga_client, start, end)
            self.stdout.write("取得: GA4 ページ別 ...")
            ga_pages = ga_cmd.fetch_by_dimension(
                ga_client, start, end, ["pagePath"], GA_PAGE_METRICS, 1000)
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"API取得に失敗: {type(e).__name__}: {e}")

        # --- パス→行 のマージ ---
        rows: dict[str, dict] = {}

        for p in gsc_pages:
            path = normalize_path(p.get("url", ""))
            r = rows.setdefault(path, self._blank(path))
            r.update(impressions=p["impressions"], clicks=p["clicks"],
                     ctr=p["ctr"], position=p["position"])

        for path, kws in page_queries.items():
            r = rows.setdefault(path, self._blank(path))
            # キーワードは表示回数の多い順
            r["keywords"] = sorted(kws, key=lambda x: x["impressions"], reverse=True)

        for g in ga_pages:
            path = normalize_path(g.get("path", ""))
            r = rows.setdefault(path, self._blank(path))
            r.update(sessions=g.get("sessions", 0), page_views=g.get("page_views", 0),
                     active_users=g.get("active_users", 0),
                     bounce_rate=g.get("bounce_rate", 0.0),
                     avg_duration_sec=g.get("avg_duration_sec", 0.0))

        # --- 記事/商品の紐付け ---
        articles = {f"/{a.slug}/": a for a in Article.objects.all()}
        product_paths = {normalize_path(p.get_absolute_url()): p
                         for p in Product.objects.all()}
        self._annotate(rows, articles, product_paths)

        # --- DB 保存 ---
        with transaction.atomic():
            snap = ArticleMetricSnapshot.objects.create(
                period_start=start, period_end=end,
                total_clicks=totals["clicks"], total_impressions=totals["impressions"],
                avg_ctr=totals["ctr"], avg_position=totals["position"],
                total_sessions=ga_totals["sessions"],
                total_page_views=ga_totals["page_views"],
                avg_bounce_rate=ga_totals["bounce_rate"],
            )
            ArticleMetric.objects.bulk_create([
                ArticleMetric(
                    snapshot=snap, path=r["path"], title=r["title"],
                    content_type=r["content_type"], article=r["article"],
                    impressions=r["impressions"], clicks=r["clicks"],
                    ctr=r["ctr"], position=r["position"],
                    sessions=r["sessions"], page_views=r["page_views"],
                    active_users=r["active_users"], bounce_rate=r["bounce_rate"],
                    avg_duration_sec=r["avg_duration_sec"], keywords=r["keywords"],
                )
                for r in rows.values()
            ])

        # --- 古いスナップショット掃除 ---
        keep = opts["keep"]
        old_ids = list(ArticleMetricSnapshot.objects.order_by("-fetched_at")
                       .values_list("id", flat=True)[keep:])
        if old_ids:
            ArticleMetricSnapshot.objects.filter(id__in=old_ids).delete()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ 保存完了: snapshot id={snap.id} / {len(rows)}ページ"))
        n_art = sum(1 for r in rows.values() if r["content_type"] == "article")
        self.stdout.write(f"記事: {n_art}件 / 全体表示回数 {totals['impressions']} / "
                          f"セッション {ga_totals['sessions']}")
        self.stdout.write("管理画面: https://sc-tsusho.jp/admin/seo/article-performance/")

    # ------------------------------------------------------------------
    def _fetch_page_queries(self, service, start: date, end: date) -> dict[str, list]:
        """dimensions=[page, query] でページ別の流入キーワードを取得しグルーピング。"""
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["page", "query"],
            "rowLimit": 5000,
        }
        resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        out: dict[str, list] = {}
        for row in resp.get("rows", []):
            keys = row.get("keys", [])
            if len(keys) < 2:
                continue
            path = normalize_path(keys[0])
            out.setdefault(path, []).append({
                "query": keys[1],
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0.0) * 100, 2),
                "position": round(row.get("position", 0.0), 2),
            })
        return out

    @staticmethod
    def _blank(path: str) -> dict:
        return {
            "path": path, "title": "", "content_type": "other", "article": None,
            "impressions": 0, "clicks": 0, "ctr": 0.0, "position": 0.0,
            "sessions": 0, "page_views": 0, "active_users": 0,
            "bounce_rate": 0.0, "avg_duration_sec": 0.0, "keywords": [],
        }

    @staticmethod
    def _annotate(rows, articles, product_paths) -> None:
        for path, r in rows.items():
            if path in articles:
                a = articles[path]
                r["content_type"] = "article"
                r["title"] = a.title
                r["article"] = a
            elif path in product_paths:
                p = product_paths[path]
                r["content_type"] = "product"
                r["title"] = p.name
            elif path == "/":
                r["content_type"] = "page"
                r["title"] = "TOPページ"
            else:
                r["content_type"] = "other"
                if not r["title"]:
                    r["title"] = path
