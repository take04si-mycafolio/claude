"""
週次SEOレポート生成コマンド

GSC（Search Console）と GA4（Analytics）のデータを「今週(直近7日)」「前週(8-14日前)」で
取得・比較し、気づきを抽出して Markdown レポートを生成する。
結果は SeoWeeklyReport モデル（管理画面で閲覧可）と /opt/claude-ops/reports/ の .md に保存する。

データ取得は既存の fetch_gsc / fetch_ga コマンドのメソッドを再利用する。

使い方:
    python manage.py weekly_seo_report               # 本番（DB + ファイル保存）
    python manage.py weekly_seo_report --dry-run      # Markdownのみ出力（保存なし）
    python manage.py weekly_seo_report --end-date=2026-05-19

期間の決め方:
    GSCは2〜3日遅延、GA4は前日まで取れる。両者が確定済みで重なる範囲として、
    デフォルトの「今週終了日」は「今日 - GSC_DATA_DELAY_DAYS日」とし、GSC/GAともこの終了日で揃える。
    これによりオーガニック比率（GSCクリック / GAセッション）の突合が公平になる。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import google.auth
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient

from django.core.management.base import BaseCommand, CommandError

from apps.products.models import SeoWeeklyReport
from apps.products.management.commands import fetch_gsc, fetch_ga


# =============================================================================
# 設定値
# =============================================================================

REPORTS_DIR = "/opt/claude-ops/reports"
SEO_DATA_DIR = "/opt/claude-ops/seo_data"
GSC_DELAY_DAYS = fetch_gsc.GSC_DATA_DELAY_DAYS  # 3
JST = ZoneInfo("Asia/Tokyo")

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# 分析しきい値
LOSER_MIN_IMPRESSIONS = 20      # 順位低下判定の最低表示回数
LOSER_MIN_POSITION_DROP = 3.0   # 順位悪化の最低幅
PUSH_POSITION_MIN = 11.0        # もう一押し候補の順位下限
PUSH_POSITION_MAX = 20.0        # もう一押し候補の順位上限
PUSH_MIN_IMPRESSIONS = 30       # もう一押し候補の最低表示回数
CTR_MIN_IMPRESSIONS = 50        # CTR弱者判定の最低表示回数
CTR_THRESHOLD = 2.0             # CTR弱者のしきい値（%）

# Phase 5b検証時の旧ファイル（存在すれば掃除する）
LEGACY_FILES = [
    "gsc_20260519.json",
    "gsc_7d.json",
    "gsc_30d.json",
]


# =============================================================================
# ユーティリティ
# =============================================================================

def normalize_url(url: str) -> str:
    """GSCのフルURL / GA4のパスを統一パス形式に変換する。
    例: "https://sc-tsusho.jp/kousyuha/" → "/kousyuha/"
        "/kousyuha/"                     → "/kousyuha/"
    """
    if not url:
        return "/"
    if url.startswith("http://") or url.startswith("https://"):
        path = urlparse(url).path
    else:
        path = url
    if not path.startswith("/"):
        path = "/" + path
    return path


def pct_change(now: float, prev: float) -> float | None:
    """前週比（%）。前週が0なら None（「-」表示用）。"""
    if prev == 0:
        return None
    return round((now - prev) / prev * 100, 1)


def fmt_change(now: float, prev: float, unit: str = "") -> str:
    """前週比を矢印付き文字列に整形。前週0なら「-」。"""
    c = pct_change(now, prev)
    if c is None:
        return "-"
    arrow = "▲" if c > 0 else ("▼" if c < 0 else "→")
    return f"{arrow}{abs(c)}%{unit}"


def pages_by_path(pages: list[dict[str, Any]], url_key: str) -> dict[str, dict[str, Any]]:
    """ページリストを正規化パスをキーにした辞書へ変換。"""
    result: dict[str, dict[str, Any]] = {}
    for p in pages:
        path = normalize_url(p.get(url_key, ""))
        result[path] = p
    return result


class Command(BaseCommand):
    help = "GSC/GA4データから週次SEOレポートを生成しDB・ファイルに保存する"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--end-date", type=str, default=None,
            help="今週の終了日 YYYY-MM-DD（デフォルト: 今日 - GSC遅延日数）",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="DB・ファイル保存をせず、Markdownのみ標準出力する",
        )

    # -------------------------------------------------------------------------
    # エントリポイント
    # -------------------------------------------------------------------------
    def handle(self, *args, **opts) -> None:
        end_date_opt: str | None = opts["end_date"]
        dry_run: bool = opts["dry_run"]

        # --- 旧ファイルの掃除（存在すれば）-----------------------------------
        self._cleanup_legacy_files()

        # --- 期間の決定 -------------------------------------------------------
        if end_date_opt:
            try:
                tw_end = datetime.strptime(end_date_opt, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"--end-date の形式が不正です: {end_date_opt!r}（YYYY-MM-DD）")
        else:
            tw_end = date.today() - timedelta(days=GSC_DELAY_DAYS)

        tw_start = tw_end - timedelta(days=6)        # 今週: 直近7日
        lw_end = tw_end - timedelta(days=7)          # 前週終了
        lw_start = tw_end - timedelta(days=13)       # 前週: 8-14日前

        self.stdout.write(self.style.SUCCESS("=== 週次SEOレポート生成開始 ==="))
        self.stdout.write(f"今週: {tw_start} 〜 {tw_end}")
        self.stdout.write(f"前週: {lw_start} 〜 {lw_end}")

        # --- データ取得 -------------------------------------------------------
        data = self.fetch_data(tw_start, tw_end, lw_start, lw_end)

        # --- 分析 -------------------------------------------------------------
        analysis = self.analyze(data)

        # --- Markdown生成 -----------------------------------------------------
        period = {
            "tw_start": tw_start, "tw_end": tw_end,
            "lw_start": lw_start, "lw_end": lw_end,
        }
        markdown = self.generate_markdown(period, data, analysis)

        # --- 出力 -------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("\n--- [DRY-RUN] 以下Markdown（DB/ファイル保存なし）---\n"))
            self.stdout.write(markdown)
            return

        report = self.save_to_db(period, data, analysis, markdown)
        file_path = self.save_to_file(markdown, tw_end)

        self.stdout.write(self.style.SUCCESS(f"\n✅ DB保存完了: SeoWeeklyReport id={report.id}"))
        self.stdout.write(self.style.SUCCESS(f"💾 ファイル保存: {file_path}"))
        self.stdout.write("管理画面: https://sc-tsusho.jp/admin/products/seoweeklyreport/")

    # -------------------------------------------------------------------------
    # 旧ファイル掃除
    # -------------------------------------------------------------------------
    def _cleanup_legacy_files(self) -> None:
        for name in LEGACY_FILES:
            p = Path(SEO_DATA_DIR) / name
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    # -------------------------------------------------------------------------
    # データ取得（今週・前週を別々に取得）
    # -------------------------------------------------------------------------
    def fetch_data(
        self, tw_start: date, tw_end: date, lw_start: date, lw_end: date
    ) -> dict[str, Any]:
        # 認証 & クライアント構築
        try:
            gsc_creds, _ = google.auth.default(scopes=GSC_SCOPES)
            gsc_service = build("searchconsole", "v1", credentials=gsc_creds)
            ga_creds, _ = google.auth.default(scopes=GA_SCOPES)
            ga_client = BetaAnalyticsDataClient(credentials=ga_creds)
            self.stdout.write("認証     : ADCロード成功（GSC/GA4）")
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                f"認証/クライアント初期化に失敗: {type(e).__name__}: {e}"
            )

        gsc = fetch_gsc.Command()
        ga = fetch_ga.Command()

        try:
            self.stdout.write("取得     : GSC 今週 ...")
            gsc_tw = self._gsc_bundle(gsc, gsc_service, tw_start, tw_end)
            self.stdout.write("取得     : GSC 前週 ...")
            gsc_lw = self._gsc_bundle(gsc, gsc_service, lw_start, lw_end)

            self.stdout.write("取得     : GA4 今週 ...")
            ga_tw = self._ga_bundle(ga, ga_client, tw_start, tw_end)
            self.stdout.write("取得     : GA4 前週 ...")
            ga_lw = self._ga_bundle(ga, ga_client, lw_start, lw_end)
        except Exception as e:  # noqa: BLE001
            raise CommandError(
                f"API取得に失敗: {type(e).__name__}: {e}"
            )

        self.stdout.write(
            f"受信     : GSC今週ページ {len(gsc_tw['pages'])} / GA4今週ページ {len(ga_tw['pages'])}"
        )
        return {
            "gsc_tw": gsc_tw, "gsc_lw": gsc_lw,
            "ga_tw": ga_tw, "ga_lw": ga_lw,
        }

    def _gsc_bundle(self, gsc, service, start: date, end: date) -> dict[str, Any]:
        return {
            "totals": gsc.fetch_overall(service, start, end),
            "pages": gsc.fetch_by_dimension(service, start, end, "page", 500),
            "queries": gsc.fetch_by_dimension(service, start, end, "query", 100),
            "devices": gsc.fetch_by_dimension(service, start, end, "device", 25),
        }

    def _ga_bundle(self, ga, client, start: date, end: date) -> dict[str, Any]:
        return {
            "totals": ga.fetch_overall(client, start, end),
            "pages": ga.fetch_by_dimension(
                client, start, end,
                dimensions=["pagePath"],
                metrics=["sessions", "screenPageViews", "activeUsers",
                         "averageSessionDuration", "bounceRate"],
                limit=100,
            ),
            "sources": ga.fetch_by_dimension(
                client, start, end,
                dimensions=["sessionSource", "sessionMedium"],
                metrics=["sessions", "engagedSessions"],
                limit=50,
            ),
            "devices": ga.fetch_by_dimension(
                client, start, end,
                dimensions=["deviceCategory"],
                metrics=["sessions", "screenPageViews"],
                limit=25,
            ),
        }

    # -------------------------------------------------------------------------
    # 分析
    # -------------------------------------------------------------------------
    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        gsc_tw_pages = pages_by_path(data["gsc_tw"]["pages"], "url")
        gsc_lw_pages = pages_by_path(data["gsc_lw"]["pages"], "url")

        winners = self._calc_winners(gsc_tw_pages, gsc_lw_pages)
        losers = self._calc_losers(gsc_tw_pages, gsc_lw_pages)
        rewrite_candidates = self._calc_push_candidates(gsc_tw_pages)
        ctr_underperformers = self._calc_ctr_underperformers(gsc_tw_pages)

        # サマリ指標
        gsc_t = data["gsc_tw"]["totals"]
        gsc_p = data["gsc_lw"]["totals"]
        ga_t = data["ga_tw"]["totals"]
        ga_p = data["ga_lw"]["totals"]

        organic_ratio = None
        if ga_t["sessions"] > 0:
            organic_ratio = round(gsc_t["clicks"] / ga_t["sessions"] * 100, 1)

        summary = {
            "clicks": gsc_t["clicks"], "clicks_prev": gsc_p["clicks"],
            "impressions": gsc_t["impressions"], "impressions_prev": gsc_p["impressions"],
            "ctr": gsc_t["ctr"], "ctr_prev": gsc_p["ctr"],
            "position": gsc_t["position"], "position_prev": gsc_p["position"],
            "sessions": ga_t["sessions"], "sessions_prev": ga_p["sessions"],
            "bounce_rate": ga_t["bounce_rate"], "bounce_rate_prev": ga_p["bounce_rate"],
            "clicks_change_pct": pct_change(gsc_t["clicks"], gsc_p["clicks"]),
            "sessions_change_pct": pct_change(ga_t["sessions"], ga_p["sessions"]),
            "organic_ratio": organic_ratio,
        }

        # デバイス偏り（GA4セッションベース）
        device_stats = self._calc_device_split(data["ga_tw"]["devices"])
        # 流入元TOP5
        top_sources = self._calc_top_sources(data["ga_tw"]["sources"], 5)

        # アクション提案
        actions = self._build_actions(ctr_underperformers, rewrite_candidates, losers)

        # 上位ページ・上位クエリ（今週、クリック降順）
        top_pages = sorted(
            data["gsc_tw"]["pages"], key=lambda x: x.get("clicks", 0), reverse=True
        )[:20]
        top_queries = sorted(
            data["gsc_tw"]["queries"], key=lambda x: x.get("clicks", 0), reverse=True
        )[:20]

        return {
            "summary": summary,
            "winners": winners,
            "losers": losers,
            "rewrite_candidates": rewrite_candidates,
            "ctr_underperformers": ctr_underperformers,
            "device_stats": device_stats,
            "top_sources": top_sources,
            "actions": actions,
            "top_pages": top_pages,
            "top_queries": top_queries,
        }

    def _calc_winners(self, tw: dict, lw: dict) -> list[dict[str, Any]]:
        """今週クリック>=1かつ増加量>0のページを増加量降順TOP3。"""
        rows = []
        for path, p in tw.items():
            tw_clicks = p.get("clicks", 0)
            if tw_clicks < 1:
                continue
            lw_clicks = lw.get(path, {}).get("clicks", 0)
            delta = tw_clicks - lw_clicks
            if delta <= 0:
                continue
            rows.append({
                "path": path,
                "clicks_prev": lw_clicks,
                "clicks_now": tw_clicks,
                "clicks_delta": delta,
                "position_prev": lw.get(path, {}).get("position", 0.0),
                "position_now": p.get("position", 0.0),
            })
        rows.sort(key=lambda x: x["clicks_delta"], reverse=True)
        return rows[:3]

    def _calc_losers(self, tw: dict, lw: dict) -> list[dict[str, Any]]:
        """今週・前週とも表示>=20かつ順位が3以上悪化したページ。"""
        rows = []
        for path, p in tw.items():
            lw_p = lw.get(path)
            if not lw_p:
                continue
            tw_impr = p.get("impressions", 0)
            lw_impr = lw_p.get("impressions", 0)
            if tw_impr < LOSER_MIN_IMPRESSIONS or lw_impr < LOSER_MIN_IMPRESSIONS:
                continue
            tw_pos = p.get("position", 0.0)
            lw_pos = lw_p.get("position", 0.0)
            drop = tw_pos - lw_pos  # 正なら悪化（順位の数字が大きくなった）
            if drop < LOSER_MIN_POSITION_DROP:
                continue
            rows.append({
                "path": path,
                "position_prev": lw_pos,
                "position_now": tw_pos,
                "position_drop": round(drop, 2),
                "clicks_prev": lw_p.get("clicks", 0),
                "clicks_now": p.get("clicks", 0),
            })
        rows.sort(key=lambda x: x["position_drop"], reverse=True)
        return rows

    def _calc_push_candidates(self, tw: dict) -> list[dict[str, Any]]:
        """今週順位11-20かつ表示>=30のページ（1ページ目突入の現実味）。"""
        rows = []
        for path, p in tw.items():
            pos = p.get("position", 0.0)
            impr = p.get("impressions", 0)
            if PUSH_POSITION_MIN <= pos <= PUSH_POSITION_MAX and impr >= PUSH_MIN_IMPRESSIONS:
                rows.append({
                    "path": path,
                    "position": pos,
                    "impressions": impr,
                    "clicks": p.get("clicks", 0),
                    "ctr": p.get("ctr", 0.0),
                })
        rows.sort(key=lambda x: x["impressions"], reverse=True)
        return rows

    def _calc_ctr_underperformers(self, tw: dict) -> list[dict[str, Any]]:
        """今週表示>=50かつCTR<2.0%のページ（タイトル/meta改善候補）。"""
        rows = []
        for path, p in tw.items():
            impr = p.get("impressions", 0)
            ctr = p.get("ctr", 0.0)
            if impr >= CTR_MIN_IMPRESSIONS and ctr < CTR_THRESHOLD:
                rows.append({
                    "path": path,
                    "impressions": impr,
                    "ctr": ctr,
                    "position": p.get("position", 0.0),
                    "clicks": p.get("clicks", 0),
                })
        rows.sort(key=lambda x: x["impressions"], reverse=True)
        return rows

    def _calc_device_split(self, devices: list[dict[str, Any]]) -> dict[str, Any]:
        total = sum(d.get("sessions", 0) for d in devices)
        split = {}
        for d in devices:
            split[d.get("device", "unknown")] = d.get("sessions", 0)
        mobile = split.get("mobile", 0)
        desktop = split.get("desktop", 0)
        tablet = split.get("tablet", 0)
        return {
            "total": total,
            "mobile": mobile,
            "desktop": desktop,
            "tablet": tablet,
            "mobile_pct": round(mobile / total * 100, 1) if total else 0.0,
            "desktop_pct": round(desktop / total * 100, 1) if total else 0.0,
            "tablet_pct": round(tablet / total * 100, 1) if total else 0.0,
        }

    def _calc_top_sources(self, sources: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        rows = sorted(sources, key=lambda x: x.get("sessions", 0), reverse=True)
        return rows[:n]

    def _build_actions(
        self,
        ctr_under: list[dict[str, Any]],
        push: list[dict[str, Any]],
        losers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """分析結果から具体的なClaude Code指示文を生成。"""
        actions: list[dict[str, Any]] = []

        for r in ctr_under[:3]:
            # CTRを現状から+2pt程度を目標に提案
            target = max(round(r["ctr"] + 2.0, 1), 4.0)
            actions.append({
                "type": "CTR改善",
                "path": r["path"],
                "reason": f"表示{r['impressions']}回・CTR{r['ctr']}%・順位{r['position']}",
                "instruction": (
                    f"claude '{r['path']} のmeta_descriptionとtitleをCTR{target}%目標で再リライトして'"
                ),
            })

        for r in push[:3]:
            actions.append({
                "type": "もう一押し",
                "path": r["path"],
                "reason": f"順位{r['position']}・表示{r['impressions']}回（1ページ目目前）",
                "instruction": (
                    f"claude '{r['path']} のコンテンツを加筆・内部リンク強化して順位を1ページ目に上げて'"
                ),
            })

        for r in losers[:3]:
            actions.append({
                "type": "順位低下",
                "path": r["path"],
                "reason": f"順位 {r['position_prev']}→{r['position_now']}（{r['position_drop']}悪化）",
                "instruction": (
                    f"claude '{r['path']} の順位低下要因を調査してリライト案を出して'"
                ),
            })

        return actions

    # -------------------------------------------------------------------------
    # Markdown生成
    # -------------------------------------------------------------------------
    def generate_markdown(
        self, period: dict[str, date], data: dict[str, Any], analysis: dict[str, Any]
    ) -> str:
        s = analysis["summary"]
        L: list[str] = []
        now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

        L.append(f"# 📊 TSUSHO 週次SEOレポート ({period['tw_start']} 〜 {period['tw_end']})")
        L.append("")
        L.append(f"生成日時: {now_str} (JST)")
        L.append("")

        # --- サマリ ---
        L.append("## 📈 サマリ")
        L.append("")
        L.append("| 指標 | 今週 | 前週 | 前週比 |")
        L.append("|------|-----:|-----:|:------:|")
        L.append(f"| 総クリック数 | {s['clicks']:,} | {s['clicks_prev']:,} | {fmt_change(s['clicks'], s['clicks_prev'])} |")
        L.append(f"| 総表示回数 | {s['impressions']:,} | {s['impressions_prev']:,} | {fmt_change(s['impressions'], s['impressions_prev'])} |")
        L.append(f"| 平均CTR | {s['ctr']}% | {s['ctr_prev']}% | {fmt_change(s['ctr'], s['ctr_prev'])} |")
        L.append(f"| 平均掲載順位 | {s['position']} | {s['position_prev']} | {self._position_change_str(s['position'], s['position_prev'])} |")
        L.append(f"| 総セッション数 | {s['sessions']:,} | {s['sessions_prev']:,} | {fmt_change(s['sessions'], s['sessions_prev'])} |")
        L.append(f"| 直帰率 | {s['bounce_rate']} | {s['bounce_rate_prev']} | {fmt_change(s['bounce_rate'], s['bounce_rate_prev'])} |")
        org = f"{s['organic_ratio']}%" if s["organic_ratio"] is not None else "-"
        L.append(f"| オーガニック比率 | {org} | - | (GSCクリック/GAセッション) |")
        L.append("")

        # --- 勝者 ---
        L.append("## 🚀 今週の勝者TOP3")
        L.append("")
        if analysis["winners"]:
            L.append("| ページ | 前週→今週 クリック | 順位変化 |")
            L.append("|--------|:-----------------:|:--------:|")
            for w in analysis["winners"]:
                L.append(
                    f"| {w['path']} | {w['clicks_prev']}→{w['clicks_now']} (+{w['clicks_delta']}) | "
                    f"{w['position_prev']}→{w['position_now']} |"
                )
        else:
            L.append("_該当ページなし（今週クリック増のページがありませんでした）_")
        L.append("")

        # --- 順位低下 ---
        L.append("## 📉 順位を落としたページ")
        L.append("")
        if analysis["losers"]:
            L.append("| ページ | 順位 前週→今週 | 悪化幅 | クリック 前週→今週 |")
            L.append("|--------|:-------------:|:-----:|:-----------------:|")
            for r in analysis["losers"]:
                L.append(
                    f"| {r['path']} | {r['position_prev']}→{r['position_now']} | "
                    f"+{r['position_drop']} | {r['clicks_prev']}→{r['clicks_now']} |"
                )
        else:
            L.append("_該当ページなし（表示20回以上で3位以上悪化したページなし）_")
        L.append("")

        # --- もう一押し ---
        L.append("## 💎 もう一押し候補（順位11-20）")
        L.append("")
        if analysis["rewrite_candidates"]:
            L.append("| ページ | 順位 | 表示回数 | クリック | CTR |")
            L.append("|--------|:----:|:--------:|:--------:|:---:|")
            for r in analysis["rewrite_candidates"]:
                L.append(
                    f"| {r['path']} | {r['position']} | {r['impressions']:,} | "
                    f"{r['clicks']} | {r['ctr']}% |"
                )
        else:
            L.append("_該当ページなし（順位11-20かつ表示30回以上のページなし）_")
        L.append("")

        # --- CTR弱者 ---
        L.append("## 🎯 CTR弱者（タイトル/meta改善候補）")
        L.append("")
        if analysis["ctr_underperformers"]:
            L.append("| ページ | 表示回数 | CTR | 順位 |")
            L.append("|--------|:--------:|:---:|:----:|")
            for r in analysis["ctr_underperformers"]:
                L.append(
                    f"| {r['path']} | {r['impressions']:,} | {r['ctr']}% | {r['position']} |"
                )
        else:
            L.append("_該当ページなし（表示50回以上でCTR2%未満のページなし）_")
        L.append("")

        # --- 流入の質 ---
        d = analysis["device_stats"]
        L.append("## 📊 流入の質")
        L.append("")
        L.append(
            f"- **デバイス比率（GAセッション）**: モバイル {d['mobile']} ({d['mobile_pct']}%) / "
            f"PC {d['desktop']} ({d['desktop_pct']}%) / タブレット {d['tablet']} ({d['tablet_pct']}%)"
        )
        L.append("- **流入元TOP5（GA4）**:")
        if analysis["top_sources"]:
            for i, src in enumerate(analysis["top_sources"], 1):
                L.append(
                    f"  {i}. {src.get('source', '?')} / {src.get('medium', '?')} — "
                    f"{src.get('sessions', 0)}セッション（エンゲージ {src.get('engaged_sessions', 0)}）"
                )
        else:
            L.append("  _データなし_")
        L.append("")

        # --- アクション提案 ---
        L.append("## 🎬 今週のアクション提案")
        L.append("")
        if analysis["actions"]:
            for i, a in enumerate(analysis["actions"], 1):
                L.append(f"{i}. **[{a['type']}]** `{a['path']}` — {a['reason']}")
                L.append("   ```")
                L.append(f"   {a['instruction']}")
                L.append("   ```")
        else:
            L.append("_今週は緊急のアクション提案はありません。好調を維持しましょう。_")
        L.append("")

        # --- 補足 ---
        L.append("## 📝 補足")
        L.append("")
        L.append(
            f"- データ範囲: GSCは{period['tw_start']}〜{period['tw_end']}、"
            f"GAは{period['tw_start']}〜{period['tw_end']}（両者とも同一終了日で揃え、突合の公平性を確保）"
        )
        L.append("- 注: GSCは2-3日の遅延があるため、終了日は今日より数日前に設定しています")
        L.append("- 全データの詳細は /opt/claude-ops/seo_data/ 配下のJSONを参照")
        L.append("")

        return "\n".join(L)

    def _position_change_str(self, now: float, prev: float) -> str:
        """掲載順位は小さいほど良い。改善（数字減）を▲、悪化（数字増）を▼で表す。"""
        if prev == 0:
            return "-"
        diff = round(now - prev, 2)
        if diff < 0:
            return f"▲改善{abs(diff)}"
        elif diff > 0:
            return f"▼悪化{diff}"
        return "→"

    # -------------------------------------------------------------------------
    # DB保存
    # -------------------------------------------------------------------------
    def save_to_db(
        self,
        period: dict[str, date],
        data: dict[str, Any],
        analysis: dict[str, Any],
        markdown: str,
    ) -> SeoWeeklyReport:
        s = analysis["summary"]
        report = SeoWeeklyReport.objects.create(
            period_start=period["tw_start"],
            period_end=period["tw_end"],
            total_clicks=s["clicks"],
            total_impressions=s["impressions"],
            total_sessions=s["sessions"],
            avg_ctr=s["ctr"],
            avg_position=s["position"],
            clicks_change_pct=s["clicks_change_pct"] or 0.0,
            sessions_change_pct=s["sessions_change_pct"] or 0.0,
            top_pages=analysis["top_pages"],
            top_queries=analysis["top_queries"],
            winners=analysis["winners"],
            losers=analysis["losers"],
            rewrite_candidates=analysis["rewrite_candidates"],
            ctr_underperformers=analysis["ctr_underperformers"],
            suggested_actions=analysis["actions"],
            report_markdown=markdown,
        )
        return report

    # -------------------------------------------------------------------------
    # ファイル保存
    # -------------------------------------------------------------------------
    def save_to_file(self, markdown: str, tw_end: date) -> Path:
        Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)
        path = Path(REPORTS_DIR) / f"seo_weekly_{tw_end.strftime('%Y%m%d')}.md"
        path.write_text(markdown, encoding="utf-8")
        return path
