"""
Google Analytics 4 (GA4) データ取得コマンド

sc-tsusho.jp の GA4 プロパティからセッション関連データを取得し、
JSON形式でファイルに保存する。週次SEOレポート（Phase 5）の元データとして利用する。

認証:
    ADC（Application Default Credentials）を使用。
    /root/.config/gcloud/application_default_credentials.json が読み込まれる。
    必要スコープ: https://www.googleapis.com/auth/analytics.readonly

使い方:
    python manage.py fetch_ga                          # 直近7日（終了日=昨日）
    python manage.py fetch_ga --days=30                # 直近30日
    python manage.py fetch_ga --end-date=2026-05-21    # 終了日を明示指定
    python manage.py fetch_ga --output=/tmp/foo.json   # 出力先を明示指定

注意:
    GA4のデータ遅延はGSCより小さいため、デフォルトの終了日は「昨日」とする。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import google.auth
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)

from django.core.management.base import BaseCommand, CommandError


# =============================================================================
# 設定値
# =============================================================================

GA4_PROPERTY_ID = "366735446"
DATA_DIR = "/opt/claude-ops/seo_data"

# GA4 Data API
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
JST = ZoneInfo("Asia/Tokyo")


class Command(BaseCommand):
    help = "GA4 から sc-tsusho.jp のセッションデータを取得しJSON保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days", type=int, default=7,
            help="取得日数（デフォルト: 7）",
        )
        parser.add_argument(
            "--end-date", type=str, default=None,
            help="終了日 YYYY-MM-DD（デフォルト: 昨日）",
        )
        parser.add_argument(
            "--output", type=str, default=None,
            help="出力先パス（デフォルト: DATA_DIR/ga_YYYYMMDD-YYYYMMDD.json）",
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
            # GA4は遅延が小さいため終了日は昨日
            end_date = date.today() - timedelta(days=1)

        start_date = end_date - timedelta(days=days - 1)

        self.stdout.write(self.style.SUCCESS("=== GA4データ取得開始 ==="))
        self.stdout.write(f"プロパティ: properties/{GA4_PROPERTY_ID}")
        self.stdout.write(f"期間     : {start_date} 〜 {end_date}（{days}日間）")

        # --- 出力先の決定 -----------------------------------------------------
        if output_opt:
            output_path = Path(output_opt)
        else:
            # 期間付きファイル名（開始日-終了日）。同じ終了日で日数違いを実行しても上書きされない
            fname = f"ga_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}.json"
            output_path = Path(DATA_DIR) / fname
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # --- 認証 & クライアント初期化 ----------------------------------------
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            client = BetaAnalyticsDataClient(credentials=creds)
            self.stdout.write("認証     : ADCロード成功")
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "認証またはクライアント初期化に失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                "  確認: gcloud auth application-default login が完了しているか、"
                "analytics.readonly スコープが付与されているか。"
            )

        # --- データ取得 -------------------------------------------------------
        try:
            self.stdout.write("取得     : 全体指標 ...")
            totals = self.fetch_overall(client, start_date, end_date)

            self.stdout.write("取得     : ページ別 Top100 ...")
            pages = self.fetch_by_dimension(
                client, start_date, end_date,
                dimensions=["pagePath"],
                metrics=["sessions", "screenPageViews", "activeUsers",
                         "averageSessionDuration", "bounceRate"],
                limit=100,
            )

            self.stdout.write("取得     : 流入元別 Top50 ...")
            sources = self.fetch_by_dimension(
                client, start_date, end_date,
                dimensions=["sessionSource", "sessionMedium"],
                metrics=["sessions", "engagedSessions"],
                limit=50,
            )

            self.stdout.write("取得     : デバイス別 ...")
            devices = self.fetch_by_dimension(
                client, start_date, end_date,
                dimensions=["deviceCategory"],
                metrics=["sessions", "screenPageViews"],
                limit=25,
            )
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                "GA4 Data API 呼び出しに失敗しました。\n"
                f"  詳細: {type(e).__name__}: {e}\n"
                f"  プロパティ {GA4_PROPERTY_ID} の権限、スコープ、期間指定を確認してください。"
            )

        self.stdout.write(
            f"受信     : ページ {len(pages)}件 / 流入元 {len(sources)}件 / "
            f"デバイス {len(devices)}件"
        )

        # --- 出力構築 & 保存 --------------------------------------------------
        output = self.build_output(start_date, end_date, totals, pages, sources, devices)
        self.save_json(output, output_path)

        self.stdout.write(self.style.SUCCESS(f"\n💾 保存しました: {output_path}"))
        self.stdout.write(
            f"全体: セッション {totals['sessions']} / アクティブUU {totals['active_users']} / "
            f"PV {totals['page_views']} / 平均滞在 {totals['avg_session_duration_sec']}秒 / "
            f"直帰率 {totals['bounce_rate']}"
        )

    # -------------------------------------------------------------------------
    # 全体指標の取得（dimensionsなし＝期間合計1行）
    # -------------------------------------------------------------------------
    def fetch_overall(
        self, client: BetaAnalyticsDataClient, start: date, end: date
    ) -> dict[str, float]:
        metric_names = [
            "sessions", "activeUsers", "screenPageViews",
            "averageSessionDuration", "bounceRate", "engagedSessions",
        ]
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            metrics=[Metric(name=m) for m in metric_names],
        )
        resp = client.run_report(request)

        if not resp.rows:
            # データなしでも空（ゼロ）で返す
            return {
                "sessions": 0, "active_users": 0, "page_views": 0,
                "avg_session_duration_sec": 0.0, "bounce_rate": 0.0,
                "engaged_sessions": 0,
            }

        # metric値はリクエストしたmetricの順に並ぶ
        vals = resp.rows[0].metric_values
        v = {name: vals[i].value for i, name in enumerate(metric_names)}
        return {
            "sessions": int(float(v["sessions"])),
            "active_users": int(float(v["activeUsers"])),
            "page_views": int(float(v["screenPageViews"])),
            "avg_session_duration_sec": round(float(v["averageSessionDuration"]), 2),
            "bounce_rate": round(float(v["bounceRate"]), 4),   # 0-1の小数のまま
            "engaged_sessions": int(float(v["engagedSessions"])),
        }

    # -------------------------------------------------------------------------
    # ディメンション別の取得（page / source / device で共通利用）
    # -------------------------------------------------------------------------
    def fetch_by_dimension(
        self,
        client: BetaAnalyticsDataClient,
        start: date,
        end: date,
        dimensions: list[str],
        metrics: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            # sessions（先頭metric想定）の降順で並べる
            order_bys=[
                OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                    desc=True,
                )
            ],
            limit=limit,
        )
        resp = client.run_report(request)

        results: list[dict[str, Any]] = []
        for row in resp.rows:
            dim_vals = [d.value for d in row.dimension_values]
            met_vals = {metrics[i]: row.metric_values[i].value for i in range(len(metrics))}
            results.append(self._format_row(dimensions, dim_vals, met_vals))
        return results

    # -------------------------------------------------------------------------
    # 行データを出力JSON用の辞書に整形（ディメンション構成ごとにキー名を割当）
    # -------------------------------------------------------------------------
    def _format_row(
        self, dimensions: list[str], dim_vals: list[str], met: dict[str, str]
    ) -> dict[str, Any]:
        row: dict[str, Any] = {}

        # --- ディメンション部分のキー割当 ---
        if dimensions == ["pagePath"]:
            row["path"] = dim_vals[0]
        elif dimensions == ["sessionSource", "sessionMedium"]:
            row["source"] = dim_vals[0]
            row["medium"] = dim_vals[1]
        elif dimensions == ["deviceCategory"]:
            row["device"] = dim_vals[0]
        else:
            # 想定外の構成でも素直に並べる
            for name, val in zip(dimensions, dim_vals):
                row[name] = val

        # --- メトリクス部分のキー割当（GA4名 → 出力名）---
        metric_key_map = {
            "sessions": "sessions",
            "screenPageViews": "page_views",
            "activeUsers": "active_users",
            "averageSessionDuration": "avg_duration_sec",
            "bounceRate": "bounce_rate",
            "engagedSessions": "engaged_sessions",
        }
        int_metrics = {"sessions", "screenPageViews", "activeUsers", "engagedSessions"}

        for ga_name, raw in met.items():
            out_name = metric_key_map.get(ga_name, ga_name)
            if ga_name in int_metrics:
                row[out_name] = int(float(raw))
            elif ga_name == "bounceRate":
                row[out_name] = round(float(raw), 4)   # 0-1の小数のまま
            else:  # averageSessionDuration など
                row[out_name] = round(float(raw), 2)
        return row

    # -------------------------------------------------------------------------
    # 出力JSONの構築
    # -------------------------------------------------------------------------
    def build_output(
        self,
        start: date,
        end: date,
        totals: dict[str, float],
        pages: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        devices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "property_id": GA4_PROPERTY_ID,
            "fetched_at": datetime.now(JST).isoformat(),
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "totals": totals,
            "pages": pages,
            "sources": sources,
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
