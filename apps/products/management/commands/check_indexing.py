"""
Google URL Inspection API で各記事のインデックス状況を取得し、
Article.index_status / index_checked_at / index_raw_status に保存するコマンド。

認証:
    ADC（Application Default Credentials）を使用。notify_google と同一の
    webmasters スコープ（consent 済み）。URL Inspection は読み取り操作で、
    このスコープに含まれる。

エンドポイント:
    searchconsole v1 urlInspection.index.inspect
    siteUrl は GSC 登録プロパティ（notify_google と同じ URL プレフィックス）。

使い方:
    python manage.py check_indexing                 # is_published=True 全件
    python manage.py check_indexing --slug=ballpen   # 個別指定
    python manage.py check_indexing --slug=ballpen --slug=peppermill  # 複数可
    python manage.py check_indexing --all            # 非公開含む全件

レート対策:
    1リクエスト/秒のスロットル＋429（および503）時の指数バックオフ。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.products.models import Article


SITE_URL = "https://sc-tsusho.jp/"          # GSC 登録プロパティ（notify_google と同一）
PUBLIC_URL_FMT = "https://sc-tsusho.jp/{slug}/"
# URL Inspection は read 操作。notify_google と同じ consent 済みスコープを使う。
SCOPES = ["https://www.googleapis.com/auth/webmasters"]
LOG_PATH = "/opt/claude-ops/logs/check_indexing.log"
JST = ZoneInfo("Asia/Tokyo")

THROTTLE_SEC = 1.0          # 1リクエスト/秒
MAX_RETRIES = 5            # 429/503 時のリトライ上限
BACKOFF_BASE = 2.0         # 指数バックオフの基数（2,4,8,16,32秒）


def map_coverage_state(coverage: str) -> str:
    """coverageState を index_status の選択肢にマッピングする。

    注意1: "Crawled - currently not indexed" などは文字列中に "indexed" を
    含むため、generic な "indexed" 判定より先に Crawled/Discovered/Excluded を
    判定する（誤って indexed に分類しないため）。
    注意2: 新規URLの "Not found (404)" / "URL is unknown to Google" /
    "URL is not on Google" は、APIエラーではなく「Google未登録/未クロール」状態。
    純粋なAPIエラー（認証失敗・5xx等）は _inspect 側で "error" を返すため、
    ここでの "error" は想定外の未知 coverageState のみのフォールバック。
    """
    if not coverage:
        return "error"
    cl = coverage.lower()
    if "crawled" in cl:
        return "crawled_not_indexed"
    if "discovered" in cl:
        return "discovered_not_indexed"
    if "excluded" in cl:
        return "excluded"
    if ("not found" in cl) or ("unknown" in cl) or ("not on google" in cl):
        return "unknown_to_google"
    if "indexed" in cl:
        return "indexed"
    return "error"


class Command(BaseCommand):
    help = "URL Inspection API で記事のGoogleインデックス状況を取得・保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--slug", action="append", default=None,
            help="対象記事のslug（複数指定可）。未指定なら公開記事を全件。",
        )
        parser.add_argument(
            "--all", action="store_true",
            help="is_published に関わらず全記事を対象にする。",
        )

    # -------------------------------------------------------------------------
    def handle(self, *args, **opts) -> None:
        slugs = opts.get("slug")
        do_all = opts.get("all")

        if slugs:
            qs = Article.objects.filter(slug__in=slugs)
            found = set(qs.values_list("slug", flat=True))
            for s in slugs:
                if s not in found:
                    self.stdout.write(self.style.WARNING(f"⚠ slug 未存在: {s}"))
        elif do_all:
            qs = Article.objects.all()
        else:
            qs = Article.objects.filter(is_published=True)
        qs = qs.order_by("slug")

        total = qs.count()
        if not total:
            self.stdout.write("対象記事がありません。")
            return

        self.stdout.write(self.style.SUCCESS(f"=== インデックス状況チェック: {total}件 ==="))
        self.stdout.write(f"プロパティ: {SITE_URL}")

        # --- 認証 & API初期化 -------------------------------------------------
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            service = build("searchconsole", "v1", credentials=creds)
        except Exception as e:  # noqa: BLE001
            self._log(f"FAILED auth: {type(e).__name__}: {e}")
            raise CommandError(
                "認証またはAPI初期化に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  確認: ADC に webmasters スコープが付与されているか。"
            )

        counts: dict[str, int] = {}
        n_error = 0
        n_checked = 0

        for art in qs:
            url = PUBLIC_URL_FMT.format(slug=art.slug)
            status, raw = self._inspect(service, url)

            art.index_status = status
            art.index_checked_at = timezone.now()
            art.index_raw_status = raw
            art.save(update_fields=["index_status", "index_checked_at", "index_raw_status"])

            counts[status] = counts.get(status, 0) + 1
            n_checked += 1
            if status == "error":
                n_error += 1
            self.stdout.write(f"  [{status:>22}] {art.slug}  ({raw[:60]})")

            time.sleep(THROTTLE_SEC)  # 1req/sec スロットル

        # --- サマリ -----------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n=== 完了サマリ ==="))
        self.stdout.write(f"チェック数 : {n_checked}")
        label = dict(Article.INDEX_STATUS_CHOICES)
        for key, _lbl in Article.INDEX_STATUS_CHOICES:
            if key and counts.get(key):
                self.stdout.write(f"  {label.get(key, key)} : {counts[key]}件")
        self.stdout.write(f"エラー件数 : {n_error}")
        self._log(
            f"DONE checked={n_checked} "
            + " ".join(f"{k}={v}" for k, v in counts.items())
            + f" errors={n_error}"
        )

    # -------------------------------------------------------------------------
    # 1URLを URL Inspection API で検査。(status, raw_coverage_or_error) を返す。
    # 429/503 は指数バックオフでリトライ。
    # -------------------------------------------------------------------------
    def _inspect(self, service, url: str) -> tuple[str, str]:
        body = {"inspectionUrl": url, "siteUrl": SITE_URL}
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = service.urlInspection().index().inspect(body=body).execute()
                coverage = (
                    resp.get("inspectionResult", {})
                    .get("indexStatusResult", {})
                    .get("coverageState", "")
                )
                return map_coverage_state(coverage), (coverage or "(coverageState なし)")
            except HttpError as e:  # noqa: PERF203
                code = getattr(e.resp, "status", None)
                if code in (429, 503) and attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    self.stdout.write(
                        self.style.WARNING(
                            f"    {code} レート制限 → {wait:.0f}秒待機して再試行 "
                            f"({attempt + 1}/{MAX_RETRIES})"
                        )
                    )
                    time.sleep(wait)
                    continue
                detail = f"HttpError {code}: {str(e)[:160]}"
                self._log(f"ERROR {url}: {detail}")
                return "error", detail
            except Exception as e:  # noqa: BLE001
                detail = f"{type(e).__name__}: {str(e)[:160]}"
                self._log(f"ERROR {url}: {detail}")
                return "error", detail
        return "error", "リトライ上限到達"

    # -------------------------------------------------------------------------
    def _log(self, message: str) -> None:
        ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        try:
            Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except OSError:
            pass
