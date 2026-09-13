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
# [survey slug="present-gift"] 利用者アンケート（設問フォーム＋集計結果）
SURVEY_SHORTCODE_RE = re.compile(r'\[survey\s+slug="([^"]+)"\]')


def _stars(n):
    n = int(n) if n else 0
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n)


# 記事内へ抜粋しない口コミ（効能・実感を述べたもの）
_EFFICACY_RE = re.compile(
    r"効[くきいかけ]|効果|実感|浸透|入っていく|入ってい|変化|ハリ|たるみ|しわ|シワ|"
    r"引き締|リフト|小顔|痩せ|美白|くすみ|毛穴が|治|改善|若返"
)
# 抜粋で優先する口コミ（使い勝手に触れたもの）
_USABILITY_RE = re.compile(
    r"重[さいくかっ]|軽[いくさ]|持ちやす|操作|ボタン|モード|充電|電池|コード|"
    r"時間|音[がはも]|静か|ジェル|収納|大きさ|サイズ|使いやす|手入れ|洗"
)


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
            # 記事内へ抜粋する口コミは、効能・実感を述べたものを除外する。
            # 個人の感想であっても、運営者が商品紹介記事に選んで載せると
            # ページ全体として効果を訴求する表示と受け取られうるため（景表法）。
            candidates = list(
                review_qs
                .annotate(helpful_count=Count("helpfuls"))
                .order_by("-rating", "-helpful_count", "-created_at")[:30]
            )
            eligible = [r for r in candidates
                        if not _EFFICACY_RE.search(f"{r.title or ''} {r.body or ''}")]
            # 操作性・重さ・充電など、使い勝手に触れた口コミを優先する
            eligible.sort(key=lambda r: 0 if _USABILITY_RE.search(f"{r.title or ''} {r.body or ''}") else 1)
            top = eligible[:3]
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
                # 評価元。現状は自社(TUSHOU)投稿の集計のみ。外部通販サイトの評価を
                # 導入する場合はここを切り替え、表示ラベルも評価元に追従させる。
                "rating_source": "tushou" if review_avg else "",
                "rating_best": 5.0,
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
    # 統合済み(非公開＋301)の記事を指す [card]/[related] は、統合先の記事で描画する
    dest = _merged_destinations().get(slug)
    if dest:
        return _resolve_internal(dest)
    return None


def _merged_destinations():
    """ARTICLE_MERGES のうち、統合元が非公開になっている(=統合が実行済みの)ものだけ {旧slug: 統合先slug}。

    統合元が公開のままのエントリは「統合先のリライト反映待ちの予約」なので、まだ置き換えない
    (2026-09-14: datsumouki-cool → datsumouki-itami の統合から)。
    """
    from ..article_redirects import ARTICLE_MERGES
    from ..models import Article

    if not ARTICLE_MERGES:
        return {}
    done = set(Article.objects.filter(slug__in=list(ARTICLE_MERGES), is_published=False)
               .values_list("slug", flat=True))
    return {src: dest for src, dest in ARTICLE_MERGES.items() if src in done}


def _apply_merges(content, current_slug=""):
    """統合済み記事(旧slug)への参照を、本文の描画前に統合先へ付け替える。

    内部リンクは「同一リンク先は card/文章中/related の1箇所のみ」がルールなので、単純に置換すると
    統合先へのリンクが重複する(例: 元から itami へのリンクがある記事に cool のカードも残っている)。
    - 統合先への参照が元から本文にある、またはこの記事自身が統合先 → 旧slugへの参照はすべて外す
      (カードと関連記事は消し、文章中のリンクは文字だけ残す)
    - 統合先への参照が無い → 最初の1か所だけ統合先へ付け替え、残りは外す
    """
    merged = _merged_destinations()
    for src, dest in merged.items():
        if src not in content:
            continue
        has_dest = (current_slug == dest
                    or f'href="/{dest}/"' in content
                    or re.search(r'\[card\s+slug="' + re.escape(dest) + r'"', content)
                    or re.search(r'\[related\s+slug="[^"]*\b' + re.escape(dest) + r'\b', content))
        state = {"kept": bool(has_dest)}

        def take():
            if state["kept"]:
                return False
            state["kept"] = True
            return True

        pat = re.compile(
            r'\[card\s+slug="' + re.escape(src) + r'"(?P<label>\s+label="[^"]*")?\]'
            r'|(?P<rel>\[related\s+slug="(?P<slugs>[^"]*)"\])'
            r'|<a\s+href="(?:https://sc-tsusho\.jp)?/' + re.escape(src) + r'/"(?P<attrs>[^>]*)>(?P<text>.*?)</a>',
            re.DOTALL)

        def repl(m):
            if m.group("rel") is not None:
                slugs = [x.strip() for x in m.group("slugs").split(",") if x.strip()]
                if src not in slugs:
                    return m.group(0)
                out = []
                for x in slugs:
                    if x == src:
                        if take():
                            out.append(dest)
                    else:
                        out.append(x)
                return f'[related slug="{",".join(out)}"]' if out else ""
            if m.group("text") is not None:
                if take():
                    return f'<a href="/{dest}/"{m.group("attrs")}>{m.group("text")}</a>'
                return m.group("text")
            if take():
                return f'[card slug="{dest}"{m.group("label") or ""}]'
            return ""

        content = pat.sub(repl, content)
    return content


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
            # 統合元と統合先が両方並んでいると同じ記事が2枚になるので、URLで重複を除く
            if info and info["url"] not in {c["url"] for c in cards}:
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


