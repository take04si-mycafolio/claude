import logging
import re

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()

logger = logging.getLogger(__name__)


PRODUCT_SHORTCODE_RE = re.compile(
    r'\[product\s+slug="([^"]+)"\](.*?)\[/product\]',
    re.DOTALL,
)

# [card slug="..."] / [card slug="..." label="任意の表示名"]
CARD_SHORTCODE_RE = re.compile(r'\[card\s+slug="([^"]+)"(?:\s+label="([^"]*)")?\]')
# [related slug="a,b,c,d"] (カンマ区切り・最大4本)
RELATED_SHORTCODE_RE = re.compile(r'\[related\s+slug="([^"]+)"\]')


def _stars(n):
    n = int(n) if n else 0
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n)


def _expand_product_shortcodes(html):
    """[product slug="..."]紹介文[/product] -> 商品カードHTMLへ展開"""
    from django.db.models import Avg, Count
    from ..models import Product

    def repl(m):
        slug = m.group(1).strip()
        intro = m.group(2).strip()
        product = Product.objects.filter(slug=slug).first()
        if not product:
            return (
                '<div class="bk-mc-product-card bk-mc-product-card-error">'
                f'⚠ 商品が見つかりません: {slug}</div>'
            )
        review_qs = product.reviews.filter(is_approved=True)
        review_count = review_qs.count()
        reviews_ctx = []
        review_avg = 0
        review_avg_stars = ""
        if review_count > 0:
            avg = review_qs.aggregate(a=Avg("rating"))["a"] or 0
            review_avg = round(float(avg), 1)
            review_avg_stars = _stars(round(avg))
            top = (
                review_qs
                .annotate(helpful_count=Count("helpfuls"))
                .order_by("-rating", "-helpful_count", "-created_at")[:3]
            )
            for r in top:
                reviews_ctx.append({
                    "stars": _stars(r.rating),
                    "rating": r.rating,
                    "title": r.title or "",
                    "body": r.body or "",
                    "skin_type": r.skin_type or "",
                    "usage_period": r.usage_period or "",
                    "helpful_count": r.helpful_count or 0,
                    "created_at": r.created_at,
                })
        return render_to_string(
            "includes/_article_product_card.html",
            {
                "product": product,
                "intro": intro,
                "reviews_ctx": reviews_ctx,
                "review_avg": review_avg,
                "review_avg_stars": review_avg_stars,
                "review_count": review_count,
            },
        )
    return PRODUCT_SHORTCODE_RE.sub(repl, html)


# ---- 内部リンク用ショートコード ([card] / [related]) ----------------------

# 役割判定キーワード (slug / title)。上から順に判定するため優先度が高い順に並べる。
_ROLE_KEYWORDS = (
    ("価格帯別", ("1man", "ika-biganki", "yen", "円以下", "puchipura", "安い", "プチプラ", "1万円")),
    ("おすすめ比較", ("hikaku", "osusume-hikaku", "比較")),
    # 選び方は hub(bigankiki/erabikata) のみ slug 一致で判定。
    # 汎用トークン「選び方」はタイトルに含む機能別/悩み別記事を誤判定するため除外。
    ("選び方", ("erabikata", "bigankiki")),
    ("悩み別", ("tarumi", "keana", "kusumi", "simi", "kaonosiwa",
              "houreisen", "mukimi", "nikibi")),
    # 年代別を機能別より先に判定: 年代別記事はタイトルに機能名(例「RF+EMS」)を
    # 含むことがあり機能別へ誤分類されるが、機能別記事の slug/title に Ndai は出ない。
    ("年代別", ("10dai", "20dai", "30dai", "40dai", "50dai", "60dai")),
    ("機能別", ("ems", "kousyuha", "maikurokaren", "hikari", "sutumu",
              "ion", "tyouonpa", "erekutoro", "reiza", "biganrola", "rora")),
)


def _article_role(article):
    """記事の役割ラベルを slug / title から推定する。"""
    hay = f"{article.slug} {article.title}".lower()
    raw = f"{article.slug} {article.title}"
    for label, kws in _ROLE_KEYWORDS:
        for kw in kws:
            if kw.lower() in hay or kw in raw:
                return label
    return "関連記事"


