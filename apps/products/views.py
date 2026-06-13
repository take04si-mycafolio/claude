from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Bookmark
from .models import Article, Category, Product


def _product_types():
    """ヘッダー表示用 (show_in_header=True のみ)"""
    return Category.objects.filter(
        parent__isnull=True, show_in_header=True
    ).order_by("sort_order", "name")


def _annotate(qs):
    return qs.annotate(
        avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        review_count=Count("reviews", filter=Q(reviews__is_approved=True)),
    )


def list_view(request):
    """TOPページ。検索/絞込パラメータがあれば商品一覧、無ければSEOホーム"""
    q = request.GET.get("q", "").strip()
    type_slug = request.GET.get("type", "").strip()
    function_slug = request.GET.get("category", "").strip()

    if q or type_slug or function_slug:
        # 検索/絞込結果モード
        products = _annotate(
            Product.objects.filter(is_published=True).prefetch_related("categories", "product_type")
        )
        active_type = None
        if type_slug:
            active_type = Category.objects.filter(slug=type_slug, parent__isnull=True).first()
            if active_type:
                products = products.filter(product_type=active_type)
        if function_slug:
            products = products.filter(categories__slug=function_slug)
        if q:
            products = products.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q))
        functions = []
        if active_type:
            functions = Category.objects.filter(parent=active_type).order_by("sort_order", "name")
        return render(request, "products/product_list.html", {
            "products": products.distinct(),
            "product_types": _product_types(),
            "active_type": active_type,
            "functions": functions,
            "active_function": function_slug,
            "q": q,
        })

    # SEO TOPページモード
    types = Category.objects.filter(parent__isnull=True, show_in_header=True).order_by("sort_order", "name")
    types_with_top = []
    for t in types:
        top = list(_annotate(
            Product.objects.filter(is_published=True, product_type=t)
        ).order_by("-avg_rating", "sort_order")[:4])
        if top:
            types_with_top.append((t, top))

    top_products = _annotate(
        Product.objects.filter(is_published=True)
    ).exclude(avg_rating__isnull=True).order_by("-avg_rating", "sort_order")[:4]

    recent_articles = Article.objects.filter(is_published=True).select_related("product_type").order_by("-published_at", "-created_at")[:21]

    # サイト統計
    from apps.reviews.models import Review
    review_total = Review.objects.filter(is_approved=True).count()
    product_total = Product.objects.filter(is_published=True).count()
    article_total = Article.objects.filter(is_published=True).count()

    return render(request, "products/home.html", {
        "types_with_top": types_with_top,
        "top_products": top_products,
        "recent_articles": recent_articles,
        "stats": {"reviews": review_total, "products": product_total, "articles": article_total},
        "product_types": _product_types(),
    })


# --- 機構ラベル (CSV) を起動時に1回ロードしてキャッシュ ---------------------
_MECH_CSV = "/opt/claude-ops/reports/biganki_product_mapping_20260604.csv"
_MECH_MAP = None  # {slug: 正規化機構トークン}

# 兄弟機構 (Phase 3b 運用ルール: RF↔EMS↔マイクロ, スチーマー↔イオン↔超音波, LED↔レーザー 等)
_SIBLINGS = {
    "RF": {"EMS", "マイクロカレント", "複合"},
    "EMS": {"RF", "マイクロカレント", "複合"},
    "マイクロカレント": {"RF", "EMS", "複合", "ローラー"},
    "スチーマー": {"イオン導入", "超音波"},
    "イオン導入": {"スチーマー", "超音波"},
    "超音波": {"イオン導入", "スチーマー"},
    "LED・光": {"レーザー"},
    "レーザー": {"LED・光"},
    "複合": {"RF", "EMS", "複合"},
    "ローラー": {"マイクロカレント"},
}


def _norm_mech(label):
    """CSV の機構ラベルを正規化トークンへ ('無判定→手動(..)'→'無判定', 'ローラー(..)'→'ローラー')。"""
    if not label:
        return ""
    return label.split("→")[0].split("(")[0].strip()


def _mech_map():
    global _MECH_MAP
    if _MECH_MAP is None:
        import csv as _csv
        m = {}
        try:
            with open(_MECH_CSV, encoding="utf-8") as f:
                for r in _csv.DictReader(f):
                    m[r["slug"]] = _norm_mech(r.get("機構ラベル", ""))
        except (OSError, KeyError):
            pass  # CSV 不在カテゴリは機構シグナルなし→人気度+キャップ多様化のみ
        _MECH_MAP = m
    return _MECH_MAP


