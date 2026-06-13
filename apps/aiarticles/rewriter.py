"""共通記事リライトサービス - 全記事タイプ対応"""
from typing import Any, Dict, Optional
from .compliance import ArticleComplianceService
from . import seo_quality

PROMPT_TEMPLATE = """あなたは美容家電サイトのSEOライターです。
以下の【元の記事】を、薬機法・景品表示法に完全準拠した形で書き直してください。

【絶対遵守ルール】
1. 下記【NG表現一覧】の単語・表現は絶対に使用禁止。違反したら再生成されます
2. 元記事の見出し構造(<h2>, <h3>)を意味・順番ともに維持
3. 元記事の文字数の70%以上を保つ
4. ターゲットキーワード「{keyword}」を本文に5〜10回自然に含める
5. 出力は HTML(h2/h3/p/ul/li/strong)のみ
6. 説明や前置きは一切不要、HTMLのみを返す
7. {info_constraint}

【NG表現一覧】
{ng_list}

{source_section}

【元の記事】
{original_content}

【書き直した記事】(HTMLのみ):"""


def _build_source_section(product_info=None, source_info=None):
    if product_info:
        section = f"""【商品情報】(これ以外の情報は絶対に追加しない)
商品名: {product_info.get('name', '')}
ブランド: {product_info.get('brand', '')}
公式説明: {(product_info.get('description', '') or '')[:600]}
特徴: {(product_info.get('features', '') or '')[:400]}
注意事項: {(product_info.get('cautions', '') or '')[:400]}"""
        return section, "【商品情報】に書かれていない事実(数値・機能・効果)を絶対に追加しない"
    if source_info:
        return ("【参考情報】\n" + "\n".join(f"{k}: {v}" for k, v in source_info.items()),
                "【参考情報】と元記事に書かれていない事実は絶対に追加しない")
    return "", "元記事に書かれていない事実を絶対に追加しない"


def _build_prompt(content, keyword, product_info, source_info):
    from .models import NgExpressionRule
    ng_rules = NgExpressionRule.objects.filter(is_active=True).order_by("-severity")[:50]
    ng_list = "\n".join(f"・「{r.pattern}」: {r.reason[:80]}" for r in ng_rules)
    section, constraint = _build_source_section(product_info, source_info)
    return PROMPT_TEMPLATE.format(
        keyword=keyword, ng_list=ng_list,
        source_section=section, info_constraint=constraint,
        original_content=content,
    )


def _ai_call(prompt: str, ai_provider: str, ai_model: Optional[str]) -> Optional[str]:
    if ai_provider == "stub":
        return None
    if ai_provider == "anthropic":
        try:
            from anthropic import Anthropic
            from django.conf import settings
            client = Anthropic(api_key=getattr(settings, "ANTHROPIC_API_KEY", ""))
            msg = client.messages.create(
                model=ai_model or "claude-sonnet-4-6",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception:
            return None
    if ai_provider == "openai":
        try:
            from openai import OpenAI
            from django.conf import settings
            client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", ""))
            res = client.chat.completions.create(
                model=ai_model or "gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000,
            )
            return res.choices[0].message.content.strip()
        except Exception:
            return None
    return None


def rewrite_content_with_compliance(
    content, keyword, product_info=None, source_info=None,
    ai_provider="anthropic", ai_model=None,
    max_attempts=3, min_seo_ratio=0.7,
    keyword_min=5, keyword_max=10,
) -> Dict[str, Any]:
    """共通リライト。保存は呼出側で。"""
    original_metrics = seo_quality.analyze_seo_metrics(content, keyword)
    history = []
    for attempt in range(1, max_attempts + 1):
        prompt = _build_prompt(content, keyword, product_info, source_info)
        rewritten = seo_quality.clean_ai_output(_ai_call(prompt, ai_provider, ai_model))
        log = {"attempt": attempt}
        if not rewritten:
            log["error"] = "AIから出力なし"; history.append(log); continue
        compliance = ArticleComplianceService.check(rewritten)
        log["violations"] = compliance["total_violations"]
        log["high"] = compliance["high_count"]
        if not compliance["passed"]:
            log["reject_reason"] = "コンプラ違反"; history.append(log); continue
        new_metrics = seo_quality.analyze_seo_metrics(rewritten, keyword)
        seo = seo_quality.compare_seo_metrics(
            original_metrics, new_metrics,
            min_ratio=min_seo_ratio, keyword_min=keyword_min, keyword_max=keyword_max,
        )
        log["seo"] = seo; history.append(log)
        if not seo["acceptable"]:
            continue
        return {
            "success": True, "rewritten_content": rewritten,
            "compliance_check": compliance, "seo_check": seo, "history": history,
        }
    return {
        "success": False, "rewritten_content": None,
        "compliance_check": ArticleComplianceService.check(content),
        "seo_check": next((h.get("seo") for h in reversed(history) if h.get("seo")), None),
        "history": history,
    }


def rewrite_product_article(pa, ai_provider="anthropic", ai_model=None, max_attempts=3):
    """ProductArticle ラッパー: リライト + 保存 + 監査ログ"""
    from .models import ArticleGenerationLog
    product_info = {
        "name": pa.product.name, "brand": pa.product.brand,
        "description": pa.product.description, "features": pa.product.features,
        "cautions": getattr(pa.product, "cautions", ""),
    }
    result = rewrite_content_with_compliance(
        content=pa.content, keyword=pa.keyword,
        product_info=product_info,
        ai_provider=ai_provider, ai_model=ai_model, max_attempts=max_attempts,
    )
    if result["success"]:
        pa.content = result["rewritten_content"]
        pa.yakkihou_check = result["compliance_check"]
        pa.yakkihou_passed = True
        pa.seo_check_result = result["seo_check"]
        pa.status = "pending_review"
    else:
        pa.seo_check_result = result["seo_check"] or {"failed": True, "history": result["history"]}
        pa.status = "human_review_required"
    pa.save()
    ArticleGenerationLog.objects.create(
        article=pa, product=pa.product, keyword=pa.keyword,
        source_snapshot={"type": "rewrite_product_article", "history": result["history"]},
        prompt_template="common_rewriter_v1",
        ai_provider=ai_provider, ai_model=ai_model or "",
        parsed_content=result["rewritten_content"] or "",
        success=result["success"],
        error_message="" if result["success"] else "全試行失敗",
        yakkihou_check_log=result["compliance_check"],
    )
    return result


def rewrite_article(article, keyword=None, ai_provider="anthropic", ai_model=None, max_attempts=3):
    """products.Article ラッパー"""
    if not keyword:
        keyword = getattr(article, "seo_keyword", "") or article.title[:30]
    source_info = {}
    try:
        related = list(article.related_products.all()[:3])
        if related:
            source_info["関連商品"] = ", ".join(p.name for p in related)
    except Exception:
        pass
    if getattr(article, "product_type", None):
        source_info["カテゴリ"] = article.product_type.name
    result = rewrite_content_with_compliance(
        content=article.content, keyword=keyword,
        source_info=source_info if source_info else None,
        ai_provider=ai_provider, ai_model=ai_model, max_attempts=max_attempts,
    )
    if result["success"]:
        article.content = result["rewritten_content"]
        if hasattr(article, "seo_check_result"):
            article.seo_check_result = result["seo_check"]
        article.save()
    return result


def check_content(content: str, keyword: Optional[str] = None) -> Dict[str, Any]:
    """純粋なチェックのみ(リライトなし)"""
    compliance = ArticleComplianceService.check(content)
    seo = seo_quality.analyze_seo_metrics(content, keyword or "") if keyword else None
    return {"compliance_check": compliance, "seo_metrics": seo}
