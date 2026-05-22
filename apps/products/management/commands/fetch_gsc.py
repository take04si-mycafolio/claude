"""
Google Search Console データ取得コマンド

sc-tsusho.jp の検索パフォーマンスデータを Search Console API から取得し、
JSON形式でファイルに保存する。週次SEOレポート（Phase 5）の元データとして利用する。

認証:
    ADC（Application Default Credentials）を使用。
    /root/.config/gcloud/application_default_credentials.json が読み込まれる。
    必要スコープ: https://www.googleapis.com/auth/webmasters.readonly

使い方:
    python manage.py fetch_gsc                          # 直近7日（終了日=今日-3日）
    python manage.py fetch_gsc --days=30                # 直近30日
    python manage.py fetch_gsc --end-date=2026-05-19    # 終了日を明示指定
    python manage.py fetch_gsc --output=/tmp/foo.json   # 出力先を明示指定

注意:
    GSCのデータは確定までに2〜3日の遅延がある。デフォルトの終了日は
    「今日 - GSC_DATA_DELAY_DAYS日」とし、未確定データを避ける。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import google.auth
from googleapiclient.discovery import build

from django.core.management.base import BaseCommand, CommandError


# =============================================================================
# 設定値
# =============================================================================

SITE_URL = "https://sc-tsusho.jp/"
DATA_DIR = "/opt/claude-ops/seo_data"
GSC_DATA_DELAY_DAYS = 3  # GSCの遅延考慮（実データは2-3日後に確定）

# Search Console API
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
JST = ZoneInfo("Asia/Tokyo")


class Command(BaseCommand):
    help = "Search Console から sc-tsusho.jp のデータを取得しJSON保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days", type=int, default=7,
            help="取得日数（デフォルト: 7）",
        )
        parser.add_argument(
            "--end-date", type=str, default=None,
            help="終了日 YYYY-MM-DD（デフォルト: 今日 - GSC_DATA_DELAY_DAYS日）",
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="出力先パス（デフォルト: DATA_DIR/gsc_YYYYMMDD-YYYYMMDD.json）",
        )

    # -------------------------------------------------------------------------
    # エントリポイント
    # -------------------------------------------------------------------------
    def handle(self, *args, **opts) -> None:
        days: int = opts["days"]
        end_date_opt: str | None = opts["end_date"]
        output_opt: str | None = opts["output"]

        # --- 期間の決定 -------------------------------------------------------
        if end_date_opt:
            try:
                end_date = datetime.strptime(end_date_opt, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"--end-date の形式が不正です: {end_date_opt!r}（YYYY-MM-DD）")
        else:
            # GSCの遅延を考慮し、今日からGSC_DATA_DELAY_DAYS日前を終了日とする
            end_date = date.today() - timedelta(days=GSC_DATA_DELAY_DAYS)

        start_date = end_date - timedelta(days=days - 1)

        self.stdout.write(self.style.SUCCESS("=== GSCデータ取得開始 ==="))
        self.stdout.write(f"サイト   : {SITE_URL}")
        self.stdout.write(f"期間     : {start_date} 〜 {end_date}（{days}日間）")

        # --- 出力先の決定 -----------------------------------------------------
        if output_opt:
            output_path = Path(output_opt)
        else:
            # 期間付きファイル名（開始日-終了日）。同じ終了日で日数違いを実行しても上書きされない
            fname = f"gsc_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}.json"
            output_path = Path(DATA_DIR) / fname
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # --- 認証 & API初期化 -------------------------------------------------
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            service = build("searchconsole", "v1", credentials=creds)
            self.stdout.write("認証     : ADCロード成功")
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "認証またはAPI初期化に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  確認: gcloud auth application-default login が完了しているか、"
                "webmasters.readonly スコープが付与されているか。"
            )

        # --- データ取得 -------------------------------------------------------
        try:
            self.stdout.write("取得     : 全体指標 ...")
            totals = self.fetch_overall(service, start_date, end_date)

            self.stdout.write("取得     : ページ別 Top500 ...")
            pages = self.fetch_by_dimension(service, start_date, end_date, "page", 500)

            self.stdout.write("取得     : クエリ別 Top100 ...")
            queries = self.fetch_by_dimension(service, start_date, end_date, "query", 100)

            self.stdout.write("取得     : デバイス別 ...")
            devices = self.fetch_by_dimension(service, start_date, end_date, "device", 25)
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "Search Console API 呼び出しに失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                f"  対象サイト {SITE_URL} の権限、スコープ、期間指定を確認してください。"
            )

        self.stdout.write(
            f"受信     : ページ {len(pages)}件 / クエリ {len(queries)}件 / "
            f"デバイス {len(devices)}件"
        )

        # --- 出力構築 & 保存 --------------------------------------------------
        output = self.build_output(start_date, end_date, totals, pages, queries, devices)
        self.save_json(output, output_path)

        self.stdout.write(self.style.SUCCESS(f"\n💾 保存しました: {output_path}"))
        self.stdout.write(
            f"全体: クリック {totals['clicks']} / 表示 {totals['impressions']} / "
            f"CTR {totals['ctr']}% / 平均順位 {totals['position']}"
        )

    # -------------------------------------------------------------------------
    # 全体指標の取得（dimensionsなし＝期間合計1行）
    # -------------------------------------------------------------------------
    def fetch_overall(self, service, start: date, end: date) -> dict[str, float]:
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [],
        }
        resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        rows = resp.get("rows", [])
        if not rows:
            # データなしでも空（ゼロ）で返す
            return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
        row = rows[0]
        return {
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0.0) * 100, 2),       # 0-1小数 → %表記
            "position": round(row.get("position", 0.0), 2),    # 小数2桁
        }

    # -------------------------------------------------------------------------
    # ディメンション別の取得（page / query / device で共通利用）
    # -------------------------------------------------------------------------
    def fetch_by_dimension(
        self, service, start: date, end: date, dimension: str, row_limit: int
    ) -> list[dict[str, Any]]:
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [dimension],
            "rowLimit": row_limit,
        }
        resp = service.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        rows = resp.get("rows", [])

        # ディメンション名 → 出力JSONでのキー名
        key_map = {"page": "url", "query": "query", "device": "device"}
        out_key = key_map.get(dimension, dimension)

        results: list[dict[str, Any]] = []
        for row in rows:
            # keysはdimensionsの順に並ぶ。今回は単一dimensionなので[0]を使う
            keys = row.get("keys", [])
            label = keys[0] if keys else ""
            results.append({
                out_key: label,
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(row.get("ctr", 0.0) * 100, 2),    # %表記
                "position": round(row.get("position", 0.0), 2),
            })
        return results

    # -------------------------------------------------------------------------
    # 出力JSONの構築
    # -------------------------------------------------------------------------
    def build_output(
        self,
        start: date,
        end: date,
        totals: dict[str, float],
        pages: list[dict[str, Any]],
        queries: list[dict[str, Any]],
        devices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "site_url": SITE_URL,
            "fetched_at": datetime.now(JST).isoformat(),
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "totals": totals,
            "pages": pages,
            "queries": queries,
            "devices": devices,
        }

    # -------------------------------------------------------------------------
    # JSON保存
    # -------------------------------------------------------------------------
    def save_json(self, data: dict[str, Any], path: Path) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