# product_type ごとの similar-products 割当をワーカー寿命で1回だけ計算しキャッシュ。
# グローバル出現キャップ + 決定論選出 (slug 昇順) のため per-call では計算不可。
# 商品/口コミ更新の反映は collectstatic→HUP (ワーカー再起動) 時。
_SIMILAR_ASSIGNMENT = {}  # {product_type_id: {product_id: [Product, ...6]}}


def _build_similar_assignment(product_type):
    import math
    from django.db.models import Avg, Count, Q

    mech = _mech_map()
    # ページ = 公開全商品 (終売ページにも similar を描画)。候補 = 公開かつ非終売 (買えない商品は勧めない)。
    base = (
        Product.objects.filter(is_published=True, product_type=product_type)
        .annotate(
            review_count=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        )
    )
    pages = sorted(base, key=lambda p: p.slug or "")
    candidates = [p for p in pages if not p.is_discontinued]
    n_pool = max(len(candidates), 1)
    cap = math.ceil(len(pages) * 6 / n_pool) + 1

    used = {}  # slug -> グローバル出現回数
    assignment = {}
    for page in pages:
        tm = mech.get(page.slug, "")
        scored = []
        for q in candidates:
            if q.id == page.id or used.get(q.slug, 0) >= cap:
                continue
            s = 0.0
            qm = mech.get(q.slug, "")
            if qm and qm == tm:
                s += 3.0            # 同一機構
            elif qm in _SIBLINGS.get(tm, ()):  # noqa: cellvar — tm はループ毎に再束縛
                s += 1.0            # 兄弟機構
            s += math.log1p(q.review_count) * 0.2  # 人気度は弱い再ランクのみ
            if page.brand and q.brand == page.brand:
                s += 0.5
            scored.append((-s, q.slug or "", q))  # 決定論タイブレーク=slug昇順
        scored.sort(key=lambda t: (t[0], t[1]))
        picked = [q for _, _, q in scored[:6]]
        for q in picked:
            used[q.slug] = used.get(q.slug, 0) + 1
        assignment[page.id] = picked
    return assignment


def _similar_products_for(product, limit=6):
    """SEO 内部リンク用 代替品候補 (Phase 3b 偏り対策 = 機構関連 + グローバルキャップ多様化)。

    候補母集団: is_published=True ∧ is_discontinued=False ∧ 同 product_type (口コミ件数フィルタは撤廃)。
    スコア: 同一機構 +3.0 / 兄弟機構 +1.0 (CSV機構ラベル) ＋ log(口コミ+1)×0.2 ＋ 同ブランド +0.5。
    グローバル出現キャップ ceil(slots/pool)+1 で勝者総取りを抑制。slug 昇順の決定論選出 (乱数なし)。
    機構ラベル CSV の無いカテゴリ(脱毛器/ドライヤー等)は人気度+キャップ多様化のみで動作。
    """
    if not product.product_type_id:
        return []
    ptid = product.product_type_id
    if ptid not in _SIMILAR_ASSIGNMENT:
        _SIMILAR_ASSIGNMENT[ptid] = _build_similar_assignment(product.product_type)
    return _SIMILAR_ASSIGNMENT[ptid].get(product.id, [])[:limit]


def _ranking_queryset(ptype):
    """カテゴリ商品をランキングスコア順で返す (口コミ投稿者特典のランキング用)。

    スコア式:
        bayesian_avg = (n*R + m*C) / (n + m)
            n: 承認済み口コミ件数
            R: 商品の平均評価
            m: 信頼度しきい値 = 5 (5件までは事前分布に引き寄せ)
            C: カテゴリ全体の承認済み平均評価
        helpful_boost = ln(1 + 参考になった合計) * 0.1
        ranking_score = bayesian_avg + helpful_boost

    制約:
        - 承認済み口コミが 1 件以上ある商品のみ対象 (口コミ 0 件は除外)
        - 同点フォールバック: 口コミ件数 desc → sort_order asc → id asc

    差し替え時はこの関数だけを書き換えれば全ランキング画面に反映されます。
    """
    from django.db.models import (
        Avg, Count, F, FloatField, IntegerField,
        OuterRef, Q, Subquery, Value, ExpressionWrapper,
    )
    from django.db.models.functions import Coalesce, Ln
    from apps.reviews.models import Review, ReviewHelpful

    # カテゴリ全体の平均評価 (Bayesian の事前分布 C)
    cat_avg = (
        Review.objects
        .filter(product__product_type=ptype, product__is_published=True, is_approved=True)
        .aggregate(a=Avg("rating"))["a"]
    ) or 3.0
    M = 5.0  # 信頼度しきい値

    # helpful_total は二重 JOIN を避けるため Subquery
    helpful_subq = (
        ReviewHelpful.objects
        .filter(review__product=OuterRef("pk"), review__is_approved=True)
        .order_by()
        .values("review__product")
        .annotate(c=Count("id"))
        .values("c")
    )

    return (
        Product.objects
        .filter(is_published=True, product_type=ptype)
        .annotate(
            review_count=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            helpful_total=Coalesce(Subquery(helpful_subq, output_field=IntegerField()), Value(0)),
        )
        .filter(review_count__gte=1)
        .annotate(
            ranking_score=ExpressionWrapper(
                (F("review_count") * F("avg_rating") + Value(M * cat_avg))
                / (F("review_count") + Value(M))
                + Ln(Value(1.0) + F("helpful_total")) * Value(0.1),
                output_field=FloatField(),
            ),
        )
        .order_by("-ranking_score", "-review_count", "sort_order", "id")
        .prefetch_related("categories")
    )


