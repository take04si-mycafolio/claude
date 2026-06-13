"""記事のNG表現チェックサービス - 公開前の薬機法/景品表示法リスクスキャン"""
import re
from typing import Optional


class ArticleComplianceService:
    """記事のコンプライアンスチェック"""

    CONTEXT_WINDOW = 30

    @classmethod
    def _get_rules(cls):
        from .models import NgExpressionRule
        return list(NgExpressionRule.objects.filter(is_active=True))

    @classmethod
    def check(cls, content: str) -> dict:
        """記事本文をスキャンして違反一覧を返す"""
        if not content:
            return {
                "passed": True, "total_violations": 0,
                "high_count": 0, "medium_count": 0, "low_count": 0,
                "risk_score": 0, "summary_by_category": {}, "violations": [],
            }

        # HTMLタグを除去してプレーンテキストでチェック
        plain = re.sub(r"<[^>]+>", " ", content)
        plain = re.sub(r"\s+", " ", plain)

        rules = cls._get_rules()
        violations = []
        summary = {}

        for rule in rules:
            try:
                if rule.is_regex:
                    regex = re.compile(rule.pattern)
                else:
                    regex = re.compile(re.escape(rule.pattern))
            except re.error:
                continue

            for m in regex.finditer(plain):
                start = max(0, m.start() - cls.CONTEXT_WINDOW)
                end = min(len(plain), m.end() + cls.CONTEXT_WINDOW)
                context = plain[start:end]
                rel_s = m.start() - start
                rel_e = m.end() - start
                context_marked = (
                    context[:rel_s] + "【" + context[rel_s:rel_e] + "】" + context[rel_e:]
                )
                violations.append({
                    "pattern": rule.pattern,
                    "matched_text": m.group(0),
                    "category": rule.risk_category,
                    "category_display": rule.get_risk_category_display(),
                    "severity": rule.severity,
                    "severity_display": rule.get_severity_display(),
                    "reason": rule.reason,
                    "suggestion": rule.suggestion,
                    "context": context_marked,
                    "position": m.start(),
                })
                summary[rule.risk_category] = summary.get(rule.risk_category, 0) + 1

        weight = {"high": 3, "medium": 1, "low": 0.5}
        risk_score = sum(weight.get(v["severity"], 0) for v in violations)
        has_high = any(v["severity"] == "high" for v in violations)
        passed = not has_high

        return {
            "passed": passed,
            "total_violations": len(violations),
            "high_count": sum(1 for v in violations if v["severity"] == "high"),
            "medium_count": sum(1 for v in violations if v["severity"] == "medium"),
            "low_count": sum(1 for v in violations if v["severity"] == "low"),
            "risk_score": risk_score,
            "summary_by_category": summary,
            "violations": violations,
        }

    @classmethod
    def is_publishable(cls, content: str) -> tuple:
        """公開可否判定"""
        result = cls.check(content)
        return result["passed"], result

    @classmethod
    def render_html_report(cls, result: dict) -> str:
        """管理画面用 HTMLレポート"""
        from django.utils.html import escape
        if not result.get("violations"):
            return ('<div style="background:#ECFDF5;color:#047857;padding:14px;border-radius:8px;'
                    'font-weight:700">✓ NG表現は検出されませんでした</div>')
        rows = []
        for v in result["violations"]:
            sev_color = {"high": "#991B1B", "medium": "#B45309", "low": "#1D4ED8"}.get(v["severity"], "#666")
            sev_bg = {"high": "#FEF2F2", "medium": "#FFFBEB", "low": "#EFF6FF"}.get(v["severity"], "#EEE")
            rows.append(
                f'<div style="border-left:4px solid {sev_color};background:{sev_bg};'
                f'padding:10px 14px;margin-bottom:8px;border-radius:0 8px 8px 0">'
                f'<div style="font-size:12px;color:{sev_color};font-weight:700;margin-bottom:4px">'
                f'[{v["severity_display"]}] {v["category_display"]}: {escape(v["pattern"])}</div>'
                f'<div style="font-size:13px;margin-bottom:4px"><strong>該当箇所:</strong> '
                f'…{escape(v["context"])}…</div>'
                f'<div style="font-size:12px;color:#5C5256"><strong>理由:</strong> {escape(v["reason"])}</div>'
                + (f'<div style="font-size:12px;color:#047857"><strong>推奨:</strong> {escape(v["suggestion"])}</div>'
                   if v.get("suggestion") else "")
                + '</div>'
            )
        header_color = "#991B1B" if result["high_count"] > 0 else "#B45309"
        summary_html = " / ".join(f"{k}: {n}" for k, n in result.get("summary_by_category", {}).items())
        header = (
            f'<div style="background:#FEF2F2;border:2px solid {header_color};'
            f'padding:12px;border-radius:8px;margin-bottom:12px">'
            f'<div style="font-weight:700;color:{header_color};margin-bottom:4px">'
            f'⚠ 検出: {result["total_violations"]}件 '
            f'(高 {result["high_count"]} / 中 {result["medium_count"]} / 低 {result["low_count"]})</div>'
            f'<div style="font-size:12px;color:#5C5256">'
            f'リスクスコア: {result["risk_score"]} / 分類: {summary_html}</div>'
            f'<div style="font-size:13px;color:{header_color};margin-top:6px;font-weight:700">'
            f'{"❌ 公開不可(severity=high違反あり)" if not result["passed"] else "⚠ 確認推奨"}</div>'
            f'</div>'
        )
        return header + "".join(rows)

    @classmethod
    def auto_fix(cls, content: str, check_result: Optional[dict] = None) -> tuple:
        """違反箇所を推奨言い換えで自動置換(シンプル版・後方互換用)
        ※AI使用したい場合は rewriter.rewrite_content_with_compliance を使用してください
        """
        if check_result is None:
            check_result = cls.check(content)
        if not check_result["violations"]:
            return content, []

        fixed = content
        fixes_applied = []
        order = {"high": 0, "medium": 1, "low": 2}
        sorted_v = sorted(check_result["violations"], key=lambda v: order.get(v["severity"], 9))

        for v in sorted_v:
            original = v["matched_text"]
            sugg = (v.get("suggestion") or "").strip()
            if not sugg or "削除" in sugg or sugg.startswith("("):
                replacement = ""
            else:
                first = sugg
                for sep in ["\n", "、", "/", "・"]:
                    if sep in first:
                        first = first.split(sep)[0]
                first = first.strip().strip('「」『』 "')[:80]
                replacement = first
            if original and original in fixed:
                fixed = fixed.replace(original, replacement)
                fixes_applied.append({
                    "original": original, "replacement": replacement,
                    "category": v["category"], "severity": v["severity"],
                })
        fixed = re.sub(r"<p>\s*</p>", "", fixed)
        fixed = re.sub(r"  +", " ", fixed)
        return fixed, fixes_applied