# 目次のうち、スマホで最初から見せる大見出しの数。
# これを超える項目は「つづきを見る」を押すまで畳む（2026-09-09 ユーザー指示）。
TOC_MOBILE_VISIBLE_H2 = 3


def _build_toc_html(toc_items):
    if not toc_items:
        return ""
    # 初期表示は大見出し(H2)の 01〜03 だけ。4本目以降と、すべての小見出し(H3)は畳む。
    # 番号の並び(01,02,03)が途切れないので、開く前でも記事の骨格が読める。
    h2_seen = 0
    marks = []
    for it in toc_items:
        if it["level"] == 2:
            h2_seen += 1
            marks.append(h2_seen > TOC_MOBILE_VISIBLE_H2)
        else:
            marks.append(True)
    fold_count = sum(marks)

    out = ['<div class="not-prose">', '<nav class="article-toc" aria-label="目次">']
    out.append("<details open>")
    out.append('<summary><span class="article-toc-mark" aria-hidden="true">≡</span><span class="article-toc-title">目次</span></summary>')
    if fold_count:
        # チェックボックス＋labelでJSなしに開閉する。スマホのみ有効（CSS側で制御）
        out.append('<input type="checkbox" id="article-toc-more" '
                   'class="article-toc-more-cb" aria-label="目次の続きを表示">')
    out.append('<ol class="article-toc-list">')
    for it, folded in zip(toc_items, marks):
        cls = f'article-toc-item article-toc-l{it["level"]}'
        if folded:
            cls += " article-toc-fold"
        out.append(f'<li class="{cls}"><a href="#{it["id"]}">{it["text"]}</a></li>')
    out.append("</ol>")
    if fold_count:
        out.append(
            '<label for="article-toc-more" class="article-toc-more">'
            f'<span class="article-toc-more-open">つづきを見る（残り{fold_count}項目）</span>'
            '<span class="article-toc-more-close">目次を閉じる</span>'
            "</label>"
        )
    out.append("</details>")
    out.append("</nav>")
    out.append("</div>")
    return "".join(out)


def _expand_survey_shortcodes(html):
    """[survey slug="..."] -> 利用者アンケート（設問フォーム＋集計）へ展開。

    集計の件数・割合は選択式設問（構造化データ）のみを対象とし、未承認回答も数える。
    自由記述コメントは is_approved のものだけを、回答総数がしきい値以上のときに公開する。
    """
    from apps.surveys.config import get_survey
    from apps.surveys.models import SurveyResponse

    def repl(m):
        slug = m.group(1).strip()
        survey = get_survey(slug)
        if not survey:
            logger.warning("survey shortcode: 未定義slug %r を空で描画", slug)
            return ""

        qs = SurveyResponse.objects.filter(survey_slug=slug, is_deleted=False)
        total = qs.count()
        threshold = survey.get("threshold", 30)
        questions = survey.get("questions", {})

        stats = {}
        for key, q in questions.items():
            # answers(JSON) の該当設問キーごとに選択値を集計（PostgreSQL JSONルックアップ）
            counts = {
                value: qs.filter(**{f"answers__{key}": value}).count()
                for value, _ in q.get("choices", [])
            }
            answered = sum(counts.values())
            rows = [
                {
                    "label": label,
                    "count": counts.get(value, 0),
                    "pct": round(counts.get(value, 0) * 100 / answered) if answered else 0,
                }
                for value, label in q.get("choices", [])
            ]
            stats[key] = {"label": q.get("label", ""), "rows": rows, "answered": answered}

        reasons = []
        if total >= threshold:
            limit = survey.get("reason_display_limit", 8)
            reasons = list(
                qs.filter(is_approved=True).exclude(reason="")
                .order_by("-created_at")
                .values_list("reason", flat=True)[:limit]
            )

        return render_to_string(
            "includes/_survey_block.html",
            {
                "slug": slug,
                "survey": survey,
                "questions": questions,
                "total": total,
                "threshold": threshold,
                "published": total >= threshold,
                "remaining": max(0, threshold - total),
                "stats": stats,
                "reasons": reasons,
            },
        )

    return SURVEY_SHORTCODE_RE.sub(repl, html)


_REVIEW_NOTE_HTML = """
<details class="bk-mc-disclosure">
  <summary>口コミ評価について</summary>
  <div class="bk-mc-disclosure-body">
    <p>TUSHOUに投稿された個人の感想の星評価を単純平均しています。件数・評価は集計日時点の数値です。記事内では個別の口コミ本文は掲載していません。</p>
    <p>購入確認を行っていない口コミを含む場合があります。メーカーや販売事業者から商品の提供を受けた投稿、投稿特典を付与した口コミが含まれる場合は、各口コミ内でその旨を表示します。</p>
    <p>評価の高低を理由に口コミを選別することはありません。<a href="/community-guidelines/">コミュニティガイドライン</a>に違反する投稿や、同一人物による不自然な連続投稿を確認した場合に限り、非掲載または削除の対象とします。</p>
  </div>
</details>
"""

