"""Amazon PA-API v5 クライアント。

認証情報は ApiCredential (DB シングルトン) を最優先 → 環境変数フォールバック。
"""
import logging
import os
import time

logger = logging.getLogger(__name__)


def _get_credentials():
    """(access, secret, tag, country) を返す。資格情報なければ空文字列。"""
    from apps.products.models import ApiCredential

    cred = ApiCredential.load()
    if (
        cred.is_amazon_enabled
        and cred.amazon_access_key
        and cred.amazon_secret_key
        and cred.amazon_partner_tag
    ):
        return (
            cred.amazon_access_key,
            cred.amazon_secret_key,
            cred.amazon_partner_tag,
            "JP",
        )
    return (
        os.getenv("AMAZON_ACCESS_KEY", ""),
        os.getenv("AMAZON_SECRET_KEY", ""),
        os.getenv("AMAZON_PARTNER_TAG", ""),
        os.getenv("AMAZON_COUNTRY", "JP"),
    )


def _client():
    """PA-API SDK クライアント。認証情報なければ None。"""
    access, secret, tag, country = _get_credentials()
    if not (access and secret and tag):
        return None
    try:
        from amazon_paapi import AmazonApi
    except ImportError:
        logger.error("python-amazon-paapi がインストールされていません")
        return None
    return AmazonApi(access, secret, tag, country)


def is_enabled():
    """Amazon 連携が利用可能か。"""
    return _client() is not None


def _g(obj, *path, default=None):
    """ネストされた属性の安全アクセス。"""
    for p in path:
        if obj is None:
            return default
        obj = getattr(obj, p, None)
    return obj if obj is not None else default


def parse_item(item):
    """PA-API SDK の Item オブジェクトを Product にマップしやすい dict に変換。"""
    title = _g(item, "item_info", "title", "display_value", default="")
    brand = (
        _g(item, "item_info", "by_line_info", "brand", "display_value")
        or _g(item, "item_info", "by_line_info", "manufacturer", "display_value")
        or ""
    )

    image_main = _g(item, "images", "primary", "large", "url")
    image_variants = []
    variants = _g(item, "images", "variants", default=[]) or []
    for v in variants:
        url = _g(v, "large", "url")
        if url:
            image_variants.append(url)

    listings = _g(item, "offers", "listings", default=[]) or []
    price_amount = None
    if listings:
        price_amount = _g(listings[0], "price", "amount")

    features = _g(item, "item_info", "features", "display_values", default=[]) or []

    return {
        "asin": item.asin,
        "title": title.strip(),
        "brand": brand.strip(),
        "image_url": image_main,
        "image_urls_extra": image_variants,
        "price": int(price_amount) if price_amount else None,
        "features": features,
        "amazon_url": _g(item, "detail_page_url"),  # アフィリリンク自動付与済
        "raw": {
            "asin": item.asin,
            "url": _g(item, "detail_page_url"),
            "title": title,
            "brand": brand,
            "image": image_main,
            "images_extra": image_variants,
            "price": price_amount,
            "features": features,
        },
    }


def search_items(keyword, brand=None, count=10, search_index="All"):
    """キーワードでアイテム検索。Returns: list[dict] (parse_item 形式)。"""
    client = _client()
    if not client:
        logger.warning("Amazon API not configured")
        return []
    try:
        result = client.search_items(
            keywords=keyword,
            brand=brand,
            item_count=min(count, 10),
            search_index=search_index,
        )
        items = getattr(result, "items", None) or []
        return [parse_item(it) for it in items]
    except Exception as e:
        logger.error(f"Amazon search_items failed: {e}")
        return []


def get_items(asins):
    """ASIN リストから商品情報取得 (最大10件/req)。"""
    client = _client()
    if not client:
        return []
    asins = [a for a in (asins or []) if a][:10]
    if not asins:
        return []
    try:
        result = client.get_items(items=asins)
        items = getattr(result, "items", None) or []
        return [parse_item(it) for it in items]
    except Exception as e:
        logger.error(f"Amazon get_items failed: {e}")
        return []


def throttled_call(fn, *args, **kwargs):
    """1 TPS 制限を踏まえた slow call ヘルパー。"""
    time.sleep(1.1)
    return fn(*args, **kwargs)
