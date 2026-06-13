import re
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import Article, Category, Product


@staff_member_required
def link_map(request):
    return render(request, "admin/seo/link_map.html")


@staff_member_required
def link_map_data(request):
    nodes, edges = [], []

    nodes.append({"id": "home", "label": "TOPページ", "type": "main", "url": "/"})

    # カテゴリ
    category_nid_by_slug = {}
    for c in Category.objects.all():
        nid = f"cat-{c.id}"
        category_nid_by_slug[c.slug] = nid
        url = f"/?category={c.slug}" if c.parent else f"/{c.slug}/"
        nodes.append({"id": nid, "label": c.name, "type": "category", "url": url})
        if c.parent:
            edges.append({"source": f"cat-{c.parent.id}", "target": nid, "kind": "structure"})
        else:
            edges.append({"source": "home", "target": nid, "kind": "structure"})

    # 商品
    products_by_id, products_by_slug = {}, {}
    for p in Product.objects.filter(is_published=True).select_related("product_type"):
        nid = f"prod-{p.id}"
        nodes.append({"id": nid, "label": p.name[:28], "type": "product",
                      "url": p.get_absolute_url(),
                      "subtitle": p.brand})
        products_by_id[p.id] = nid
        products_by_slug[p.slug] = nid
        if p.product_type:
            edges.append({"source": f"cat-{p.product_type.id}", "target": nid, "kind": "structure"})

    # 記事
    articles_by_slug, articles_data = {}, []
    for a in Article.objects.filter(is_published=True):
        nid = f"art-{a.id}"
        nodes.append({"id": nid, "label": a.title[:28], "type": "article",
                      "url": a.get_absolute_url(),
                      "subtitle": "記事"})
        articles_by_slug[a.slug] = nid
        articles_data.append((a, nid))
        edges.append({"source": "home", "target": nid, "kind": "structure"})
        # 関連商品(M2M)
        for p in a.related_products.all():
            if p.id in products_by_id:
                edges.append({"source": nid, "target": products_by_id[p.id], "kind": "related"})

    # 本文中の内部リンク(<a href>)を解析。現行URL: 記事/カテゴリ=/{slug}/、商品=/{type}/products/{slug}/
    def parse_links(content, source_id):
        if not content:
            return
        for href in re.findall(r'''href=["'](/[^"'#?]*)''', content):
            s = href.split("?")[0].split("#")[0].strip("/")
            if not s:
                continue
            parts = s.split("/")
            tgt = None
            if len(parts) >= 3 and parts[-2] == "products" and parts[-1] in products_by_slug:
                tgt = products_by_slug[parts[-1]]
            elif len(parts) == 1:
                tgt = articles_by_slug.get(parts[0]) or category_nid_by_slug.get(parts[0])
            if tgt and tgt != source_id:
                edges.append({"source": source_id, "target": tgt, "kind": "content"})

    for a, nid in articles_data:
        parse_links(a.content, nid)
    for p in Product.objects.filter(is_published=True):
        parse_links(p.description, products_by_id[p.id])

    # 記事下「関連記事」([related slug="a,b,c"] ショートコード) → 記事間の内部リンク
    for a, nid in articles_data:
        for m in re.finditer(r'\[related\s+slug="([^"]+)"', a.content or ""):
            for tslug in (s.strip() for s in m.group(1).split(",")):
                tid = articles_by_slug.get(tslug)
                if tid and tid != nid:
                    edges.append({"source": nid, "target": tid, "kind": "relart"})

    # 商品ページ → 関連ページ への内部リンク (商品詳細ページが実際に出すリンクを再現)
    #   = 関連商品(similar 6件) + 手動キュレーション関連記事(related_articles 最大4) + hub記事カード
    from .views import _similar_products_for, _category_hub_articles

    def _url_to_nid(url):
        s = (url or "").split("?")[0].strip("/")
        if not s:
            return "home"
        if s in articles_by_slug:
            return articles_by_slug[s]
        if s in category_nid_by_slug:
            return category_nid_by_slug[s]
        parts = s.split("/")
        if len(parts) >= 3 and parts[-2] == "products" and parts[-1] in products_by_slug:
            return products_by_slug[parts[-1]]
        return None

    for p in Product.objects.filter(is_published=True).prefetch_related("related_articles"):
        src = products_by_id[p.id]
        targets = []
        for sp in _similar_products_for(p, limit=6):
            targets.append(products_by_id.get(sp.id))
        for a in p.related_articles.filter(is_published=True)[:4]:
            targets.append(articles_by_slug.get(a.slug))
        for card in _category_hub_articles(p):
            targets.append(_url_to_nid(card.get("url")))
        for tgt in targets:
            if tgt and tgt != src:
                edges.append({"source": src, "target": tgt, "kind": "prodrel"})

    # 重複除去
    seen = set()
    deduped = []
    for e in edges:
        key = (e["source"], e["target"], e.get("kind"))
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    return JsonResponse({
        "nodes": nodes,
        "edges": deduped,
        "stats": {
            "pages": len(nodes),
            "links": len(deduped),
            "articles": len([n for n in nodes if n["type"] == "article"]),
            "products": len([n for n in nodes if n["type"] == "product"]),
            "categories": len([n for n in nodes if n["type"] == "category"]),
        }
    })