def _resolve_internal(slug):
    """slug を カテゴリTOP(優先) → 公開Article(fallback) に解決して
    カード描画用の dict を返す。解決できなければ None。"""
    from ..models import Article, Category

    cat = Category.objects.filter(parent__isnull=True, slug=slug).first()
    if cat:
        return {
            "url": f"/{cat.slug}/",
            "title": cat.name,
            "kind": "カテゴリTOP",
            "desc": (cat.meta_description or cat.description or ""),
        }
    a = Article.objects.filter(slug=slug, is_published=True).first()
    if a:
        return {
            "url": a.get_absolute_url(),
            "title": a.title,
            "kind": _article_role(a),
            "desc": (a.meta_description or a.excerpt or ""),
        }
    return None


def _expand_card_shortcodes(html):
    """[card slug="..."] -> ページカードHTMLへ展開"""
    def repl(m):
        slug = m.group(1).strip()
        label = (m.group(2) or "").strip()
        info = _resolve_internal(slug)
        if not info:
            # 未解決slugは [related] と挙動を統一し、空で描画(警告ログのみ)。
            # 先行配線(後続Stepで公開予定の記事カードを未存在のまま挿入)を許容する。
            logger.warning("card shortcode: 未解決slug %r を空で描画", slug)
            return ""
        if label:
            info = {**info, "title": label}
        return render_to_string("includes/_article_page_card.html", {"c": info})
    return CARD_SHORTCODE_RE.sub(repl, html)


def _expand_related_shortcodes(html):
    """[related slug="a,b,c,d"] -> 関連記事ブロックへ展開(最大4本)"""
    def repl(m):
        slugs = [s.strip() for s in m.group(1).split(",") if s.strip()]
        cards = []
        seen = set()
        for s in slugs:
            if s in seen:
                continue
            seen.add(s)
            info = _resolve_internal(s)
            if info:
                cards.append(info)
        cards = cards[:4]
        if not cards:
            return ""
        return render_to_string(
            "includes/_article_related_list.html", {"cards": cards}
        )
    return RELATED_SHORTCODE_RE.sub(repl, html)


def _slugify_anchor(text, used):
    base = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff\s-]", "", text or "")
    base = re.sub(r"\s+", "-", base).strip("-")
    base = base[:40] or "section"
    candidate = base
    i = 1
    while candidate in used:
        i += 1
        candidate = f"{base}-{i}"
    used.add(candidate)
    return candidate


def _process_article(html):
    """h2/h3 に id を付与して目次データを抽出。[toc] ショートコードは除去。"""
    if not html:
        return "", []

    toc_items = []
    used = set()

    def replace_heading(m):
        level = int(m.group(1))
        attrs = m.group(2) or ""
        inner = m.group(3)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        if not plain:
            return m.group(0)
        anchor_id = _slugify_anchor(plain, used)
        toc_items.append({"level": level, "text": plain, "id": anchor_id})
        if re.search(r"\bid\s*=", attrs):
            return m.group(0)
        return f'<h{level}{attrs} id="{anchor_id}">{inner}</h{level}>'

    html = re.sub(
        r"<h([23])((?:\s+[^>]*)?)>(.*?)</h\1>",
        replace_heading,
        html,
        flags=re.DOTALL,
    )

    html = re.sub(r"\s*\[toc\]\s*", "", html, flags=re.IGNORECASE)

    return html, toc_items


def _build_toc_html(toc_items):
    if not toc_items:
        return ""
    out = ['<div class="not-prose">', '<nav class="article-toc" aria-label="目次">']
    out.append("<details open>")
    out.append('<summary><span class="article-toc-mark" aria-hidden="true">≡</span><span class="article-toc-title">目次</span></summary>')
    out.append('<ol class="article-toc-list">')
    for it in toc_items:
        out.append(
            f'<li class="article-toc-item article-toc-l{it["level"]}">'
            f'<a href="#{it["id"]}">{it["text"]}</a>'
            f"</li>"
        )
    out.append("</ol>")
    out.append("</details>")
    out.append("</nav>")
    out.append("</div>")
    return "".join(out)


@register.simple_tag
def render_article(content):
    """記事HTMLを処理。最初の <h2> 直前に「広告 + 目次」を inline 挿入する。
    Usage:
        {% render_article article.content as a %}
        {{ a.html|safe }}
    """
    html, items = _process_article(content or "")
    html = _expand_product_shortcodes(html)
    html = _expand_card_shortcodes(html)
    html = _expand_related_shortcodes(html)
    toc_html = _build_toc_html(items)
    # ファーストビュー広告を「目次の直前」(=最初の<h2>の直前)に再配置
    adsense_html = render_to_string("includes/_adsense.html")
    inject = (adsense_html or "") + (toc_html or "")
    if inject.strip():
        m = re.search(r"<h2\b", html)
        if m:
            pos = m.start()
            html = html[:pos] + inject + html[pos:]
        else:
            html = inject + html
    return {
        "html": mark_safe(html),
        "toc": mark_safe(toc_html),
        "count": len(items),
    }


