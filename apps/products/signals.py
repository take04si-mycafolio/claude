"""記事本文の [product slug="..."] から Article.related_products を自動同期する。

本文中に埋め込んだ商品を「この記事で取り上げた商品」(記事下グリッド) と
商品ページ側の「関連記事」(逆引き) の正源にする。本文が唯一の真実なので set()。
"""
import re

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Article, Product

PRODUCT_SLUG_RE = re.compile(r'\[product\s+slug="([^"]+)"\]')


def extract_product_slugs(content):
    """記事本文から [product slug=] の slug を出現順・重複排除で返す。"""
    seen, out = set(), []
    for s in PRODUCT_SLUG_RE.findall(content or ""):
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def sync_related_products(article):
    """1記事ぶん同期。反映できた商品数を返す。"""
    slugs = extract_product_slugs(article.content)
    prods = list(Product.objects.filter(slug__in=slugs)) if slugs else []
    article.related_products.set(prods)
    return len(prods)


@receiver(post_save, sender=Article, dispatch_uid="sync_related_products_from_content")
def _sync_related_products_on_save(sender, instance, **kwargs):
    sync_related_products(instance)


def connect():
    # ready() から呼ぶ。@receiver で既に接続済みだが、import を確実に通すための明示エントリ。
    return True
