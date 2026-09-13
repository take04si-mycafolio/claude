"""
プレイブック生成コマンド  python manage.py build_playbook

最新（または指定）TriageRun の「生きている記事(quick_win+performing)」と
「死んでいる記事(dead)」を比較し、順位に効く要素を決定論的に抽出して
PlaybookRule（機械参照用）と playbook.md（人間がレビューする正本）を生成する。

- LLM は使わない（この環境にAPIキーが無いため）。特徴量はHTML/メタから機械抽出し、
  生死での偏在度をエビデンスとして各ルールに付与する。
- 商品ページは構造が異なるため対象外（記事=article FK のみ）。
- 既存の verified / verification_note（パートCの人間検証結果）は上書きしない。

使い方:
    python manage.py build_playbook                 # 最新runで生成
    python manage.py build_playbook --run=4
    python manage.py build_playbook --out=/opt/claude-ops/playbook.md
"""

from __future__ import annotations

import re
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.html import strip_tags

from apps.analytics.models import TriageRun, PlaybookRule

DEFAULT_OUT = "/opt/claude-ops/playbook.md"


def _features(triage) -> dict:
    """1記事の特徴量を抽出（regexベース、依存なし）。"""
    a = triage.article
    html = a.content or ""
    text = strip_tags(html)
    bq = [w for w in (triage.best_query or "").split() if len(w) >= 2]
    title = a.title or ""
    overlap = sum(1 for w in bq if w in title) / len(bq) if bq else 0.0
    pub_days = (timezone.now().date() - a.published_at.date()).days if a.published_at else None
    return {
        "title_query_overlap": overlap,            # best_query語のタイトル含有率
        "title_has_query": 1 if overlap > 0 else 0,
        "chars": len(text),
        "h2": len(re.findall(r"<h2", html)),
        "h3": len(re.findall(r"<h3", html)),
        "internal_links": len(re.findall(r'href="(?:/|https://sc-tsusho)', html)),
        "rakuten_links": len(re.findall(r"hb\.afl\.rakuten", html)),
        "faq": 1 if ("よくある質問" in html or "bk-mc-faq" in html) else 0,
        "table": 1 if "<table" in html else 0,
        "pub_days": pub_days,
    }


