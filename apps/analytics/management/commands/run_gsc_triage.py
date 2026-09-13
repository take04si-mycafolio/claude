"""
GSC記事トリアージ・コマンド

全ページを Search Console データで4バケットに自動仕分けし、TriageRun /
ArticleTriage として DB に保存する。判定は「ページ平均順位」ではなく
「表示フロア以上のクエリの中での最小position（＝最上位クエリの順位）」で行う。

バケット:
    quick_win  : best_position 8〜20位（あと一歩・最優先）
    needs_work : best_position 20位超だが表示あり（検索意図のズレ）
    performing : best_position 1〜7位（すでに上位・維持/CTR最適化）
    dead       : 表示合計 < しきい値、または サイトマップにあるのにGSC不在

認証:
    既存の fetch_gsc と同じ ADC（Application Default Credentials）を再利用。
    cron/root で実行（鍵: /root/.config/gcloud/application_default_credentials.json）。

使い方:
    python manage.py run_gsc_triage                      # 直近28日（末尾3日除外）
    python manage.py run_gsc_triage --start=2026-06-01 --end=2026-06-26
    python manage.py run_gsc_triage --sitemap=https://sc-tsusho.jp/sitemap.xml
    python manage.py run_gsc_triage --sitemap=""         # サイトマップ照合をスキップ
    python manage.py run_gsc_triage --keep=12            # 古い実行を保持数で掃除
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.request import urlopen, Request

import google.auth
from googleapiclient.discovery import build

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.management.commands import fetch_gsc
from apps.analytics.management.commands.fetch_article_metrics import normalize_path
from apps.products.models import Article, Product
from apps.analytics.models import TriageRun, ArticleTriage

SITE_URL = fetch_gsc.SITE_URL  # "https://sc-tsusho.jp/"
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# --- 調整可能な定数（settings で上書き可能） ---------------------------------
DEAD_IMPRESSION_THRESHOLD = getattr(settings, "GSC_TRIAGE_DEAD_IMPRESSION_THRESHOLD", 10)
QUERY_IMPR_FLOOR = getattr(settings, "GSC_TRIAGE_QUERY_IMPR_FLOOR", 3)
DEFAULT_SITEMAP_URL = getattr(settings, "GSC_TRIAGE_SITEMAP_URL", "https://sc-tsusho.jp/sitemap.xml")

# 観察ステータスの閾値（period_end からの経過日数）
OBSERVING_DAYS = getattr(settings, "GSC_TRIAGE_OBSERVING_DAYS", 14)   # これ未満=様子見
EVALUABLE_DAYS = getattr(settings, "GSC_TRIAGE_EVALUABLE_DAYS", 56)   # これ未満=評価中

PAGE_ROW_LIMIT = 25000      # page 次元（実サイトは数百ページなので1リクエストで十分）
PAGE_QUERY_ROW_LIMIT = 25000  # page×query 次元（startRow でページネーション）


class Command(BaseCommand):
    help = "GSC データで全ページを4バケットに仕分けし TriageRun/ArticleTriage を保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--start", type=str, default=None,
                            help="開始日 YYYY-MM-DD（省略時: 終了日-27日）")
        parser.add_argument("--end", type=str, default=None,
                            help="終了日 YYYY-MM-DD（省略時: 今日-3日）")
        parser.add_argument("--sitemap", type=str, default=None,
                            help='サイトマップURL（省略時: 定数。"" で照合スキップ）')
        parser.add_argument("--keep", type=int, default=None,
                            help="保持する実行数（指定時のみ古い実行を削除）")

    # ------------------------------------------------------------------
    def handle(self, *args, **opts) -> None:
        # --- 期間の決定（末尾3日除外がデフォルト） ---
        if opts["end"]:
            end = self._parse_date(opts["end"], "--end")
        else:
            end = date.today() - timedelta(days=fetch_gsc.GSC_DATA_DELAY_DAYS)
        if opts["start"]:
            start = self._parse_date(opts["start"], "--start")
        else:
            start = end - timedelta(days=27)  # 直近28日
        if start > end:
            raise CommandError(f"開始日 {start} が終了日 {end} より後です。")

        sitemap_url = opts["sitemap"] if opts["sitemap"] is not None else DEFAULT_SITEMAP_URL

        self.stdout.write(self.style.SUCCESS("=== GSC記事トリアージ ==="))
        self.stdout.write(f"サイト   : {SITE_URL}")
        self.stdout.write(f"期間     : {start} 〜 {end}（{(end - start).days + 1}日）")
        self.stdout.write(f"しきい値 : dead<{DEAD_IMPRESSION_THRESHOLD}imp / クエリ表示フロア{QUERY_IMPR_FLOOR}")
        self.stdout.write(f"サイトマップ: {sitemap_url or '(照合スキップ)'}")

        # --- 認証 ---
        try:
            creds, _ = google.auth.default(scopes=GSC_SCOPES)
            service = build("searchconsole", "v1", credentials=creds)
            self.stdout.write("認証     : ADCロード成功")
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "認証またはAPI初期化に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  確認: ADC（application_default_credentials.json）と "
                "webmasters.readonly スコープ。"
            )

        gsc_cmd = fetch_gsc.Command()

        # --- GSC データ取得 ---
        try:
            self.stdout.write("取得     : ページ別合計（表示の正）...")
            gsc_pages = gsc_cmd.fetch_by_dimension(service, start, end, "page", PAGE_ROW_LIMIT)
            self.stdout.write(f"           {len(gsc_pages)}ページ")
            self.stdout.write("取得     : ページ×クエリ明細（ページネーション）...")
            page_queries = self._fetch_page_queries(service, start, end)
            self.stdout.write(f"           {len(page_queries)}ページ分のクエリ明細")
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "Search Console API 呼び出しに失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                f"  対象 {SITE_URL} の権限・SITE_URL形式（URLプレフィックス/sc-domain）・"
                "期間指定を確認してください。"
            )

        # --- サイトマップ取得（入れ子 sitemapindex 対応） ---
        sitemap_paths: set[str] = set()
        if sitemap_url:
            try:
                sitemap_paths = self._fetch_sitemap_paths(sitemap_url)
                self.stdout.write(f"取得     : サイトマップ {len(sitemap_paths)}URL")
            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.WARNING(
                    f"サイトマップ取得に失敗（照合スキップ）: {type(e).__name__}: {e}"))
                sitemap_url = ""

        # --- ページ単位に集約 ---
        # GSC は #フラグメント付きURLを別行で返すため、同一パスは合算する
        # （表示の「正」＝表示回数は合計、平均順位は表示回数の加重平均）。
        gsc_paths: set[str] = set()
        rows: dict[str, dict] = {}
        page_agg: dict[str, dict] = {}
        for p in gsc_pages:
            path = normalize_path(p.get("url", ""))
            if not path:
                continue
            a = page_agg.setdefault(path, {"impr": 0, "clicks": 0, "posw": 0.0})
            a["impr"] += p["impressions"]
            a["clicks"] += p["clicks"]
            a["posw"] += p["position"] * p["impressions"]
        gsc_paths = set(page_agg)
        for path, a in page_agg.items():
            r = rows.setdefault(path, self._blank(path))
            r["impressions"] = a["impr"]
            r["clicks"] = a["clicks"]
            r["avg_position"] = round(a["posw"] / a["impr"], 2) if a["impr"] else 0.0
            r["ctr"] = round(a["clicks"] / a["impr"] * 100, 2) if a["impr"] else 0.0

        # クエリ明細から best_position 等を計算＋全クエリ portfolio を保存
        for path, kws in page_queries.items():
            r = rows.setdefault(path, self._blank(path))
            r["num_queries"] = len(kws)
            # URL単位・全クエリ考慮のリライト用。position昇順・上位40件を保持。
            r["queries"] = [
                {"query": q["query"], "position": q["position"],
                 "impressions": q["impressions"], "clicks": q["clicks"]}
                for q in sorted(kws, key=lambda q: q["position"])[:40]
            ]
            qualified = [q for q in kws if q["impressions"] >= QUERY_IMPR_FLOOR]
            pool = qualified if qualified else kws
            if pool:
                best = min(pool, key=lambda q: q["position"])
                r["best_query"] = best["query"][:300]
                r["best_query_position"] = best["position"]
                r["best_query_impressions"] = best["impressions"]

        # サイトマップにあるがGSCに出てこないURL（完全0表示の死蔵候補）
        for path in sitemap_paths:
            rows.setdefault(path, self._blank(path))
        for path, r in rows.items():
            r["in_sitemap"] = path in sitemap_paths

        # --- 記事/商品の紐付け＋バケット判定＋観察ステータス ---
        articles = {f"/{a.slug}/": a for a in Article.objects.all()}
        products = {normalize_path(p.get_absolute_url()): p for p in Product.objects.all()}
        for path, r in rows.items():
            art = articles.get(path)
            prod = products.get(path)
            r["article"] = art
            r["is_product"] = prod is not None
            r["bucket"] = self._classify(r, gsc_paths)
            # 更新日スナップショット（観察ステータスの基準）。
            # ※ ArticleTriage.last_updated 列に保存するが、値は last_rewritten_at
            #   （リライト専用日。auto_now の updated_at ではない）。null=リライト日不明→unknown。
            src = art or prod
            r["last_updated"] = getattr(src, "last_rewritten_at", None) if src else None
            self._annotate_observation(r, end)

        # --- 集計 ---
        counts = {"quick_win": 0, "needs_work": 0, "performing": 0, "dead": 0}
        for r in rows.values():
            counts[r["bucket"]] += 1

        # --- DB 保存 ---
        with transaction.atomic():
            run = TriageRun.objects.create(
                period_start=start, period_end=end,
                total_articles=len(rows),
                count_quick_win=counts["quick_win"],
                count_needs_work=counts["needs_work"],
                count_performing=counts["performing"],
                count_dead=counts["dead"],
                sitemap_url=sitemap_url or "",
            )
            ArticleTriage.objects.bulk_create([
                ArticleTriage(
                    run=run, article=r["article"], url=r["path"], bucket=r["bucket"],
                    impressions=r["impressions"], clicks=r["clicks"],
                    ctr=r["ctr"], avg_position=r["avg_position"],
                    best_query=r["best_query"],
                    best_query_position=r["best_query_position"],
                    best_query_impressions=r["best_query_impressions"],
                    num_queries=r["num_queries"], in_sitemap=r["in_sitemap"],
                    queries=r.get("queries", []),
                    last_updated=r["last_updated"],
                    days_since_update=r["days_since_update"],
                    observation_status=r["observation_status"],
                )
                for r in rows.values()
            ])

        # --- 古い実行の掃除（--keep 指定時のみ） ---
        keep = opts["keep"]
        if keep is not None and keep > 0:
            old_ids = list(TriageRun.objects.order_by("-fetched_at")
                           .values_list("id", flat=True)[keep:])
            if old_ids:
                TriageRun.objects.filter(id__in=old_ids).delete()
                self.stdout.write(f"掃除     : 古い実行 {len(old_ids)}件を削除")

        # --- レポート ---
        self._report(run, rows, counts, gsc_paths, sitemap_paths)

    # ------------------------------------------------------------------
    # ページ×クエリ（startRow ページネーションで全件取得）
    # ------------------------------------------------------------------
    def _fetch_page_queries(self, service, start: date, end: date) -> dict[str, list]:
        # (path, query) で合算（#フラグメント違いの同一ページ・同一クエリをまとめる）。
        merged: dict[tuple, dict] = {}
        start_row = 0
        while True:
            body = {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["page", "query"],
                "rowLimit": PAGE_QUERY_ROW_LIMIT,
                "startRow": start_row,
            }
            resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
            batch = resp.get("rows", [])
            for row in batch:
                keys = row.get("keys", [])
                if len(keys) < 2:
                    continue
                path = normalize_path(keys[0])
                key = (path, keys[1])
                m = merged.setdefault(key, {"clicks": 0, "impressions": 0, "posw": 0.0})
                imp = int(row.get("impressions", 0))
                m["clicks"] += int(row.get("clicks", 0))
                m["impressions"] += imp
                m["posw"] += round(row.get("position", 0.0), 2) * imp
            if len(batch) < PAGE_QUERY_ROW_LIMIT:
                break
            start_row += PAGE_QUERY_ROW_LIMIT

        out: dict[str, list] = {}
        for (path, query), m in merged.items():
            imp = m["impressions"]
            out.setdefault(path, []).append({
                "query": query,
                "clicks": m["clicks"],
                "impressions": imp,
                "ctr": round(m["clicks"] / imp * 100, 2) if imp else 0.0,
                "position": round(m["posw"] / imp, 2) if imp else 0.0,
            })
        return out

    # ------------------------------------------------------------------
    # サイトマップ（sitemapindex 入れ子に対応）→ パス集合
    # ------------------------------------------------------------------
    def _fetch_sitemap_paths(self, url: str, _depth: int = 0) -> set[str]:
        if _depth > 5:
            return set()
        req = Request(url, headers={"User-Agent": "gsc-triage/1.0"})
        with urlopen(req, timeout=30) as resp:  # noqa: S310 (信頼できる自サイト)
            xml = resp.read()
        root = ET.fromstring(xml)

        def localname(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        paths: set[str] = set()
        rootname = localname(root.tag)
        if rootname == "sitemapindex":
            for sm in root:
                loc = next((c.text for c in sm if localname(c.tag) == "loc"), None)
                if loc:
                    paths |= self._fetch_sitemap_paths(loc.strip(), _depth + 1)
        else:  # urlset
            for u in root:
                loc = next((c.text for c in u if localname(c.tag) == "loc"), None)
                if loc:
                    paths.add(normalize_path(loc.strip()))
        return paths

    # ------------------------------------------------------------------
    # バケット判定
    # ------------------------------------------------------------------
    def _classify(self, r: dict, gsc_paths: set[str]) -> str:
        # dead: 表示合計がしきい値未満、または サイトマップにありGSC不在
        if r["in_sitemap"] and r["path"] not in gsc_paths:
            return "dead"
        if r["impressions"] < DEAD_IMPRESSION_THRESHOLD:
            return "dead"
        # 最上位クエリ順位（無ければ平均順位で代替）
        pos = r["best_query_position"]
        if pos is None:
            pos = r["avg_position"]
        if pos is None or pos <= 0:
            return "needs_work"
        if pos <= 7:
            return "performing"
        if pos <= 20:
            return "quick_win"
        return "needs_work"

    # ------------------------------------------------------------------
    # 観察ステータス（period_end と last_updated の経過日数で判定）
    # ------------------------------------------------------------------
    @staticmethod
    def _annotate_observation(r: dict, period_end: date) -> None:
        lu = r.get("last_updated")
        if not lu:
            r["days_since_update"] = None
            r["observation_status"] = "unknown"
            return
        days = (period_end - lu.date()).days
        r["days_since_update"] = days
        if days < OBSERVING_DAYS:
            r["observation_status"] = "observing"
        elif days < EVALUABLE_DAYS:
            r["observation_status"] = "evaluable"
        else:
            r["observation_status"] = "settled"

    # ------------------------------------------------------------------
    @staticmethod
    def _blank(path: str) -> dict:
        return {
            "path": path, "article": None, "is_product": False, "bucket": "dead",
            "impressions": 0, "clicks": 0, "ctr": 0.0, "avg_position": 0.0,
            "best_query": "", "best_query_position": None,
            "best_query_impressions": 0, "num_queries": 0, "queries": [], "in_sitemap": False,
            "last_updated": None, "days_since_update": None,
            "observation_status": "unknown",
        }

    @staticmethod
    def _parse_date(s: str, flag: str) -> date:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"{flag} の形式が不正です: {s!r}（YYYY-MM-DD）")

    # ------------------------------------------------------------------
    def _report(self, run, rows, counts, gsc_paths, sitemap_paths) -> None:
        def impr(bucket):
            return sum(r["impressions"] for r in rows.values() if r["bucket"] == bucket)

        labels = {
            "quick_win": "quick_win（あと一歩・最優先）",
            "needs_work": "needs_work（意図のズレ）",
            "performing": "performing（すでに上位）",
            "dead": "dead（統合/削除候補）",
        }
        self.stdout.write(self.style.SUCCESS(f"\n✅ 保存完了: TriageRun id={run.id}"))
        self.stdout.write(f"対象ページ数: {len(rows)}")
        n_article = sum(1 for r in rows.values() if r["article"])
        n_product = sum(1 for r in rows.values() if r["is_product"])
        self.stdout.write(f"  内訳: 記事 {n_article} / 商品 {n_product} / その他 "
                          f"{len(rows) - n_article - n_product}")
        self.stdout.write("\nバケット別（件数 / 表示回数合計）:")
        for b in ("quick_win", "needs_work", "performing", "dead"):
            self.stdout.write(f"  {labels[b]:28} {counts[b]:>5}件  /  表示 {impr(b):>7}")

        sitemap_only = sitemap_paths - gsc_paths
        self.stdout.write("\nサイトマップ照合:")
        self.stdout.write(f"  サイトマップURL数 : {len(sitemap_paths)}")
        self.stdout.write(f"  GSC出現URL数      : {len(gsc_paths)}")
        self.stdout.write(f"  サイトマップにありGSC不在（完全0表示の死蔵）: {len(sitemap_only)}")

        # --- bucket × 観察ステータス（記事のみ）の内訳 ---
        statuses = ("observing", "evaluable", "settled", "unknown")
        self.stdout.write("\n観察ステータス内訳（記事=article FK有 のみ）:")
        self.stdout.write(f"  {'bucket':12} " + "".join(f"{s:>11}" for s in statuses) + f"{'計':>7}")
        for b in ("quick_win", "needs_work", "performing", "dead"):
            cells = {s: 0 for s in statuses}
            for r in rows.values():
                if r["bucket"] == b and r["article"]:
                    cells[r["observation_status"]] += 1
            line = f"  {b:12} " + "".join(f"{cells[s]:>11}" for s in statuses)
            self.stdout.write(line + f"{sum(cells.values()):>7}")
        self.stdout.write(
            f"  ※閾値: observing<{OBSERVING_DAYS}日 / "
            f"evaluable<{EVALUABLE_DAYS}日 / settled≥{EVALUABLE_DAYS}日")
        self.stdout.write("\n管理画面: https://sc-tsusho.jp/admin/analytics/articletriage/")
