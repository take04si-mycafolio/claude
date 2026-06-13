"""
AI記事生成サービス。

【最重要】
DBに保存された商品情報のみを唯一のソースとし、AIが勝手に補完できないように
プロンプトと検証で2重に縛る。
"""
import json
import time
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from apps.products.models import Product, Article
from apps.reviews.models import Review
from .models import ArticleGenerationLog, ProductArticle


PROMPT_TEMPLATE = """あなたは美容家電サイトのSEOライターです。
以下の【商品情報】のみに基づいて、ターゲットキーワード「{keyword}」で
日本人ユーザー向けのSEO記事(2000〜3500文字)を執筆してください。

【最重要ルール】
1. 【商品情報】に書かれていない事実(数値・機能・効果)を絶対に追加しないこと
2. 推測・想像・他社製品の比較を含めないこと
3. 効果効能の断定的表現は薬機法違反の恐れあり、避けること
4. 出力は HTML(h2/h3/p/ul/li/strong)のみ。<script>等は禁止
5. 必ず以下の構成で書く:
   - リード文(キーワードを含む冒頭150文字)
   - <h2>商品概要</h2>
   - <h2>主な機能</h2>
   - <h2>こんな方におすすめ</h2>
   - <h2>使用上の注意</h2> (cautionsがあれば必ず記載)
   - <h2>まとめ</h2>

【商品情報】(これ以外の情報は使用禁止)
商品名: {name}
ブランド: {brand}
カテゴリ: {category}
参考価格: {price_text}
公式説明: {description}
主な機能: {features}
スペック: {specifications}
注意事項: {cautions}
公式URL: {official_url}
情報最終確認日: {last_verified_at}

{review_section}

出力形式: JSONで以下のキーを返してください
{{
  "title": "記事タイトル(60〜70文字、キーワード必須)",
  "excerpt": "記事の抜粋(120〜160文字、メタディスクリプション用)",
  "content": "本文HTML"
}}
"""

# 薬機法NGワード(簡易チェック用)
YAKKIHOU_NG_PATTERNS = [
    "完全に治る", "必ず効く", "病気が治る", "副作用なし",
    "100%安全", "がんが治る", "アンチエイジング効果", "若返り効果",
    "シミが消える", "シワが消える", "薄毛が治る",
]


def build_source_snapshot(product: Product) -> dict:
    """商品情報のスナップショット(後から検証可能)"""
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.product_type.name if product.product_type else None,
        "price": product.price,
        "description": product.description,
        "features": product.features,
        "specifications": product.specifications,
        "cautions": product.cautions,
        "official_url": product.official_url,
        "last_verified_at": str(product.last_verified_at) if product.last_verified_at else None,
        "categories": list(product.categories.values_list("name", flat=True)),
        "snapshot_at": timezone.now().isoformat(),
    }


def build_review_section(product: Product, max_reviews: int = 5) -> str:
    """ユーザーレビューを引用可能な形でフォーマット(任意)"""
    reviews = Review.objects.filter(
        product=product, is_approved=True
    ).order_by("-created_at")[:max_reviews]
    if not reviews:
        return "ユーザーレビュー: なし(レビュー情報を記事に含めない)"
    lines = ["ユーザーレビュー(これも【商品情報】の一部、これ以外は禁止):"]
    for r in reviews:
        lines.append(f"- ★{r.rating} 「{r.title}」: {r.body[:200]}")
    return "\n".join(lines)


def build_prompt(product: Product, keyword: str) -> str:
    """プロンプトを組み立て"""
    return PROMPT_TEMPLATE.format(
        keyword=keyword,
        name=product.name or "(未設定)",
        brand=product.brand or "(未設定)",
        category=product.product_type.name if product.product_type else "(未設定)",
        price_text=f"¥{product.price:,}" if product.price else "(価格情報なし)",
        description=product.description or "(公式説明なし)",
        features=product.features or "(主な機能の記載なし)",
        specifications=json.dumps(product.specifications, ensure_ascii=False) if product.specifications else "(スペック情報なし)",
        cautions=product.cautions or "(注意事項の記載なし)",
        official_url=product.official_url or "(公式URLなし)",
        last_verified_at=product.last_verified_at or "(未確認)",
        review_section=build_review_section(product),
    )


def yakkihou_check(text: str) -> dict:
    """簡易薬機法チェック"""
    violations = []
    warnings = []
    for pattern in YAKKIHOU_NG_PATTERNS:
        if pattern in text:
            violations.append(pattern)
    # 「効果」のような単語は警告のみ(文脈依存)
    if "効果" in text and "個人差" not in text:
        warnings.append("「効果」を断定的に使う場合は「個人差があります」等の付記推奨")
    return {
        "violations": violations,
        "warnings": warnings,
        "ok": len(violations) == 0,
    }