def _user_has_review_in_category(user, ptype):
    """ログイン済みかつ該当カテゴリでレビュー投稿済みなら True。"""
    if not user.is_authenticated:
        return False
    from apps.reviews.models import Review
    return Review.objects.filter(
        user=user, product__product_type=ptype, is_approved=True,
    ).exists()


def type_ranking(request, type_slug):
    """商品ランキング一覧 - URL: /<type_slug>/ranking/ (口コミ投稿者の特権)"""
    ptype = get_object_or_404(Category, slug=type_slug, parent__isnull=True)
    products_qs = _ranking_queryset(ptype)

    # 該当カテゴリで未投稿のユーザー(未ログイン含む)は TOP3 + LP のみ
    if not _user_has_review_in_category(request.user, ptype):
        return render(request, "products/ranking_locked.html", {
            "ptype": ptype,
            "active_type": ptype,
            "product_types": _product_types(),
            "top_products": list(products_qs[:3]),
            "total_count": products_qs.count(),
        })

    # 投稿済ユーザー: 全件表示
    q = request.GET.get("q", "").strip()
    function_slug = request.GET.get("category", "").strip()

    products = products_qs
    if function_slug:
        products = products.filter(categories__slug=function_slug)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q))

    functions = Category.objects.filter(parent=ptype).order_by("sort_order", "name")
    articles = Article.objects.filter(is_published=True, product_type=ptype).order_by("-published_at", "-created_at")[:6]

    return render(request, "products/product_list.html", {
        "products": products.distinct(),
        "product_types": _product_types(),
        "active_type": ptype,
        "type_articles": articles,
        "functions": functions,
        "noindex": True,
        "active_function": function_slug,
        "q": q,
    })


# カテゴリ別 hub 記事 (比較記事 / 選び方記事)。今回は美顔器のみ先行。
# 将来は Category モデルに hub_compare_article_slug / hub_select_article_slug を持たせる想定。
HUB_ARTICLES = {
    "bigankiki": {"compare": "osusume-hikaku", "select": "bigankiki"},
    "dryer": {"compare": "dryer-osusume-hikaku", "select": "dryer"},
}


def _category_hub_articles(product):
    """商品ページ用: カテゴリの「おすすめ比較記事」「選び方記事」のページカード2本。"""
    pt = product.product_type
    if not pt:
        return []
    conf = HUB_ARTICLES.get(pt.slug)
    if not conf:
        return []
    out = []
    comp = Article.objects.filter(slug=conf["compare"], is_published=True).first()
    if comp:
        out.append({
            "url": comp.get_absolute_url(), "title": comp.title,
            "kind": "おすすめ比較", "desc": comp.meta_description or comp.excerpt or "",
        })
    sel_slug = conf["select"]
    cat = Category.objects.filter(parent__isnull=True, slug=sel_slug).first()
    if cat:
        out.append({
            "url": f"/{cat.slug}/", "title": cat.name,
            "kind": "選び方", "desc": cat.meta_description or cat.description or "",
        })
    else:
        sel = Article.objects.filter(slug=sel_slug, is_published=True).first()
        if sel:
            out.append({
                "url": sel.get_absolute_url(), "title": sel.title,
                "kind": "選び方", "desc": sel.meta_description or sel.excerpt or "",
            })
    return out


def _related_article_cards(product):
    """商品ページ用: 手動キュレーションした関連記事(Product.related_articles)を
    role-chip付きカード dict にする(最大4本)。Phase 3b で機構hub/悩みhub等を populate。"""
    from .templatetags.article_extras import _article_role
    cards = []
    for a in product.related_articles.filter(is_published=True):
        cards.append({
            "url": a.get_absolute_url(), "title": a.title,
            "kind": _article_role(a), "desc": a.meta_description or a.excerpt or "",
        })
    return cards[:4]


