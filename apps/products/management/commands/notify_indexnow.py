"""
IndexNow 通知コマンド（Bing / Yandex / Naver 等向けの即時クロール通知）

記事の公開・更新URLを IndexNow API に送信し、対応検索エンジンへ即時通知する。
Google は IndexNow 非対応のため、Google向けは notify_google（sitemap再送信）を使う。

前提（重要）:
    IndexNow はサイト所有の確認のため、APIキーを記載したテキストファイルを
    サイトのルートに公開しておく必要がある。
        URL: https://sc-tsusho.jp/{KEY}.txt
        内容: {KEY} （1行）
    このキー配信のためのURLルートは別途 urls.py への追加が必要（未設定なら送信は弾かれる）。

認証:
    不要（APIキー方式）。Google ADCは使わない。

使い方:
    python manage.py notify_indexnow --url=https://sc-tsusho.jp/kousyuha/
    python manage.py notify_indexnow --url=... --url=...   # 複数指定可
    python manage.py notify_indexnow                       # URL省略時はトップページ
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError


# =============================================================================
# 設定値
# =============================================================================

HOST = "sc-tsusho.jp"
SITE_URL = "https://sc-tsusho.jp/"
KEY_FILE = "/opt/claude-ops/indexnow_key.txt"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
LOG_PATH = "/opt/claude-ops/logs/notify_indexnow.log"
JST = ZoneInfo("Asia/Tokyo")


class Command(BaseCommand):
    help = "IndexNow APIで指定URLの再クロールをBing/Yandex等へ通知する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--url", action="append", default=None,
            help="通知するURL（複数回指定可）。省略時はトップページ",
        )

    def handle(self, *args, **opts) -> None:
        urls = opts["url"] or [SITE_URL]

        # --- APIキー読込 ------------------------------------------------------
        try:
            key = Path(KEY_FILE).read_text(encoding="utf-8").strip()
        except OSError as e:
            raise CommandError(f"IndexNowキーの読込に失敗: {KEY_FILE}: {e}")
        if not key:
            raise CommandError(f"IndexNowキーが空です: {KEY_FILE}")

        key_location = f"{SITE_URL}{key}.txt"

        self.stdout.write(self.style.SUCCESS("=== IndexNow 通知 ==="))
        self.stdout.write(f"host        : {HOST}")
        self.stdout.write(f"keyLocation : {key_location}")
        self.stdout.write(f"対象URL数   : {len(urls)}")

        payload = {
            "host": HOST,
            "key": key,
            "keyLocation": key_location,
            "urlList": urls,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            INDEXNOW_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        # --- 送信 -------------------------------------------------------------
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            self._log(f"FAILED {len(urls)}url: {type(e).__name__}: {e}")
            raise CommandError(f"IndexNow送信に失敗: {type(e).__name__}: {e}")

        # IndexNowは 200/202 が成功。403=キーファイル未配置/不一致、422=URL不正
        if status in (200, 202):
            self.stdout.write(self.style.SUCCESS(f"✅ IndexNow送信 成功 (HTTP {status})"))
            self._log(f"SUCCESS {len(urls)}url HTTP {status}")
        else:
            hint = {
                403: "キーファイル未配置/不一致（https://sc-tsusho.jp/{KEY}.txt を確認）",
                422: "URLがホスト不一致、またはキー不正",
                400: "リクエスト不正",
                429: "送信過多（レート制限）",
            }.get(status, "")
            self.stdout.write(self.style.WARNING(f"⚠ HTTP {status} {hint}\n{body[:300]}"))
            self._log(f"HTTP {status} {len(urls)}url {hint}")

    def _log(self, message: str) -> None:
        ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        try:
            Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except OSError:
            pass