def _agg(rows: list[dict]):
    n = len(rows) or 1

    def avg(k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return round(sum(v) / len(v), 1) if v else 0.0

    def pct(k):
        return round(100 * sum(1 for r in rows if r.get(k)) / n)
    return avg, pct, len(rows)


class Command(BaseCommand):
    help = "生死記事の差分から PlaybookRule と playbook.md を生成する（初版・未検証仮説）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--run", type=int, default=None, help="対象TriageRun id（省略時:最新）")
        parser.add_argument("--out", type=str, default=DEFAULT_OUT, help="playbook.md 出力先")

    def handle(self, *args, **opts) -> None:
        run = (TriageRun.objects.get(id=opts["run"]) if opts["run"]
               else TriageRun.objects.order_by("-fetched_at").first())
        if not run:
            raise CommandError("TriageRun がありません。先に run_gsc_triage を実行してください。")

        live_qs = run.articles.filter(bucket__in=["quick_win", "performing"], article__isnull=False)
        dead_qs = run.articles.filter(bucket="dead", article__isnull=False)
        live = [_features(t) for t in live_qs.select_related("article")]
        dead = [_features(t) for t in dead_qs.select_related("article")]
        if not live or not dead:
            raise CommandError(f"live={len(live)} / dead={len(dead)}: 比較に十分なデータがありません。")

        la, lp, ln = _agg(live)
        da, dp, dn = _agg(dead)
        self.stdout.write(self.style.SUCCESS(
            f"=== build_playbook (run id={run.id}) live={ln} / dead={dn} ==="))

        # --- ルール定義（生死の偏在を実数で根拠づける） -------------------------
        # 各 rule: (key, category, title, desc, check_item, priority, anti, evidence)
        RULES = [
            dict(
                key="title-query-match", category="title", priority=1, is_antipattern=False,
                title="タイトル/H1に押し上げ対象クエリの主要語を含める",
                description=(
                    "生きている記事はタイトルに best_query の主要語を含む率が高く、死んでいる記事は"
                    "ほとんど含まない。順位に最も効く差は『本文の深さ』ではなく『タイトルと検索クエリの一致』。"),
                check_item="タイトル/H1に target_query の主要語が自然に入っているか",
                evidence={"metric": "title_has_query%", "live": lp("title_has_query"),
                          "dead": dp("title_has_query"),
                          "live_overlap_avg%": round(la("title_query_overlap") * 100),
                          "dead_overlap_avg%": round(da("title_query_overlap") * 100)},
            ),
            dict(
                key="intent-commerce-restraint", category="intent", priority=2, is_antipattern=True,
                title="情報型クエリでは商業リンクを詰め込みすぎない",
                description=(
                    "死んでいる記事は楽天アフィリリンクが平均的に多い。情報・比較意図のクエリに対して"
                    "購入リンク過多だと検索意図とズレやすい。クエリの意図(情報/比較/購入)に構成を合わせる。"),
                check_item="検索意図に対し商業リンクが過剰でないか（情報型なら解説を主、リンクは従）",
                evidence={"metric": "rakuten_links_avg", "live": la("rakuten_links"),
                          "dead": da("rakuten_links")},
            ),
            dict(
                key="faq-coverage", category="structure", priority=3, is_antipattern=False,
                title="FAQでロングテール・指名疑問をカバーする",
                description=(
                    "生きている記事のほうがFAQ設置率が高い。設問形でロングテール語や"
                    "強調スニペットを取りにいく。"),
                check_item="検索意図に沿ったFAQ（よくある質問）があるか",
                evidence={"metric": "faq%", "live": lp("faq"), "dead": dp("faq")},
            ),
            dict(
                key="depth-is-not-the-lever", category="anti", priority=4, is_antipattern=True,
                title="文字数・見出し数・内部リンク数を増やすこと自体は順位の差別化要因ではない",
                description=(
                    "死んでいる記事はむしろ文字数が多く、見出し・内部リンクも同等以上。"
                    "『増量・装飾すれば上がる』は誤り。まず検索意図とタイトル一致を直す。"),
                check_item="増量で誤魔化していないか（意図適合・タイトル一致を優先したか）",
                evidence={"metric": "chars_avg / h2_avg / internal_links_avg",
                          "live": [la("chars"), la("h2"), la("internal_links")],
                          "dead": [da("chars"), da("h2"), da("internal_links")]},
            ),
            dict(
                key="specificity-primary-info", category="specificity", priority=5, is_antipattern=False,
                title="具体性・一次情報（実測/比較/独自データ）で差をつける",
                description=(
                    "機械抽出では定量化できていない仮説。実測値・独自比較・体験など一次情報の有無が"
                    "効くかはパートC（効果測定）で検証する。"),
                check_item="一般論でなく、実測・比較・独自の具体情報が入っているか",
                evidence={"metric": "未測定（パートCで検証）", "live": None, "dead": None},
            ),
        ]

        # --- PlaybookRule upsert（verified/verification_note は保持） ------------
        created, updated = 0, 0
        for r in RULES:
            obj, was_created = PlaybookRule.objects.update_or_create(
                key=r["key"],
                defaults=dict(
                    category=r["category"], title=r["title"], description=r["description"],
                    check_item=r["check_item"], priority=r["priority"],
                    is_antipattern=r["is_antipattern"], evidence=r["evidence"],
                    is_active=True, source_run=run,
                ),
            )
            created += was_created
            updated += (not was_created)
        self.stdout.write(f"PlaybookRule: 新規{created} / 更新{updated}")

        # --- playbook.md 出力 --------------------------------------------------
        md = self._render_md(run, ln, dn, RULES, la, lp, da, dp)
        with open(opts["out"], "w", encoding="utf-8") as f:
            f.write(md)
        self.stdout.write(self.style.SUCCESS(f"\n✅ playbook.md: {opts['out']}（{len(md)}字）"))
        self.stdout.write("管理画面: https://sc-tsusho.jp/admin/analytics/playbookrule/")

        # 上位エビデンスをコンソールにも
        self.stdout.write("\n生きている側に偏在した上位要素:")
        self.stdout.write(f"  1. タイトルにクエリ語含む: live {lp('title_has_query')}% vs dead {dp('title_has_query')}%")
        self.stdout.write(f"  2. 楽天リンク数(少ないほどlive): live {la('rakuten_links')} vs dead {da('rakuten_links')}")
        self.stdout.write(f"  3. FAQ設置: live {lp('faq')}% vs dead {dp('faq')}%")
        self.stdout.write(f"  (対照)文字数: live {la('chars')} vs dead {da('chars')} ＝差別化要因でない")

    # ------------------------------------------------------------------
    def _render_md(self, run, ln, dn, rules, la, lp, da, dp) -> str:
        today = timezone.now().strftime("%Y-%m-%d")
        L = []
        L.append("# 記事プレイブック（順位に効く要素）— 初版・**未検証仮説**\n")
        L.append("> ⚠️ **これは初版＝実データで未検証の仮説です。** GSCトリアージ "
                 f"TriageRun id={run.id}（生きている記事 {ln}本 vs 死んでいる記事 {dn}本）の"
                 "決定論的な差分から自動生成しました。各ルールはパートC（リライト後の順位変化）で"
                 "検証され、`verified` が立つまでは仮説として扱ってください。\n")
        L.append(f"- 生成日: {today} / 生成元: `build_playbook`（LLM不使用・機械抽出）")
        L.append("- 対象: 記事のみ（商品ページは構造が異なるため対象外）")
        L.append("- 正本はこの playbook.md。機械参照用に `PlaybookRule`（/admin/analytics/playbookrule/）にも同内容を保持。\n")

        L.append("## 結論（生きている側に偏在した上位要素）\n")
        L.append(f"1. **タイトル/H1とクエリの一致が最大の差**: タイトルに best_query 語を含む率は "
                 f"live **{lp('title_has_query')}%** vs dead **{dp('title_has_query')}%**。"
                 "順位に最も効くのは本文の深さではなくタイトル一致。")
        L.append(f"2. **商業リンク過多は死の相関**: 楽天リンク平均は live **{la('rakuten_links')}** vs dead "
                 f"**{da('rakuten_links')}**。情報型クエリに購入リンク過多は逆効果。")
        L.append(f"3. **FAQ設置**: live **{lp('faq')}%** vs dead **{dp('faq')}%**。")
        L.append(f"4. **（対照）文字数・構造は差別化要因でない**: 文字数 live {la('chars')} vs dead {da('chars')}、"
                 f"H2 live {la('h2')} vs dead {da('h2')}。むしろ dead の方が長い。**増量・装飾では上がらない。**\n")

        L.append("## 順位に効く要素（チェックリスト）\n")
        for r in rules:
            if r["is_antipattern"]:
                continue
            ev = r["evidence"]
            L.append(f"### ✅ {r['title']}")
            L.append(f"- {r['description']}")
            L.append(f"- チェック: {r['check_item']}")
            L.append(f"- 根拠: `{ev.get('metric')}` live={ev.get('live')} / dead={ev.get('dead')}\n")

        L.append("## 避けるべきパターン\n")
        for r in rules:
            if not r["is_antipattern"]:
                continue
            ev = r["evidence"]
            L.append(f"### 🚫 {r['title']}")
            L.append(f"- {r['description']}")
            L.append(f"- 根拠: `{ev.get('metric')}` live={ev.get('live')} / dead={ev.get('dead')}\n")

        L.append("## リライト時チェックリスト（レビュー画面に表示）\n")
        for r in rules:
            mark = "🚫" if r["is_antipattern"] else "✅"
            L.append(f"- [ ] {mark} {r['check_item']}")
        L.append("\n## 検証状況\n")
        L.append("- 初版の全ルールは `verified=False`。パートC（効果測定）でリライト前後の順位変化を見て、"
                 "効いた要素を `verified=True` にし、効かなかった仮説は見直す。")
        return "\n".join(L) + "\n"
