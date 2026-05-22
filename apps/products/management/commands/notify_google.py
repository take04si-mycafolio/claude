"""
Google（Search Console）へ sitemap 再送信を行うコマンド

記事の公開・更新後に実行することで、Googleに sitemap の再クロールを促す。
検索結果への反映を早める狙い。

認証:
    ADC（Application Default Credentials）を使用。
    sitemap の submit は書き込み操作のため、スコープは
    https://www.googleapis.com/auth/webmasters （readonlyではない）が必要。

使い方:
    python manage.py notify_google
    python manage.py notify_google --sitemap-url=https://sc-tsusho.jp/sitemap.xml
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import google.auth
from googleapiclient.discovery import build

from django.core.management.base import BaseCommand, CommandError


# =============================================================================
# 設定値
# =============================================================================

SITE_URL = "https://sc-tsusho.jp/"
DEFAULT_SITEMAP_URL = "https://sc-tsusho.jp/sitemap.xml"
LOG_PATH = "/opt/claude-ops/logs/notify_google.log"

# sitemap送信は書き込み操作のため readonly では不可
SCOPES = ["https://www.googleapis.com/auth/webmasters"]
JST = ZoneInfo("Asia/Tokyo")


class Command(BaseCommand):
    help = "Search Console に sitemap を再送信してGoogleの再クロールを促す"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--sitemap-url", type=str, default=DEFAULT_SITEMAP_URL,
            help=f"再送信するsitemapのURL（デフォルト: {DEFAULT_SITEMAP_URL}）",
        )

    def handle(self, *args, **opts) -> None:
        sitemap_url: str = opts["sitemap_url"]

        self.stdout.write(self.style.SUCCESS("=== Google sitemap 再送信 ==="))
        self.stdout.write(f"サイト  : {SITE_URL}")
        self.stdout.write(f"sitemap : {sitemap_url}")

        # --- 認証 & API初期化 -------------------------------------------------
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            service = build("searchconsole", "v1", credentials=creds)
        except Exception as e:  # noqa: BLE001
            msg = (
                "認証またはAPI初期化に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  確認: webmasters（書き込み）スコープが付与されているか。"
            )
            self._log(f"FAILED auth: {type(e).__name__}: {e}")
            raise CommandError(msg)

        # --- sitemap 送信 -----------------------------------------------------
        try:
            service.sitemaps().submit(
                siteUrl=SITE_URL, feedpath=sitemap_url
            ).execute()
        except Exception as e:  # noqa: BLE001
            # スコープ不足（403）などはここで分かりやすく表示
            msg = (
                "sitemap の送信に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  ヒント: 403の場合は webmasters 書き込みスコープの再認証が必要です。\n"
                "    gcloud auth application-default login \\\n"
                "      --scopes=https://www.googleapis.com/auth/webmasters,openid"
            )
            self._log(f"FAILED submit {sitemap_url}: {type(e).__name__}: {e}")
            raise CommandError(msg)

        # --- 送信後の状態を取得（任意・確認用）-------------------------------
        status_line = ""
        try:
            info = service.sitemaps().get(
                siteUrl=SITE_URL, feedpath=sitemap_url
            ).execute()
            status_line = (
                f"lastSubmitted={info.get('lastSubmitted')} "
                f"isPending={info.get('isPending')} "
                f"errors={info.get('errors')} warnings={info.get('warnings')}"
            )
            self.stdout.write(f"状態    : {status_line}")
        except Exception:  # noqa: BLE001
            # 状態取得に失敗しても送信自体は成功しているので致命ではない
            status_line = "(状態取得スキップ)"

        self.stdout.write(self.style.SUCCESS("✅ sitemap 再送信 成功"))
        self._log(f"SUCCESS submit {sitemap_url} | {status_line}")

    # -------------------------------------------------------------------------
    # ログ記録
    # -------------------------------------------------------------------------
    def _log(self, message: str) -> None:
        ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        try:
            Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except OSError:
            # ログ書き込み失敗は本処理を止めない
            pass