def detail(request, type_slug, slug):
    """商品詳細 - URL: /<type_slug>/products/<slug>/"""
    product = get_object_or_404(
        Product.objects.prefetch_related(
            "categories", "articles", "related_articles"
        ).select_related("product_type"),
        slug=slug, is_published=True, product_type__slug=type_slug,
    )
    stats = product.review_stats()
    reviews = product.reviews.filter(is_approved=True).select_related("user").order_by("-created_at")
    user_review = None
    can_view = False
    is_bookmarked = False
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        if product.product_type_id:
            can_view = request.user.reviews.filter(
                product__product_type_id=product.product_type_id
            ).exists()
        is_bookmarked = Bookmark.objects.filter(user=request.user, product=product).exists()
    preview_reviews = reviews[:2] if not can_view else None
    full_reviews = reviews if can_view else None
    # SEO内部リンク用の関連商品 6 件(通常商品でも表示)。生産終了は「最新のおすすめ」として強調。
    similar_products = _similar_products_for(product, limit=6)
    # 商品ページから比較記事・選び方記事へ評価を返すページカード(2本)
    hub_cards = _category_hub_articles(product)
    # 手動キュレーションの関連記事(機構hub/悩みhub/比較/選び方)最大4本
    related_article_cards = _related_article_cards(product)

    return render(request, "products/product_detail.html", {
        "similar_products": similar_products,
        "hub_cards": hub_cards,
        "related_article_cards": related_article_cards,
        "product": product, "stats": stats,
        "reviews": full_reviews, "preview_reviews": preview_reviews,
        "user_review": user_review, "can_view": can_view,
        "is_bookmarked": is_bookmarked,
        "product_types": _product_types(),
    })


def article_list(request):
    articles = Article.objects.filter(is_published=True).select_related("product_type")
    return render(request, "products/article_list.html", {
        "articles": articles, "product_types": _product_types(),
    })


def article_detail(request, slug):
    """記事詳細 - URL: /<slug>/  (ドメイン直下の安定URL)"""
    article = get_object_or_404(
        Article.objects.select_related("product_type"),
        slug=slug, is_published=True,
    )
    return render(request, "products/article_detail.html", {
        "article": article, "product_types": _product_types(),
    })


@login_required
@require_POST
def bookmark_toggle(request, slug):
    product = get_object_or_404(Product, slug=slug, is_published=True)
    bm = Bookmark.objects.filter(user=request.user, product=product).first()
    if bm:
        bm.delete()
        messages.info(request, f"「{product.name}」を気になる一覧から外しました。")
    else:
        Bookmark.objects.create(user=request.user, product=product)
        messages.success(request, f"「{product.name}」を気になる一覧に追加しました。")
    next_url = request.POST.get("next") or product.get_absolute_url()
    return HttpResponseRedirect(next_url)


# =============================================================================
# 信頼性重視カテゴリTOP (datsumouki 先行 / hair-iron・dryer へ流用可)
#   カテゴリ別の文言・リンクは TRUST_LANDING で差し替え。数値は実データのみ。
# =============================================================================
TRUST_LANDING = {
    "datsumouki": {
        "eyebrow": "美容家電TUSHOU · 脱毛器",
        "h1": "脱毛器を、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合う家庭用脱毛器を、納得して選べる拠点です。",
        "hub_slug": "datsumouki-osusume-hikaku",
        "hub_title": "脱毛器のおすすめ比較ガイド",
        "hub_text": "光・レーザー・冷却の違いから、価格帯・部位ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["効果の実感", "痛み", "価格", "使いやすさ", "口コミ傾向"],
        "find_groups": [
            {"label": "タイプで選ぶ", "items": [
                {"t": "光（IPL）", "u": "/datsumouki-ipl/"},
                {"t": "レーザー", "u": "/datsumouki-reiza/"},
                {"t": "冷却機能つき", "u": "/datsumouki-cool/"}]},
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円台", "u": "/products/?type=datsumouki&pmax=19999&sort=price_asc"},
                {"t": "2〜4万円", "u": "/products/?type=datsumouki&pmin=20000&pmax=49999&sort=price_asc"},
                {"t": "5万円〜", "u": "/products/?type=datsumouki&pmin=50000&sort=price_desc"}]},
            {"label": "悩み・部位で選ぶ", "items": [
                {"t": "VIO", "u": "/datsumouki-vio/"},
                {"t": "メンズ・ヒゲ", "u": "/datsumouki-mens/"},
                {"t": "顔・産毛", "u": "/datsumouki-kao/"},
                {"t": "全身", "u": "/datsumouki-zenshin/"},
                {"t": "痛みが心配", "u": "/datsumouki-itami/"},
                {"t": "効果・回数", "u": "/datsumouki-kaisu/"}]},
            {"label": "使う人で選ぶ", "items": [
                {"t": "学生", "u": "/datsumouki-gakusei/"},
                {"t": "サロンと比較", "u": "/datsumouki-salon/"}]},
        ],
        "theme_groups": [
            {"label": "仕組みで知る", "items": [
                {"t": "光（IPL）", "u": "/datsumouki-ipl/"}, {"t": "レーザー", "u": "/datsumouki-reiza/"}, {"t": "冷却機能", "u": "/datsumouki-cool/"}]},
            {"label": "悩み・部位で読む", "items": [
                {"t": "VIO", "u": "/datsumouki-vio/"}, {"t": "メンズ", "u": "/datsumouki-mens/"}, {"t": "顔・産毛", "u": "/datsumouki-kao/"},
                {"t": "全身", "u": "/datsumouki-zenshin/"}, {"t": "痛み", "u": "/datsumouki-itami/"}, {"t": "効果・回数", "u": "/datsumouki-kaisu/"}]},
            {"label": "価格・使う人で読む", "items": [
                {"t": "コスパで選ぶ", "u": "/datsumouki-cospa/"}, {"t": "学生向け", "u": "/datsumouki-gakusei/"}, {"t": "サロンと比較", "u": "/datsumouki-salon/"}]},
        ],
        "price_bands": [(0, 19999), (20000, 49999), (50000, 10 ** 12)],
    },
    "hair-iron": {
        "eyebrow": "美容家電TUSHOU · ヘアアイロン",
        "h1": "ヘアアイロンを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合うヘアアイロンを、納得して選べる拠点です。",
        "hub_slug": "hair-iron-osusume-hikaku",
        "hub_title": "ヘアアイロンのおすすめ比較ガイド",
        "hub_text": "ストレート・カール・2WAYの違いから、髪質・価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["仕上がりのツヤ", "髪へのダメージ", "温度・立ち上がり", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "タイプで選ぶ", "items": [
                {"t": "ストレート", "u": "/hair-iron-straight/"},
                {"t": "カール（コテ）", "u": "/hair-iron-curl/"},
                {"t": "2WAY", "u": "/hair-iron-2way/"},
                {"t": "ヒートブラシ", "u": "/hair-iron-brush/"}]},
            {"label": "価格で選ぶ", "items": [
                {"t": "〜5,000円", "u": "/products/?type=hair-iron&pmax=4999&sort=price_asc"},
                {"t": "5,000〜1万円", "u": "/products/?type=hair-iron&pmin=5000&pmax=9999&sort=price_asc"},
                {"t": "1万円〜", "u": "/products/?type=hair-iron&pmin=10000&sort=price_desc"}]},
            {"label": "悩み・髪質で選ぶ", "items": [
                {"t": "くせ毛", "u": "/hair-iron-kusege/"},
                {"t": "前髪", "u": "/hair-iron-maegami/"},
                {"t": "傷みにくい", "u": "/hair-iron-itamanai/"},
                {"t": "海外対応", "u": "/hair-iron-kaigai/"}]},
            {"label": "使う人で選ぶ", "items": [
                {"t": "学生", "u": "/hair-iron-gakusei/"},
                {"t": "メンズ", "u": "/hair-iron-mens/"},
                {"t": "大人世代", "u": "/hair-iron-otona/"}]},
        ],
        "theme_groups": [
            {"label": "タイプで知る", "items": [
                {"t": "ストレート", "u": "/hair-iron-straight/"}, {"t": "カール", "u": "/hair-iron-curl/"}, {"t": "2WAY", "u": "/hair-iron-2way/"},
                {"t": "ヒートブラシ", "u": "/hair-iron-brush/"}, {"t": "26mm", "u": "/hair-iron-curl26/"}, {"t": "32mm", "u": "/hair-iron-curl32/"}]},
            {"label": "悩み・髪質で読む", "items": [
                {"t": "くせ毛", "u": "/hair-iron-kusege/"}, {"t": "前髪", "u": "/hair-iron-maegami/"}, {"t": "傷みにくい", "u": "/hair-iron-itamanai/"},
                {"t": "海外対応", "u": "/hair-iron-kaigai/"}]},
            {"label": "価格・使う人で読む", "items": [
                {"t": "コスパで選ぶ", "u": "/hair-iron-cospa/"}, {"t": "安い・プチプラ", "u": "/hair-iron-yasui/"}, {"t": "学生向け", "u": "/hair-iron-gakusei/"},
                {"t": "メンズ", "u": "/hair-iron-mens/"}, {"t": "大人世代", "u": "/hair-iron-otona/"}]},
        ],
        "price_bands": [(0, 4999), (5000, 9999), (10000, 10 ** 12)],
    },
    "dryer": {
        "eyebrow": "美容家電TUSHOU · ドライヤー",
        "h1": "ドライヤーを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合うドライヤーを、納得して選べる拠点です。",
        "hub_slug": "dryer-osusume-hikaku",
        "hub_title": "ドライヤーのおすすめ比較ガイド",
        "hub_text": "速乾・美髪ケア・価格の違いから、髪質・使う人ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["速乾性（風量）", "髪へのやさしさ", "静音性", "重さ・取り回し", "価格"],
        "find_groups": [
            {"label": "機能で選ぶ", "items": [
                {"t": "速乾・大風量", "u": "/dryer-sokkan/"},
                {"t": "美髪・ケア", "u": "/dryer-bihatsu/"},
                {"t": "ダメージレス", "u": "/dryer-itamanai/"},
                {"t": "静音", "u": "/dryer-seion/"}]},
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=dryer&pmax=9999&sort=price_asc"},
                {"t": "1〜3万円", "u": "/products/?type=dryer&pmin=10000&pmax=29999&sort=price_asc"},
                {"t": "3万円〜", "u": "/products/?type=dryer&pmin=30000&sort=price_desc"}]},
            {"label": "悩み・髪質で選ぶ", "items": [
                {"t": "くせ毛・うねり", "u": "/dryer-kusege/"},
                {"t": "毛量が多い", "u": "/dryer-ryoooi/"},
                {"t": "軽量がいい", "u": "/dryer-keiryo/"}]},
            {"label": "使う人で選ぶ", "items": [
                {"t": "メンズ", "u": "/dryer-mens/"},
                {"t": "子供・赤ちゃん", "u": "/dryer-kodomo/"}]},
        ],
        "theme_groups": [
            {"label": "機能で読む", "items": [
                {"t": "速乾", "u": "/dryer-sokkan/"}, {"t": "美髪", "u": "/dryer-bihatsu/"}, {"t": "ダメージレス", "u": "/dryer-itamanai/"},
                {"t": "静音", "u": "/dryer-seion/"}, {"t": "軽量", "u": "/dryer-keiryo/"}]},
            {"label": "悩み・髪質で読む", "items": [
                {"t": "くせ毛・うねり", "u": "/dryer-kusege/"}, {"t": "毛量が多い", "u": "/dryer-ryoooi/"}, {"t": "メンズ", "u": "/dryer-mens/"},
                {"t": "子供・赤ちゃん", "u": "/dryer-kodomo/"}]},
            {"label": "価格で読む", "items": [
                {"t": "コスパで選ぶ", "u": "/dryer-cospa/"}, {"t": "安い", "u": "/dryer-yasui/"}, {"t": "高級の違い", "u": "/dryer-kokyu/"}]},
        ],
        "price_bands": [(0, 9999), (10000, 29999), (30000, 10 ** 12)],
    },
    "bigankiki": {
        "eyebrow": "美容家電TUSHOU · 美顔器",
        "h1": "美顔器を、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合う美顔器を、納得して選べる拠点です。",
        "hub_slug": "osusume-hikaku",
        "hub_title": "美顔器のおすすめ比較ガイド",
        "hub_text": "RF・EMS・イオン導入などタイプの違いから、肌悩み・価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["効果の実感", "肌へのやさしさ", "使いやすさ", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "タイプで選ぶ", "items": [
                {"t": "RF（ラジオ波）", "u": "/kousyuha/"},
                {"t": "EMS", "u": "/ems/"},
                {"t": "マイクロカレント", "u": "/maikurokaren/"},
                {"t": "イオン導入", "u": "/ion/"},
                {"t": "光・LED", "u": "/hikari/"},
                {"t": "超音波", "u": "/tyouonpa/"}]},
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=bigankiki&pmax=9999&sort=price_asc"},
                {"t": "1〜3万円", "u": "/products/?type=bigankiki&pmin=10000&pmax=29999&sort=price_asc"},
                {"t": "3万円〜", "u": "/products/?type=bigankiki&pmin=30000&sort=price_desc"}]},
            {"label": "肌悩みで選ぶ", "items": [
                {"t": "たるみ", "u": "/tarumi/"},
                {"t": "ほうれい線", "u": "/houreisen/"},
                {"t": "しわ", "u": "/kaonosiwa/"},
                {"t": "毛穴", "u": "/keana/"},
                {"t": "シミ", "u": "/simi/"},
                {"t": "くすみ", "u": "/kusumi/"}]},
            {"label": "使う人・目的で選ぶ", "items": [
                {"t": "10代", "u": "/10dai-osusume-biganki/"},
                {"t": "50代", "u": "/50dai-osusume-biganki/"},
                {"t": "プレゼント", "u": "/present/"}]},
        ],
        "theme_groups": [
            {"label": "仕組みで知る", "items": [
                {"t": "RF（ラジオ波）", "u": "/kousyuha/"}, {"t": "EMS", "u": "/ems/"}, {"t": "マイクロカレント", "u": "/maikurokaren/"},
                {"t": "イオン導入", "u": "/ion/"}, {"t": "エレクトロポレーション", "u": "/erekutoro/"}, {"t": "光・LED", "u": "/hikari/"},
                {"t": "超音波", "u": "/tyouonpa/"}, {"t": "レーザー", "u": "/reiza/"}]},
            {"label": "肌悩みで読む", "items": [
                {"t": "たるみ", "u": "/tarumi/"}, {"t": "ほうれい線", "u": "/houreisen/"}, {"t": "しわ", "u": "/kaonosiwa/"},
                {"t": "毛穴", "u": "/keana/"}, {"t": "シミ", "u": "/simi/"}, {"t": "くすみ", "u": "/kusumi/"},
                {"t": "むくみ", "u": "/mukimi/"}, {"t": "ニキビ", "u": "/nikibi/"}]},
            {"label": "価格・使う人で読む", "items": [
                {"t": "1万円以下", "u": "/1man-ika-biganki/"}, {"t": "10代", "u": "/10dai-osusume-biganki/"}, {"t": "50代", "u": "/50dai-osusume-biganki/"},
                {"t": "プレゼント", "u": "/present/"}]},
        ],
        "price_bands": [(0, 9999), (10000, 29999), (30000, 10 ** 12)],
    },
}


def _trust_landing(request, ptype):
    """信頼性重視カテゴリTOP。指標は実データのみ。"""
    from django.db.models import Max
    cfg = TRUST_LANDING[ptype.slug]
    base_qs = Product.objects.filter(is_published=True, is_discontinued=False, product_type=ptype)
    prods = _annotate(base_qs.prefetch_related("categories"))
    arts = Article.objects.filter(is_published=True, product_type=ptype)

    product_count = base_qs.count()
    kuchikomi_count = arts.filter(slug__icontains="-kuchikomi").count()
    dates = [d for d in (arts.aggregate(m=Max("updated_at"))["m"],
                         base_qs.aggregate(m=Max("updated_at"))["m"]) if d]
    last_updated = max(dates) if dates else None

    # 脱毛器一覧: 標準の並び (口コミ→評価→表示順) で最大20件。
    popular = list(
        prods.order_by("-review_count", "-avg_rating", "sort_order", "id")[:20]
    )

    # 新着・更新フィード: 実在の記事更新のみ (商品ページは含めない)。最大40件。
    feed = []
    for a in arts.order_by("-updated_at")[:40]:
        feed.append({"date": a.updated_at or a.published_at or a.created_at,
                     "kind": "口コミ分析" if a.slug.endswith("-kuchikomi") else "記事更新",
                     "title": a.title, "url": a.get_absolute_url(),
                     "image": a.display_thumbnail})
    feed = sorted(feed, key=lambda x: x["date"], reverse=True)[:40]

    return render(request, "products/type_landing_trust.html", {
        "ptype": ptype, "active_type": ptype, "cfg": cfg,
        "product_count": product_count, "kuchikomi_count": kuchikomi_count,
        "last_updated": last_updated, "popular": popular, "feed": feed,
        "product_types": _product_types(),
    })


def type_landing(request, type_slug):
    """カテゴリTOP(SEOランディング) - URL: /<type_slug>/"""
    from django.core.paginator import Paginator
    ptype = get_object_or_404(Category, slug=type_slug, parent__isnull=True)

    if ptype.slug in TRUST_LANDING:
        return _trust_landing(request, ptype)

    # ランキングプレビュー用 上位6商品 (生産終了は除外)
    top_products = _annotate(
        Product.objects.filter(is_published=True, is_discontinued=False, product_type=ptype)
        .prefetch_related("categories")
    ).order_by("-avg_rating", "sort_order")[:6]

    # bigankiki TOPは全商品をavg_rating順でページネーション(12件/ページ)
    page_obj = None
    landing_top = ""
    landing_bottom = ""
    if ptype.slug == "bigankiki":
        all_products = _annotate(
            Product.objects.filter(is_published=True, is_discontinued=False, product_type=ptype)
            .prefetch_related("categories")
        ).order_by("-avg_rating", "sort_order")
        paginator = Paginator(all_products, 12)
        page_obj = paginator.get_page(request.GET.get("page"))
        if ptype.landing_html and "<!--PRODUCT_LIST_HERE-->" in ptype.landing_html:
            parts = ptype.landing_html.split("<!--PRODUCT_LIST_HERE-->", 1)
            landing_top, landing_bottom = parts[0], parts[1]
        else:
            landing_top = ptype.landing_html or ""

    # カテゴリ所属の記事(biyou は記事カテゴリなので多めに、他は6件)
    article_qs = Article.objects.filter(
        is_published=True, product_type=ptype
    ).order_by("-published_at", "-created_at")
    if ptype.slug in ("biyou", "colam-ipan"):
        _article_paginator = Paginator(article_qs, 30)
        articles = _article_paginator.get_page(request.GET.get("article_page"))
    else:
        articles = article_qs[:6]

    return render(request, "products/type_landing.html", {
        "ptype": ptype,
        "active_type": ptype,
        "top_products": top_products,
        "articles": articles,
        "page_obj": page_obj,
        "landing_top": landing_top,
        "landing_bottom": landing_bottom,
        "product_types": _product_types(),
    })


def slug_dispatch(request, slug):
    """/<slug>/ を カテゴリTOP or 記事詳細に自動振り分け
    
    優先順:
    1. parent=None の Category と一致 → カテゴリランディング
    2. is_published=True の Article と一致 → 記事詳細
    3. どちらでもない → 404
    """
    cat = Category.objects.filter(parent__isnull=True, slug=slug).first()
    if cat:
        return type_landing(request, type_slug=slug)
    article = Article.objects.filter(slug=slug, is_published=True).first()
    if article:
        return article_detail(request, slug=slug)
    raise Http404(f"slug={slug} に該当するページがありません")



def all_products(request):
    """全商品一覧 (検索+ブランド/カテゴリ絞込+ソート)。"""
    from django.core.paginator import Paginator

    q = (request.GET.get("q") or "").strip()
    brand = (request.GET.get("brand") or "").strip()
    type_slug = (request.GET.get("type") or "").strip()
    sort = (request.GET.get("sort") or "rating").strip()

    qs = _annotate(Product.objects.filter(is_published=True).prefetch_related("categories"))

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q))
    if brand:
        qs = qs.filter(brand=brand)
    if type_slug:
        qs = qs.filter(product_type__slug=type_slug)
    # 価格帯フィルタ (カテゴリTOPの価格タイルから利用)
    pmin = (request.GET.get("pmin") or "").strip()
    pmax = (request.GET.get("pmax") or "").strip()
    if pmin.isdigit():
        qs = qs.filter(price__gte=int(pmin))
    if pmax.isdigit():
        qs = qs.filter(price__gt=0, price__lte=int(pmax))

    if sort == "newest":
        qs = qs.order_by("-created_at", "-id")
    elif sort == "price_asc":
        qs = qs.filter(price__gt=0).order_by("price", "-id")
    elif sort == "price_desc":
        qs = qs.order_by("-price", "-id")
    else:  # rating (default)
        qs = qs.order_by("-avg_rating", "-review_count", "-id")
        sort = "rating"

    paginator = Paginator(qs.distinct(), 24)
    page = paginator.get_page(request.GET.get("page", 1))

    # ページャ用 query string (page を除く)
    query_params = request.GET.copy()
    query_params.pop("page", None)

    # ブランド一覧 (フィルタ用)
    brands = (
        Product.objects.filter(is_published=True)
        .exclude(brand="")
        .values_list("brand", flat=True)
        .distinct()
        .order_by("brand")
    )

    types = Category.objects.filter(parent__isnull=True, show_in_header=True).order_by("sort_order", "name")

    return render(request, "products/all_products.html", {
        "page": page,
        "q": q,
        "brand": brand,
        "type_slug": type_slug,
        "sort": sort,
        "brands": list(brands),
        "types": types,
        "total": paginator.count,
        "product_types": _product_types(),
        "query_string": query_params.urlencode(),
    })