@register.filter
def yenformat(value):
    """¥カンマ区切り(例: 71000 -> ¥71,000)。空/不正値は空文字。"""
    if value is None or value == "":
        return ""
    try:
        n = int(float(value))
        return f"¥{n:,}"
    except (ValueError, TypeError):
        return str(value)


_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.DOTALL | re.IGNORECASE)


@register.filter
def strip_style_tags(value):
    """<style>...</style> および <script>...</script> ブロックを中身ごと除去する。
    Django組込の striptags は HTMLタグだけ除去するため、<style>内のCSSテキストが
    本文として残ってしまう。構造化データ(JSON-LD)の description などで使う。
    """
    if not value:
        return ""
    s = str(value)
    s = _STYLE_BLOCK_RE.sub("", s)
    s = _SCRIPT_BLOCK_RE.sub("", s)
    return s


@register.simple_tag
def product_jsonld(product, stats=None):
    """Product JSON-LD 構造化データを生成する。

    - description は <style>/<script> ブロック除去後に strip_tags して200字
    - offers は product.price > 0 のとき付与（affiliate_url > rakuten_url > official_url の優先順）
    - aggregateRating は自社stats優先、無ければ api_data.rakuten の reviewCount/reviewAverage にフォールバック
    """
    import json as _json
    from django.utils.html import strip_tags as _strip
    from django.utils.safestring import mark_safe as _safe

    if not product:
        return ""

    # description: <style>/<script> 除去 → HTMLタグ除去 → 200字
    raw_desc = getattr(product, "description", "") or ""
    clean = _STYLE_BLOCK_RE.sub("", raw_desc)
    clean = _SCRIPT_BLOCK_RE.sub("", clean)
    clean = _strip(clean).strip()
    desc = clean[:200].strip()

    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": getattr(product, "name", "") or "",
    }
    if getattr(product, "brand", ""):
        data["brand"] = product.brand
    img = getattr(product, "display_image", None) or getattr(product, "image_url", "")
    if img:
        data["image"] = img
    if desc:
        data["description"] = desc

    # offers
    price = getattr(product, "price", None)
    if price:
        try:
            price_int = int(price)
        except (TypeError, ValueError):
            price_int = 0
        if price_int > 0:
            offer = {
                "@type": "Offer",
                "price": str(price_int),
                "priceCurrency": "JPY",
            }
            url = (
                getattr(product, "affiliate_url", "")
                or getattr(product, "rakuten_url", "")
                or getattr(product, "official_url", "")
                or ""
            ).strip()
            if url:
                offer["url"] = url
            offer["availability"] = (
                "https://schema.org/Discontinued"
                if getattr(product, "is_discontinued", False)
                else "https://schema.org/InStock"
            )
            data["offers"] = offer

    # aggregateRating (自社stats優先 → 楽天APIフォールバック)
    rating = None
    if stats:
        cnt = stats.get("count") if isinstance(stats, dict) else getattr(stats, "count", 0)
        avg = stats.get("average") if isinstance(stats, dict) else getattr(stats, "average", 0)
        if cnt:
            rating = {"@type": "AggregateRating", "ratingValue": str(avg), "reviewCount": str(cnt)}
    if rating is None and isinstance(getattr(product, "api_data", None), dict):
        rk = product.api_data.get("rakuten") or {}
        rc = rk.get("reviewCount") or 0
        ra = rk.get("reviewAverage") or 0
        if rc and ra:
            rating = {"@type": "AggregateRating", "ratingValue": str(ra), "reviewCount": str(rc)}
    if rating:
        data["aggregateRating"] = rating

    # Google Rich Results requires Product schema to include at least one of
    # offers / review / aggregateRating. If none are present (e.g. future product
    # without price registered and no reviews), skip emitting the schema entirely
    # to avoid invalid-structured-data warnings in Search Console.
    if "offers" not in data and "aggregateRating" not in data and "review" not in data:
        return ""

    return _safe(
        '<script type="application/ld+json">'
        + _json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )
