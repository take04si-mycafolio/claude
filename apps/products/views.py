from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.accounts.models import Bookmark
from .article_redirects import ARTICLE_MERGES, ARTICLE_REDIRECTS
from .models import Article, Brand, Category, Product


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
    # 承認前でも投稿した時点で特権(ランキング全件閲覧)は解放する。公開表示の
    # ゲート(is_approved)と会員特権は別物で、詳細ページの can_view とも揃える。
    return Review.objects.filter(
        user=user, product__product_type=ptype,
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
    "hair-iron": {"compare": "hair-iron-osusume-hikaku", "select": "hair-iron"},
    "datsumouki": {"compare": "datsumouki-osusume-hikaku", "select": "datsumouki"},
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
            "img": comp.display_thumbnail,
        })
    sel_slug = conf["select"]
    cat = Category.objects.filter(parent__isnull=True, slug=sel_slug).first()
    if cat:
        out.append({
            "url": f"/{cat.slug}/", "title": cat.name,
            "kind": "選び方", "desc": cat.meta_description or cat.description or "",
            "img": "",
        })
    else:
        sel = Article.objects.filter(slug=sel_slug, is_published=True).first()
        if sel:
            out.append({
                "url": sel.get_absolute_url(), "title": sel.title,
                "kind": "選び方", "desc": sel.meta_description or sel.excerpt or "",
                "img": sel.display_thumbnail,
            })
    return out


def _desc_linked_cards(product):
    """商品記事本文(description)からサイト内リンクを抽出しカードdict化する。
    v2記事で紹介した記事・比較した商品を「関連記事」欄へ再掲するため。"""
    import re as _re

    from .templatetags.article_extras import _resolve_internal
    cards = []
    desc = product.description or ""
    # 記事・カテゴリハブ(単一セグメント)。アイキャッチ付きでカード化
    for s in dict.fromkeys(_re.findall(r'href="/([a-z0-9\-_]+)/"', desc)):
        a = Article.objects.filter(slug=s, is_published=True).first()
        if a:
            cards.append({
                "url": a.get_absolute_url(), "title": a.title,
                "kind": _article_role_of(a),
                "desc": a.meta_description or a.excerpt or "",
                "img": a.display_thumbnail,
            })
            continue
        info = _resolve_internal(s)
        if info:
            cards.append(info)
    # 比較で紹介した商品ページ(/カテゴリ/products/slug/)
    for s in dict.fromkeys(_re.findall(r'href="/[a-z0-9\-_]+/products/([a-z0-9\-_]+)/"', desc)):
        p = Product.objects.filter(slug=s, is_published=True).first()
        if p and p.pk != product.pk:
            cards.append({
                "url": p.get_absolute_url(), "title": p.name,
                "kind": "比較した商品",
                "desc": f"参考価格 ¥{p.price}" if p.price else "",
                "img": p.display_image,
            })
    return cards


def _article_role_of(article):
    from .templatetags.article_extras import _article_role
    return _article_role(article)


def _related_article_cards(product):
    """商品ページ用: 手動キュレーションした関連記事(Product.related_articles)を
    role-chip付きカード dict にする(最大4本)。Phase 3b で機構hub/悩みhub等を populate。"""
    from .templatetags.article_extras import _article_role
    cards = []
    for a in product.related_articles.filter(is_published=True):
        cards.append({
            "url": a.get_absolute_url(), "title": a.title,
            "kind": _article_role(a), "desc": a.meta_description or a.excerpt or "",
            "img": a.display_thumbnail,
        })
    return cards[:4]


def _brand_page_for(product):
    """商品の brand 値に一致する公開メーカーページ(Brand)を返す。無ければ None。

    Brand.match_brands の正規化グルーピング（brand_detail と同じ規則）を
    商品→ブランドの逆引きに使う。exclude_name_keywords も同様に尊重する。
    """
    if not product.brand:
        return None
    for b in Brand.objects.filter(is_published=True):
        if product.brand in b.match_list():
            name = product.name or ""
            if any(kw in name for kw in b.exclude_list()):
                continue
            return b
    return None


def detail(request, type_slug, slug):
    """商品詳細 - URL: /<type_slug>/products/<slug>/"""
    product = (
        Product.objects.prefetch_related(
            "categories", "articles", "related_articles"
        ).select_related("product_type")
        .filter(slug=slug, is_published=True, product_type__slug=type_slug)
        .first()
    )
    if product is None:
        # カテゴリ変更などで type_slug が変わった旧URLは、正規URLへ 301 で送る
        # (slug は全体で一意なので type を跨いでも1件に定まる)
        moved = Product.objects.filter(slug=slug, is_published=True).first()
        if moved is not None:
            return HttpResponsePermanentRedirect(moved.get_absolute_url())
        raise Http404("商品が見つかりません")
    stats = product.review_stats()
    reviews = product.reviews.filter(is_approved=True).select_related("user").order_by("-created_at")
    user_review = None
    # メディアサイト方針(2026-09-06): 口コミは誰でも全件閲覧可。
    # 「1件投稿でカテゴリ解放」のゲートは口コミサイト昇格時に戻せるよう can_view の
    # 仕組み自体は残し、常時 True にする。
    can_view = True
    is_bookmarked = False
    if request.user.is_authenticated:
        # 承認待ちも含めて本人の口コミを拾う(承認制)。承認待ちはテンプレート側で
        # 「確認中」の案内を出し、公開一覧(reviews)には承認済みのみが載る。
        user_review = product.reviews.filter(user=request.user).first()
        is_bookmarked = Bookmark.objects.filter(user=request.user, product=product).exists()
    preview_reviews = reviews[:2] if not can_view else None
    full_reviews = reviews if can_view else None
    # 使用記録（ProductUseLog）。既定マネージャが論理削除を除外、新しい順。
    # 既存の口コミ表示方針に合わせ、can_view なら全件・それ以外は2件プレビュー。
    # 承認制: 一般には承認済みのみ。本人の承認待ちは本人にだけ見せる
    # （カード側で「承認待ち」バッジを表示）。
    # 平均評価/ランキング/review_count とは別リレーション(use_logs)なので集計に混ざらない。
    use_log_visible = Q(is_approved=True)
    if request.user.is_authenticated:
        use_log_visible |= Q(user=request.user)
    use_logs = (
        product.use_logs.filter(use_log_visible)
        .select_related("user", "review")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    use_logs_full = use_logs if can_view else None
    use_logs_preview = None if can_view else use_logs[:2]
    # SEO内部リンク用の関連商品 6 件(通常商品でも表示)。生産終了は「最新のおすすめ」として強調。
    similar_products = _similar_products_for(product, limit=6)
    # 商品ページから比較記事・選び方記事へ評価を返すページカード(2本)
    hub_cards = _category_hub_articles(product)
    # 手動キュレーションの関連記事(機構hub/悩みhub/比較/選び方)最大4本
    related_article_cards = _related_article_cards(product)
    # 関連記事を1箇所に統合(2026-09-07 ユーザー指示):
    # 記事本文で紹介した記事 + 手動キュレーション + カテゴリハブ をURL重複なしでまとめ、
    # 口コミ投稿フォームの下に「関連記事」として表示する。
    related_links = []
    _seen_urls = set()
    for card in _desc_linked_cards(product) + related_article_cards + hub_cards:
        if card["url"] in _seen_urls:
            continue
        _seen_urls.add(card["url"])
        related_links.append(card)
    related_links = related_links[:6]

    return render(request, "products/product_detail.html", {
        "similar_products": similar_products,
        "hub_cards": hub_cards,
        "related_article_cards": related_article_cards,
        "product": product, "stats": stats,
        "reviews": full_reviews, "preview_reviews": preview_reviews,
        "use_logs_full": use_logs_full, "use_logs_preview": use_logs_preview,
        "user_review": user_review, "can_view": can_view,
        "is_bookmarked": is_bookmarked,
        "brand_page": _brand_page_for(product),
        "product_types": _product_types(),
        "guest_review_form": _guest_review_form(),
        "guest_form_token": _guest_form_token(product.slug),
        "related_links": related_links,
    })


def _guest_review_form():
    from apps.reviews.forms import GuestReviewForm
    return GuestReviewForm()


def _guest_form_token(slug):
    from apps.reviews.views import guest_form_token
    return guest_form_token(slug)


def article_list(request):
    articles = Article.objects.filter(is_published=True).select_related("product_type")
    return render(request, "products/article_list.html", {
        "articles": articles, "product_types": _product_types(),
    })


COLUMN_SLUGS = ("biyou", "colam-ipan")

# コラム記事を内容テーマでクラスタ化し、記事下の「あわせて読みたい」を関連性の高い
# 記事で埋めるためのマップ。コラムは商品カテゴリのような構造を持たないため、
# ここで同テーマ同士を明示的につなぐ(関係の薄い記事へリンクしない=SEO/UX方針)。
# 新規コラムを追加したら該当クラスタに slug を足す(未登録でも新着順フォールバックで6本は出る)。
#   各クラスタは「同テーマで関連性が高い順」に並べる(先頭ほど優先表示)。
#   クラスタ内は最大6本まで先頭から表示→残りは他の物販クラスタで補完するため、
#   そのカテゴリの“ハブ的・汎用的に関連する記事”を前に置くと回遊が最適化される。
#   ※ クーポンは必ず最後のクラスタにまとめる(is_coupon 判定が末尾前提)。物販⇄クーポンは混ぜない。
COLUMN_RELATED_CLUSTERS = (
    # 映像・テレビ・レコーダー・プロジェクター
    ("4ktv", "40tv", "32tv", "burei", "dvd", "mobai_pro"),
    # オーディオ・カメラ・楽器・趣味ガジェット
    ("itiganrefu", "miraresu_itigan", "toy-camera", "action_camera",
     "bluetooth_speaker", "minicop", "ai-supika", "densipiano", "3kyaku", "3d_print"),
    # PC・スマホ・デジタル周辺・ウェアラブル
    ("notepc", "kakuyasu_sumaho", "usb", "wi_fi_ru", "mobile", "mobile_bateri", "smartwatch", "katuroukei", "pen-tab"),
    # 暮らし・健康・癒し・季節家電
    ("taijyu", "denndouhaburasi", "massage_chair", "nyuyokuzai", "aroma_diffuser", "mattress",
     "reifu", "air-cleaner", "kedamatori", "codoles_soujiki"),
    # キッチン家電・調理
    ("mixer", "suihanki", "flyer", "ih-furaipan", "furaipan-sozai", "hotpreto", "open_tosuta", "tousuta",
     "gurirunabe", "denkikeruto", "kogata-reizouko"),
    # ドリンク・カフェ・テーブル雑貨
    ("coffe_mir", "koutya", "wine_cellar", "wine_cooler", "suitou-10", "peppermill"),
    # 文房具・ラベル
    ("ballpen", "yusei-ballpen", "syapen", "tepura"),
    # 車・カー用品
    ("car-soujiki", "drive_recorder", "reda-tntiki"),
    # ファッション・旅行・おでかけ
    ("sneakers", "suitcase"),
    # 運動・ボディケア・健康管理（ヨガ/運動まわりで回遊）
    ("yogamato", "taijyu", "massage_chair", "smartwatch", "mixer"),
    # 美容・入浴・身だしなみ
    ("milk_furo", "bath_salt", "nyuyokuzai", "aroma_diffuser", "kogaokea", "dresser",
     "hair_color", "denndouhaburasi"),
    # 脱毛（脇脱毛コラム → 家庭用脱毛器の実用記事へ回遊させる）
    ("datumou_waki", "datsumouki-osusume-hikaku", "datsumouki-salon", "datsumouki-itami",
     "datsumouki-vio", "datsumouki-zenshin", "datsumouki-kaisu"),
    # クーポン・割引情報(必ず末尾)
    ("adidas-coupon", "dell-coupon", "dominos-coupon", "mcdonalds-coupon",
     "misterdonut-coupon", "nissen-copon", "pizzahut-coupon", "sushiro",
     "uniqlo-coupon", "zoff-coupon"),
)
# クーポン以外(物販レビュー系)は相互に補い合ってよい。クーポン⇄物販はテーマが離れるため分離。
# 末尾=クーポンクラスタを除く全クラスタを物販プールとする。各クラスタから1本ずつ
# ラウンドロビンで拾い、薄いクラスタ(車/文房具/美容等)の補完が1テーマに偏らないようにする。
def _roundrobin_fill(clusters):
    from itertools import zip_longest
    out = []
    for col in zip_longest(*clusters):
        for s in col:
            if s is not None:
                out.append(s)
    return tuple(out)


# 脱毛器クラスタ(datumou_waki 起点)は専用回遊のため、他コラムの埋め草プールには混ぜない。
_COLUMN_SHOPPING_FILL = _roundrobin_fill(
    tuple(c for c in COLUMN_RELATED_CLUSTERS[:-1] if "datumou_waki" not in c)
)


def _column_related_articles(article, limit=6):
    """コラム記事の関連コラムを最大 limit 本、関連性順で返す。
    1) 同テーマクラスタ → 2) (クーポン以外は)他の物販系コラム → 3) 全コラム新着順 で補完。"""
    slug = article.slug
    cluster = next((c for c in COLUMN_RELATED_CLUSTERS if slug in c), None)
    is_coupon = cluster is COLUMN_RELATED_CLUSTERS[-1]

    ordered = []  # 重複を避けつつ優先順位どおりに slug を積む
    def _add(slugs):
        for s in slugs:
            if s != slug and s not in ordered:
                ordered.append(s)

    # 専用クラスタが十分な本数(4本以上)を提供できる記事は、無関係な物販の埋め草をせず
    # 同テーマだけで出す（例: 運動クラスタのヨガマットに4Kテレビ等を混ぜない）。
    cluster_related = len([s for s in cluster if s != slug]) if cluster else 0
    if cluster:
        _add(cluster)
    if not is_coupon and cluster_related < 4:
        _add(_COLUMN_SHOPPING_FILL)

    found = {
        a.slug: a for a in Article.objects.filter(
            slug__in=ordered, is_published=True
        ).select_related("product_type")
    }
    result = [found[s] for s in ordered if s in found][:limit]

    # クラスタ未登録 or 候補不足のコラムは全コラム新着順で 6 本まで補う。
    if len(result) < limit and cluster_related < 4:
        have = {a.pk for a in result} | {article.pk}
        extra = (
            Article.objects.filter(
                product_type__slug__in=COLUMN_SLUGS, is_published=True
            )
            .exclude(pk__in=have)
            .select_related("product_type")
            .order_by("-published_at", "-id")[: limit - len(result)]
        )
        result += list(extra)
    return result


@ensure_csrf_cookie
def article_detail(request, slug):
    """記事詳細 - URL: /<slug>/  (ドメイン直下の安定URL)

    アンケート([survey])のAJAX送信でCSRFトークンを使うため csrftoken cookie を保証する。
    """
    article = (
        Article.objects.select_related("product_type")
        .filter(slug=slug, is_published=True)
        .first()
    )
    if article is None:
        raise Http404("記事が見つかりません")
    ctx = {"article": article, "product_types": _product_types()}
    # コラム記事(美容・コラム一般)は記事下にアイキャッチ付きの関連コラム6本を出して回遊させる。
    if article.product_type and article.product_type.slug in COLUMN_SLUGS:
        ctx["column_related"] = _column_related_articles(article)
    return render(request, "products/article_detail.html", ctx)


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
    "cleansing-brush": {
        "eyebrow": "美容家電TUSHOU · 電動洗顔ブラシ",
        "h1": "電動洗顔ブラシを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合う電動洗顔ブラシを、納得して選べる拠点です。",
        "hub_slug": "cleansing-brush-osusume-hikaku",
        "hub_title": "電動洗顔ブラシのおすすめ比較ガイド",
        "hub_text": "回転式・シリコン音波式・イオン・EMSの違いから、肌質・価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["洗い上がり", "肌へのやさしさ", "防水・お手入れ", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=cleansing-brush&pmax=9999&sort=price_asc"},
                {"t": "1〜2万円", "u": "/products/?type=cleansing-brush&pmin=10000&pmax=19999&sort=price_asc"},
                {"t": "2万円〜", "u": "/products/?type=cleansing-brush&pmin=20000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "FOREO", "u": "/products/?type=cleansing-brush&brand=FOREO"},
                {"t": "フィリップス", "u": "/products/?type=cleansing-brush&brand=フィリップス"},
                {"t": "ヤーマン", "u": "/products/?type=cleansing-brush&brand=ヤーマン"},
                {"t": "SALONIA", "u": "/products/?type=cleansing-brush&brand=SALONIA"},
                {"t": "DISM", "u": "/products/?type=cleansing-brush&brand=DISM"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=cleansing-brush&sort=rating"},
                {"t": "新着順", "u": "/products/?type=cleansing-brush&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=cleansing-brush&sort=price_asc"}]},
        ],
        "theme_groups": [],
        "price_bands": [(0, 9999), (10000, 19999), (20000, 10 ** 12)],
    },
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
    "steamer": {
        "eyebrow": "美容家電TUSHOU · 美顔スチーマー",
        "h1": "美顔スチーマーを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合う美顔スチーマーを、納得して選べる拠点です。",
        "hub_slug": "steamer-osusume-hikaku",
        "hub_title": "美顔スチーマーのおすすめ比較ガイド",
        "hub_text": "据置き・ハンディ、温スチーム・ナノミストの違いから、価格帯・使う人ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["ミストの細かさ", "立ち上がりの速さ", "手入れのしやすさ", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=steamer&pmax=9999&sort=price_asc"},
                {"t": "1〜3万円", "u": "/products/?type=steamer&pmin=10000&pmax=29999&sort=price_asc"},
                {"t": "3万円〜", "u": "/products/?type=steamer&pmin=30000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "パナソニック", "u": "/products/?type=steamer&brand=パナソニック"},
                {"t": "ヤーマン", "u": "/products/?type=steamer&brand=ヤーマン"},
                {"t": "美ルル", "u": "/products/?type=steamer&brand=美ルル"},
                {"t": "FESTINO", "u": "/products/?type=steamer&brand=FESTINO"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=steamer&sort=rating"},
                {"t": "新着順", "u": "/products/?type=steamer&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=steamer&sort=price_asc"}]},
        ],
        "theme_groups": [],
        "price_bands": [(0, 9999), (10000, 29999), (30000, 10 ** 12)],
    },
    "massage": {
        "eyebrow": "美容家電TUSHOU · マッサージ機",
        "h1": "マッサージ機を、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合うマッサージ機・ヘッドスパを、納得して選べる拠点です。",
        "hub_slug": "massage-osusume-hikaku",
        "hub_title": "マッサージ機のおすすめ比較ガイド",
        "hub_text": "ヘッドスパ・かっさ・EMSブラシの違いから、部位・価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["ほぐし心地", "使いやすさ", "防水・お手入れ", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=massage&pmax=9999&sort=price_asc"},
                {"t": "1〜3万円", "u": "/products/?type=massage&pmin=10000&pmax=29999&sort=price_asc"},
                {"t": "3万円〜", "u": "/products/?type=massage&pmin=30000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "ReFa", "u": "/products/?type=massage&brand=ReFa"},
                {"t": "ヤーマン", "u": "/products/?type=massage&brand=ヤーマン"},
                {"t": "Brighte", "u": "/products/?type=massage&brand=Brighte"},
                {"t": "SALONIA", "u": "/products/?type=massage&brand=SALONIA"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=massage&sort=rating"},
                {"t": "新着順", "u": "/products/?type=massage&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=massage&sort=price_asc"}]},
        ],
        "theme_groups": [],
        "price_bands": [(0, 9999), (10000, 29999), (30000, 10 ** 12)],
    },
    "toothbrush": {
        "eyebrow": "美容家電TUSHOU · 電動歯ブラシ",
        "h1": "電動歯ブラシを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合う電動歯ブラシを、納得して選べる拠点です。",
        "hub_slug": "toothbrush-osusume-hikaku",
        "hub_title": "電動歯ブラシのおすすめ比較ガイド",
        "hub_text": "音波・回転式の違いから、替えブラシのコスト・価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["磨き上がり", "静音・振動", "替えブラシのコスト", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜5,000円", "u": "/products/?type=toothbrush&pmax=4999&sort=price_asc"},
                {"t": "5,000〜2万円", "u": "/products/?type=toothbrush&pmin=5000&pmax=19999&sort=price_asc"},
                {"t": "2万円〜", "u": "/products/?type=toothbrush&pmin=20000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "ブラウン", "u": "/products/?type=toothbrush&brand=ブラウン"},
                {"t": "Panasonic", "u": "/products/?type=toothbrush&brand=Panasonic"},
                {"t": "フィリップス", "u": "/products/?type=toothbrush&brand=フィリップス"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=toothbrush&sort=rating"},
                {"t": "新着順", "u": "/products/?type=toothbrush&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=toothbrush&sort=price_asc"}]},
        ],
        "theme_groups": [],
        "price_bands": [(0, 4999), (5000, 19999), (20000, 10 ** 12)],
    },
    "shaver": {
        "eyebrow": "美容家電TUSHOU · シェーバー",
        "h1": "シェーバーを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合うシェーバーを、納得して選べる拠点です。",
        "hub_slug": "shaver-osusume-hikaku",
        "hub_title": "シェーバーのおすすめ比較ガイド",
        "hub_text": "往復式・回転式やレディース・メンズの違いから、価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["剃り心地", "肌へのやさしさ", "手入れ・防水", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜3,000円", "u": "/products/?type=shaver&pmax=2999&sort=price_asc"},
                {"t": "3,000〜5,000円", "u": "/products/?type=shaver&pmin=3000&pmax=4999&sort=price_asc"},
                {"t": "5,000円〜", "u": "/products/?type=shaver&pmin=5000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "Panasonic", "u": "/products/?type=shaver&brand=Panasonic"},
                {"t": "ReFa", "u": "/products/?type=shaver&brand=ReFa"},
                {"t": "フィリップス", "u": "/products/?type=shaver&brand=フィリップス"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=shaver&sort=rating"},
                {"t": "新着順", "u": "/products/?type=shaver&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=shaver&sort=price_asc"}]},
        ],
        "theme_groups": [],
        "price_bands": [(0, 2999), (3000, 4999), (5000, 10 ** 12)],
    },
    "shower-head": {
        "eyebrow": "美容家電TUSHOU · シャワーヘッド",
        "h1": "シャワーヘッドを、本音の口コミで選ぶ。",
        "lede": "紹介料に左右されない中立評価と、実際に使った人の声。あなたに合うシャワーヘッドを、納得して選べる拠点です。",
        "hub_slug": "shower-head-osusume-hikaku",
        "hub_title": "シャワーヘッドのおすすめ比較ガイド",
        "hub_text": "ファインバブル・節水・水圧アップの違いから、価格帯ごとの選び方まで。一本で全体像がつかめます。",
        "criteria": ["節水性", "水当たり・ミスト", "取り付けやすさ", "価格", "口コミ傾向"],
        "find_groups": [
            {"label": "価格で選ぶ", "items": [
                {"t": "〜1万円", "u": "/products/?type=shower-head&pmax=9999&sort=price_asc"},
                {"t": "1〜3万円", "u": "/products/?type=shower-head&pmin=10000&pmax=29999&sort=price_asc"},
                {"t": "3万円〜", "u": "/products/?type=shower-head&pmin=30000&sort=price_desc"}]},
            {"label": "ブランドで選ぶ", "items": [
                {"t": "ReFa", "u": "/products/?type=shower-head&brand=ReFa"},
                {"t": "田中金属製作所", "u": "/products/?type=shower-head&brand=田中金属製作所"},
                {"t": "サイエンス", "u": "/products/?type=shower-head&brand=サイエンス"}]},
            {"label": "並びで選ぶ", "items": [
                {"t": "口コミ評価順", "u": "/products/?type=shower-head&sort=rating"},
                {"t": "新着順", "u": "/products/?type=shower-head&sort=newest"},
                {"t": "価格が安い順", "u": "/products/?type=shower-head&sort=price_asc"}]},
        ],
        "theme_groups": [],
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

    # 比較ガイド(hub)記事が存在するカテゴリだけ hub カードを出す(未整備カテゴリはリンク切れ回避)
    hub_exists = Article.objects.filter(
        slug=cfg["hub_slug"], is_published=True
    ).exists()

    return render(request, "products/type_landing_trust.html", {
        "ptype": ptype, "active_type": ptype, "cfg": cfg,
        "product_count": product_count, "kuchikomi_count": kuchikomi_count,
        "last_updated": last_updated, "popular": popular, "feed": feed,
        "hub_exists": hub_exists,
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
        _article_paginator = Paginator(article_qs, 80)
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
    # 商品ページへ統合した記事の旧URLは、対応する商品ページへ 301 で送る
    # (2026-09-01 の統合。対応表は apps/products/article_redirects.py)
    target = ARTICLE_REDIRECTS.get(slug)
    if target:
        moved = Product.objects.filter(slug=target, is_published=True).first()
        if moved is not None:
            return HttpResponsePermanentRedirect(moved.get_absolute_url())
    # 記事どうしを統合した旧URLは、統合先の記事へ 301 で送る(2026-09-07 の統合)
    merged = ARTICLE_MERGES.get(slug)
    if merged:
        dest = Article.objects.filter(slug=merged, is_published=True).first()
        if dest is not None:
            return HttpResponsePermanentRedirect(dest.get_absolute_url())
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

    paginator = Paginator(qs.distinct(), 48)
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

    # コラム系（記事カテゴリ）は商品の絞込対象にならないため、カテゴリ選択から除外する
    types = (
        Category.objects.filter(parent__isnull=True, show_in_header=True)
        .exclude(slug__in=["colam-ipan", "biyou"])
        .order_by("sort_order", "name")
    )

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


def brand_index(request):
    """メーカー(ブランド)一覧。登録商品3点以上の主要メーカーをカード表示。"""
    cards = []
    for bdef in Brand.objects.filter(is_published=True):
        qs = _annotate(
            bdef.filter_products(
                Product.objects.filter(is_published=True)
            ).prefetch_related("categories")
        )
        prods = list(qs)
        if not prods:
            continue
        # カテゴリ内訳 + 代表画像 + 口コミ集計
        cats = {}
        reviews = 0
        thumb = ""
        for p in prods:
            if p.product_type:
                cats[p.product_type.name] = cats.get(p.product_type.name, 0) + 1
            reviews += p.review_count or 0
            if not thumb and p.display_image:
                thumb = p.display_image
        cards.append({
            "brand": bdef,
            "count": len(prods),
            "reviews": reviews,
            "cats": sorted(cats.items(), key=lambda kv: -kv[1]),
            "thumb": thumb,
        })
    cards.sort(key=lambda c: (-c["count"], -c["reviews"]))

    return render(request, "products/brand_index.html", {
        "cards": cards,
        "total_brands": len(cards),
        "product_types": _product_types(),
        "active_brand": True,
    })


def _brand_spec_compare(ptype, prods, max_cols=6):
    """ブランド×カテゴリの機種横断スペック比較表データを組む。

    行 = spec_schema 順の仕様項目のうち2機種以上で値が入っているもの（最大10行）、
    列 = 商品（並びは呼び出し元の口コミ評価順のまま、先頭 max_cols 機種）。
    比較として成立しない場合（対象2機種未満・行2つ未満・スキーマ未定義）は None。
    """
    from apps.products import spec_schema as S
    if not ptype or len(prods) < 2:
        return None
    schema = S.get_schema(ptype.slug)
    if not schema:
        return None
    cols = prods[:max_cols]
    rows = []
    for f in schema:
        if f["key"] == "official_url":
            continue
        cells = []
        for p in cols:
            specs = p.specifications if isinstance(p.specifications, dict) else {}
            v = specs.get(f["key"])
            cells.append(("" if v is None else str(v)).strip())
        if sum(1 for c in cells if c) >= 2:
            rows.append({"label": f["label"], "cells": cells})
        if len(rows) >= 10:
            break
    if len(rows) < 2:
        return None
    return {"products": cols, "rows": rows, "omitted": max(0, len(prods) - len(cols))}


def brand_detail(request, brand_slug):
    """メーカー個別ページ。該当商品をカテゴリ別・口コミ評価順に表示。"""
    bdef = Brand.objects.filter(slug=brand_slug, is_published=True).first()
    if not bdef:
        raise Http404("メーカーが見つかりません")

    qs = _annotate(
        bdef.filter_products(
            Product.objects.filter(is_published=True)
        ).select_related("product_type").prefetch_related("categories")
    ).order_by("-avg_rating", "-review_count", "-id")
    prods = list(qs)
    if not prods:
        raise Http404("登録商品がありません")

    # カテゴリ(製品タイプ)別にグルーピング。並びはヘッダーのカテゴリ順に寄せる。
    type_order = {t.slug: i for i, t in enumerate(_product_types())}
    groups = {}
    for p in prods:
        key = p.product_type if p.product_type else None
        groups.setdefault(key, []).append(p)
    grouped = sorted(
        groups.items(),
        key=lambda kv: type_order.get(kv[0].slug, 999) if kv[0] else 1000,
    )

    # カテゴリ内をさらにシリーズ別に細分化。
    #  - 2件以上のシリーズは小見出し付きセクションに
    #  - 単発シリーズ / シリーズ未設定は末尾の「個別モデル」へ集約(小見出しの乱立を防ぐ)
    #  各カテゴリを {"series": [(series名, [商品...]), ...], "singles": [商品...]} に変換。
    grouped_series = []
    for ptype, plist in grouped:
        by_series = {}
        for p in plist:
            by_series.setdefault((p.series or "").strip(), []).append(p)
        named = [(s, items) for s, items in by_series.items() if s and len(items) >= 2]
        named.sort(key=lambda si: (-len(si[1]), si[0]))
        singles = [p for s, items in by_series.items()
                   if not (s and len(items) >= 2) for p in items]
        grouped_series.append({
            "ptype": ptype,
            "series": named,
            "singles": singles,
            "count": len(plist),
            "spec_compare": _brand_spec_compare(ptype, plist),
        })
    has_series = any(g["series"] for g in grouped_series)

    ratings = [p.avg_rating for p in prods if p.avg_rating]
    total_reviews = sum(p.review_count or 0 for p in prods)
    stats = {
        "count": len(prods),
        "categories": len(groups),
        "reviews": total_reviews,
        "avg": round(sum(ratings) / len(ratings), 1) if ratings else 0,
    }

    return render(request, "products/brand_detail.html", {
        "bdef": bdef,
        "grouped": grouped,
        "grouped_series": grouped_series,
        "has_series": has_series,
        "stats": stats,
        "product_types": _product_types(),
        "active_brand": True,
    })
