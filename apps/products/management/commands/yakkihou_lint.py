"""
薬機法・景表法 表現リンタ（Django management command）

配置先: <your_app>/management/commands/yakkihou_lint.py
        ↑ <your_app> は記事を管理しているDjangoアプリ名（例: articles）

使い方:
  python manage.py yakkihou_lint                            # 全記事スキャン（テキスト出力）
  python manage.py yakkihou_lint --slug=ems                 # 特定記事のみ
  python manage.py yakkihou_lint --output=markdown          # Markdown形式
  python manage.py yakkihou_lint --output=json --save=/opt/claude-ops/reports/lint_$(date +%Y%m%d).json
  python manage.py yakkihou_lint --severity=CRITICAL        # 重大違反だけ抽出

検出カテゴリ:
  CRITICAL : 医療的効能・身体作用への直接的言及（薬機法違反リスク：高）
  HIGH     : 断定的効能表現
  KEIHYO   : 景表法・優良誤認（最大級表現）
  SAFETY   : 安全性の断定
"""

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

# ⚠️ 環境に合わせて変更してください
# 記事モデルが articles.models.Article でない場合はインポート先を修正
from apps.products.models import Article  # noqa


# =============================================================================
# ルール定義
# =============================================================================

RULES = {
    "CRITICAL": {
        "description": "医療的効能・身体作用への直接的言及（薬機法違反リスク：高）",
        "patterns": [
            (r"コラーゲン.{0,15}(?:生成|再生|産生|形成|促|増[加殖]|活性)", "コラーゲン生成・促進"),
            (r"(?:真皮|表皮基底|皮下)層?.{0,5}(?:届|到達|浸透|作用|アプローチ)", "皮膚深部への作用"),
            (r"細胞.{0,5}活性[化]?", "細胞活性化"),
            (r"線維芽細胞.{0,10}(?:活性|刺激|増殖|促進)", "線維芽細胞への作用"),
            (r"(?:シミ|シワ|たるみ|ほうれい線).{0,10}(?:消[えす]|なくな|改善する|治[るす])", "症状改善の断定"),
            (r"肌.{0,5}(?:若返|蘇生|再生)", "若返り表現"),
            (r"血行.{0,5}(?:促進|改善)(?!.{0,5}と[言い])", "血行促進の断定"),
            (r"代謝.{0,5}(?:アップ|促進|向上)(?!.{0,5}と[言い])", "代謝への作用"),
            (r"アンチエイジング(?:効果|作用)", "アンチエイジング効果"),
            (r"治[るす療癒]", "治癒・治療表現"),
            (r"リフトアップ(?:し[まて]す|されます|効果)", "リフトアップ効果の断定"),
            (r"(?:筋肉|表情筋).{0,10}(?:引き上げ|鍛え|刺激し)ます", "筋肉作用の断定"),
        ],
    },
    "HIGH": {
        "description": "断定的効能表現（薬機法違反リスク：中〜高）",
        "patterns": [
            (r"(?<![とや言])効果(?:が|を)あ[るり]", "効果がある"),
            (r"効[くき]ま?す[よね。！]", "効きます"),
            (r"確実に", "確実に"),
            (r"必ず.{0,10}(?:効|変|改善|なる)", "必ず〜"),
            (r"短期間で.{0,10}(?:結果|効果|変化)", "短期間で〜"),
            (r"(?:1週間|2週間|1ヶ月).{0,15}(?:で|に).{0,10}(?:効|結果|変化|なる)", "期間限定の効果保証"),
            (r"医学的に(?:証明|実証|認め)", "医学的根拠の主張"),
            (r"臨床(?:試験|実験)で(?:証明|実証)", "臨床試験の主張"),
        ],
    },
    "KEIHYO": {
        "description": "景表法・優良誤認の恐れ（最大級表現）",
        "patterns": [
            (r"最強(?!レベル)", "最強"),
            (r"業界最[高大強安]", "業界最〜"),
            (r"日本一", "日本一"),
            (r"No\.?\s*[1１]", "No.1"),
            (r"ナンバーワン", "ナンバーワン"),
            (r"完全に(?!.{0,3}は)", "完全に"),
            (r"絶対(?:に)?(?![にだと])", "絶対"),
            (r"唯一無二", "唯一無二"),
            (r"圧倒的(?:な)?(?:効|結果|実感)", "圧倒的な効果"),
        ],
    },
    "SAFETY": {
        "description": "安全性の断定（薬機法違反リスク）",
        "patterns": [
            (r"副作用(?:は)?(?:ない|なし|ありません)", "副作用なし"),
            (r"100%安全", "100%安全"),
            (r"誰でも(?:必ず|安心|安全)", "誰でも安心"),
            (r"刺激が(?:ない|なし)", "刺激なし断定"),
        ],
    },
}


# =============================================================================
# Django Management Command
# =============================================================================


class Command(BaseCommand):
    help = "記事本文の薬機法・景表法表現をスキャンする"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="特定スラッグのみスキャン")
        parser.add_argument(
            "--output",
            choices=["text", "json", "markdown"],
            default="text",
            help="出力形式",
        )
        parser.add_argument(
            "--severity",
            choices=["CRITICAL", "HIGH", "KEIHYO", "SAFETY", "ALL"],
            default="ALL",
            help="絞り込むカテゴリ",
        )
        parser.add_argument("--save", type=str, help="レポート保存先パス")
        parser.add_argument(
            "--published-only",
            action="store_true",
            help="公開済み記事のみ対象（is_published=True）",
        )

    def handle(self, *args, **opts):
        qs = Article.objects.all()
        if opts["slug"]:
            qs = qs.filter(slug=opts["slug"])
        if opts["published_only"]:
            # ⚠️ フィールド名は環境に合わせて調整
            qs = qs.filter(is_published=True)

        results = []
        scanned = 0
        for article in qs.iterator():
            scanned += 1
            findings = self.scan_article(article, opts["severity"])
            if findings:
                results.append(
                    {
                        "slug": article.slug,
                        "title": article.title,
                        "findings_count": len(findings),
                        "critical_count": sum(1 for f in findings if f["severity"] == "CRITICAL"),
                        "findings": findings,
                    }
                )

        # サマリ
        summary = {
            "scanned_articles": scanned,
            "articles_with_violations": len(results),
            "total_findings": sum(r["findings_count"] for r in results),
            "by_severity": self._severity_breakdown(results),
        }

        output = self.format(results, summary, opts["output"])

        if opts["save"]:
            Path(opts["save"]).parent.mkdir(parents=True, exist_ok=True)
            Path(opts["save"]).write_text(output, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"💾 保存しました: {opts['save']}"))
            self.stdout.write(
                self.style.WARNING(
                    f"スキャン {scanned}件 / 違反 {len(results)}件 / 検出数 {summary['total_findings']}"
                )
            )
        else:
            self.stdout.write(output)

    def scan_article(self, article, severity_filter):
        # ⚠️ contentフィールド名は環境に合わせて調整（body, content, html等）
        raw_content = getattr(article, "content", None) or getattr(article, "body", "")
        text = strip_tags(raw_content or "")

        findings = []
        for severity, rule_set in RULES.items():
            if severity_filter != "ALL" and severity_filter != severity:
                continue
            for pattern, label in rule_set["patterns"]:
                for m in re.finditer(pattern, text):
                    start = max(0, m.start() - 30)
                    end = min(len(text), m.end() + 30)
                    findings.append(
                        {
                            "severity": severity,
                            "label": label,
                            "match": m.group(),
                            "context": text[start:end].replace("\n", " ").strip(),
                            "position": m.start(),
                        }
                    )
        return findings

    def _severity_breakdown(self, results):
        breakdown = {"CRITICAL": 0, "HIGH": 0, "KEIHYO": 0, "SAFETY": 0}
        for r in results:
            for f in r["findings"]:
                breakdown[f["severity"]] += 1
        return breakdown

    def format(self, results, summary, fmt):
        if fmt == "json":
            return json.dumps(
                {"summary": summary, "articles": results}, ensure_ascii=False, indent=2
            )

        if fmt == "markdown":
            lines = [
                "# 薬機法・景表法 リントレポート",
                "",
                "## サマリ",
                f"- スキャン記事数: {summary['scanned_articles']}",
                f"- 違反あり記事: {summary['articles_with_violations']}",
                f"- 検出総数: {summary['total_findings']}",
                f"- 内訳: CRITICAL {summary['by_severity']['CRITICAL']} / "
                f"HIGH {summary['by_severity']['HIGH']} / "
                f"KEIHYO {summary['by_severity']['KEIHYO']} / "
                f"SAFETY {summary['by_severity']['SAFETY']}",
                "",
                "---",
                "",
            ]
            # CRITICAL多い順にソート
            for r in sorted(results, key=lambda x: -x["critical_count"]):
                lines.append(f"## {r['title']} (`{r['slug']}`)")
                lines.append(f"検出数: {r['findings_count']} (CRITICAL {r['critical_count']})")
                lines.append("")
                for f in r["findings"]:
                    lines.append(f"- **[{f['severity']}]** {f['label']}: `{f['match']}`")
                    lines.append(f"  - 文脈: …{f['context']}…")
                lines.append("")
            return "\n".join(lines)

        # text
        if not results:
            return "✅ 違反表現は検出されませんでした"
        out = [
            f"スキャン {summary['scanned_articles']}件 / 違反 {summary['articles_with_violations']}件",
            f"内訳: CRITICAL {summary['by_severity']['CRITICAL']} / "
            f"HIGH {summary['by_severity']['HIGH']} / "
            f"KEIHYO {summary['by_severity']['KEIHYO']} / "
            f"SAFETY {summary['by_severity']['SAFETY']}",
            "=" * 60,
        ]
        for r in sorted(results, key=lambda x: -x["critical_count"]):
            out.append(f"\n■ {r['title']} ({r['slug']}) - {r['findings_count']}件")
            for f in r["findings"]:
                out.append(f"  [{f['severity']}] {f['label']}: 「{f['match']}」")
                out.append(f"    …{f['context']}…")
        return "\n".join(out)