# 記事末尾の注釈ブロック（<div class="bk-mc-notes" id="notes">）の検出
_NOTES_BLOCK_RE = re.compile(r'<div[^>]*class="[^"]*bk-mc-notes[^"]*"[^>]*id="notes"', re.I)


def _inline_review_note(html):
    """「口コミ評価について」を記事末尾の注釈ブロック(#notes)内の最後の折りたたみとして差し込む。

    注釈ブロックが無い記事は (html, False) を返し、テンプレート側が従来どおり本文末尾に出す。
    [related]（あわせて読みたい）より下に単独で出てしまうのを防ぐため、
    注釈は1か所にまとめる。
    """
    m = _NOTES_BLOCK_RE.search(html or "")
    if not m:
        return html, False
    # 注釈ブロック以降の最後の </details> の直後に差し込む（注釈は details の連なり）
    last = html.rfind("</details>")
    if last < m.end():
        return html, False
    pos = last + len("</details>")
    return html[:pos] + _REVIEW_NOTE_HTML + html[pos:], True


@register.simple_tag
def render_article(content, slug=""):
    """記事HTMLを処理。最初の <h2> 直前に「広告 + 目次」を inline 挿入する。
    Usage:
        {% render_article article.content as a %}
        {{ a.html|safe }}
    """
    html, items = _process_article(_apply_merges(content or "", slug))
    html = _expand_product_shortcodes(html)
    html = _expand_card_shortcodes(html)
    html = _expand_related_shortcodes(html)
    html = _expand_survey_shortcodes(html)
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
    has_products = bool(PRODUCT_SHORTCODE_RE.search(content or ""))
    # 「口コミ評価について」は他の注釈と並べる。記事末尾に注釈ブロック（#notes）があれば
    # その中の最後の折りたたみとして差し込む。無い記事はテンプレート側が本文末尾に出す
    # （その場合 review_note_inlined=False）。
    review_note_inlined = False
    if has_products:
        html, review_note_inlined = _inline_review_note(html)
    return {
        "html": mark_safe(html),
        "toc": mark_safe(toc_html),
        "count": len(items),
        # 商品カードを含む記事だけ、口コミ評価の注釈を出す
        "has_products": has_products,
        "review_note_inlined": review_note_inlined,
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
def related_in_body_order(article):
    """Article.related_products を本文の [product slug=] 出現順に並べて返す。
    本文に無い関連商品は末尾にDB既定順で付ける（欠落防止）。"""
    from ..signals import extract_product_slugs
    prods = list(article.related_products.all())
    by_slug = {p.slug: p for p in prods}
    order = extract_product_slugs(getattr(article, "content", "") or "")
    ordered = [by_slug[s] for s in order if s in by_slug]
    ordered += [p for p in prods if p not in ordered]
    return ordered


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

    # aggregateRating は「画面に表示している評価」とのみ一致させる。
    # 表示しているのは自社(TUSHOU)投稿の集計値だけなので、楽天API等の外部評価は
    # 出力しない（画面に無い評価を構造化データだけに出すと Google の
    # 「レビューはページ上で確認できること」に反し、評価元も不明瞭になるため）。
    rating = None
    if stats:
        cnt = stats.get("count") if isinstance(stats, dict) else getattr(stats, "count", 0)
        avg = stats.get("average") if isinstance(stats, dict) else getattr(stats, "average", 0)
        if cnt and avg:
            rating = {
                "@type": "AggregateRating",
                "ratingValue": str(avg),
                "reviewCount": str(cnt),
                "bestRating": "5",
                "worstRating": "1",
            }
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


@register.simple_tag
def spec_table(product):
    """製品タイプのスキーマ(spec_schema)に沿って、値のある項目だけを
    グループ単位で並べた仕様表データを返す。Web/API共通の spec_table_data を使う。

    返り値: [{"group", "rows":[{"key","label","value","unit","is_url"}...]}, ...]
    値が1つも無ければ空list(テンプレ側で非表示)。
    """
    from apps.products import spec_schema as S

    pt = getattr(product, "product_type", None)
    slug = getattr(pt, "slug", None)
    specs = product.specifications if isinstance(product.specifications, dict) else {}
    return S.spec_table_data(slug, specs)


@register.filter
def split_desc_notes(description):
    """商品記事(description)を本文と末尾注記(bk-mc-notes)に分割する。

    商品記事v2(2026-09-07)は「本文 → 購入ボタン(テンプレ) → 注記」の順で
    表示するため、テンプレートが注記だけを購入ボタンの下に回せるようにする。
    注記ブロックが無い記事は notes 空でそのまま表示される。
    """
    text = description or ""
    idx = text.find('<div class="bk-mc-notes"')
    if idx == -1:
        return {"main": text, "notes": ""}
    return {"main": text[:idx], "notes": text[idx:]}