def hallucination_check(content: str, snapshot: dict) -> dict:
    """ハルシネーション(DB外の情報混入)の簡易検査
    商品情報に存在しない数値・固有名詞が含まれていないか軽くチェック
    """
    issues = []
    # ブランド以外のメーカー名が出てきていないか(よくあるブランド名チェック)
    other_brands = ["ヤーマン", "パナソニック", "ダイソン", "リファ", "MTG", "コイズミ",
                    "シャープ", "ブラウン", "テスコム", "ケラスターゼ"]
    snapshot_text = json.dumps(snapshot, ensure_ascii=False)
    for brand in other_brands:
        if brand in content and brand not in snapshot_text:
            issues.append(f"商品情報外のブランド言及: {brand}")
    return {
        "issues": issues,
        "ok": len(issues) == 0,
    }


def generate_article(
    product: Product, keyword: str,
    ai_provider: str = "stub",
    ai_model: str = "stub-v1",
    user=None,
) -> ProductArticle:
    """
    記事生成のメインエントリ。

    現状はスタブ実装(プロンプト構築 + 検証フローまで)。
    実AI呼び出しは ai_provider に応じて差し替え可能(anthropic/openai等)。
    """
    snapshot = build_source_snapshot(product)
    prompt = build_prompt(product, keyword)
    started = time.time()

    # ProductArticle のレコード作成(下書き状態)
    pa = ProductArticle.objects.create(
        product=product,
        keyword=keyword,
        title=f"[要編集] {product.name} - {keyword}",
        content="<p>(AI生成失敗または未実行)</p>",
        status="draft",
        ai_generated_at=timezone.now(),
    )

    # ===== AI呼び出し(スタブ) =====
    # 実装時はここで anthropic.messages.create / openai.chat.completions.create 等
    raw_output = ""
    parsed_title = ""
    parsed_content = ""
    success = False
    error_message = ""

    if ai_provider == "stub":
        # スタブ: プロンプトを返すだけ(動作確認用)
        raw_output = json.dumps({
            "title": f"[STUB] {product.name}の{keyword}解説",
            "excerpt": f"スタブ生成: {keyword} に関する{product.name}の情報",
            "content": f"<h2>商品概要</h2><p>{product.name}({product.brand})は…(本実装でAI出力に置換)</p>"
                       f"<h2>注意事項</h2><p>{product.cautions or '(注意事項なし)'}</p>",
        }, ensure_ascii=False)
        try:
            data = json.loads(raw_output)
            parsed_title = data.get("title", "")
            parsed_content = data.get("content", "")
            pa.title = parsed_title
            pa.content = parsed_content
            pa.excerpt = data.get("excerpt", "")
            success = True
        except Exception as e:
            error_message = str(e)
    else:
        error_message = f"AIプロバイダ '{ai_provider}' は未実装"

    duration_ms = int((time.time() - started) * 1000)

    # 品質チェック
    yk = yakkihou_check(parsed_content)
    hc = hallucination_check(parsed_content, snapshot)

    pa.yakkihou_check = yk
    pa.yakkihou_passed = yk["ok"]
    pa.status = "pending_review" if (success and yk["ok"] and hc["ok"]) else "draft"
    pa.save()

    # 監査ログ
    ArticleGenerationLog.objects.create(
        article=pa,
        product=product,
        keyword=keyword,
        source_snapshot=snapshot,
        prompt_template="default_v1",
        full_prompt=prompt,
        ai_provider=ai_provider,
        ai_model=ai_model,
        raw_output=raw_output,
        parsed_title=parsed_title,
        parsed_content=parsed_content,
        duration_ms=duration_ms,
        hallucination_check=hc,
        yakkihou_check_log=yk,
        success=success,
        error_message=error_message,
    )
    return pa


def publish_article(product_article: ProductArticle, user=None) -> Article:
    """承認済AI記事を 公開Article(products.Article)に登録"""
    if product_article.status != "approved":
        raise ValueError(f"承認済(approved)以外は公開できません(現在: {product_article.status})")
    from django.utils.text import slugify
    base_slug = slugify(product_article.title, allow_unicode=True)[:80]
    slug = base_slug
    n = 1
    while Article.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base_slug}-{n}"
    article = Article.objects.create(
        title=product_article.title,
        slug=slug,
        content=product_article.content,
        excerpt=product_article.excerpt,
        product_type=product_article.product.product_type,
        is_published=True,
        published_at=timezone.now(),
    )
    article.related_products.add(product_article.product)
    product_article.published_article = article
    product_article.status = "published"
    product_article.save(update_fields=["published_article", "status"])
    return article


# === 共通サービスへの移行 (re-export) ===
# これより上の inline 関数はオーバーライドされる
from .seo_quality import (
    analyze_seo_metrics,
    compare_seo_metrics,
    compare_h2_structure,
    clean_ai_output as _clean_ai_output,
)
from .rewriter import rewrite_product_article, rewrite_content_with_compliance


def rewrite_full_article(pa, ai_provider="anthropic", ai_model=None, max_attempts=3, min_seo_ratio=0.7):
    """後方互換ラッパー: rewriter.rewrite_product_article を呼ぶだけ"""
    return rewrite_product_article(pa, ai_provider=ai_provider, ai_model=ai_model, max_attempts=max_attempts)
