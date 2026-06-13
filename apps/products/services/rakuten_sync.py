"""楽天 Open API (Ichiba MS) クライアント。

エンドポイント: https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401
認証: applicationId(UUID) + accessKey(pk_xxx) の両方が必要。
affiliateId 指定時は affiliateUrl が自動付与される。
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"


def _get_credentials():
    """(app_id, access_key, affiliate_id) を返す。"""
    from apps.products.models import ApiCredential

    cred = ApiCredential.load()
    if cred.is_rakuten_enabled and cred.rakuten_app_id:
        return (
            cred.rakuten_app_id,
            cred.rakuten_access_key or "",
            cred.rakuten_affiliate_id or "",
        )
    return (
        os.getenv("RAKUTEN_APP_ID", ""),
        os.getenv("RAKUTEN_ACCESS_KEY", ""),
        os.getenv("RAKUTEN_AFFILIATE_ID", ""),
    )


def is_enabled():
    app_id, _, _ = _get_credentials()
    return bool(app_id)


def _normalize_image_url(url):
    if not url:
        return url
    return url.split("?_ex=")[0]


def parse_item(item):
    images = []
    for size_key in ("mediumImageUrls", "smallImageUrls"):
        for img in item.get(size_key, []) or []:
            url = img.get("imageUrl") if isinstance(img, dict) else img
            url = _normalize_image_url(url)
            if url and url not in images:
                images.append(url)

    return {
        "rakuten_item_code": item.get("itemCode", ""),
        "title": (item.get("itemName") or "").strip(),
        "shop_name": item.get("shopName", ""),
        "image_url": images[0] if images else "",
        "image_urls_extra": images[1:],
        "price": int(item["itemPrice"]) if item.get("itemPrice") else None,
        "caption": item.get("itemCaption", ""),
        "rakuten_url": item.get("itemUrl", ""),
        "affiliate_url": item.get("affiliateUrl", ""),
        "review_count": item.get("reviewCount", 0),
        "review_average": item.get("reviewAverage", 0.0),
        "raw": item,
    }


def _request(params):
    """Rakuten Open API へ GET。ブラウザ擬装ヘッダ + レート制限緩和の throttle。"""
    import time as _t
    _t.sleep(1.2)  # 1秒/req のレート制限対策
    headers = {
        "Referer": "https://sc-tsusho.jp/",
        "Origin": "https://sc-tsusho.jp",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response is not None else ""
        logger.error(f"Rakuten HTTPError: {e} body={body}")
    except Exception as e:
        logger.error(f"Rakuten request failed: {e}")
    return None


def search_items(keyword, brand=None, hits=10, page=1, genre_id=None):
    app_id, access_key, aff_id = _get_credentials()
    if not app_id or not access_key:
        logger.warning("Rakuten API not configured (app_id and access_key required)")
        return []

    q = f"{brand} {keyword}".strip() if brand else keyword
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "format": "json",
        "formatVersion": 2,
        "keyword": q,
        "hits": min(hits, 30),
        "page": page,
        "imageFlag": 1,
        "availability": 1,
    }
    if aff_id:
        params["affiliateId"] = aff_id
    if genre_id:
        params["genreId"] = genre_id

    data = _request(params)
    if not data:
        return []

    items = data.get("Items", []) or []
    out = []
    for it in items:
        node = it.get("Item") if isinstance(it, dict) and "Item" in it else it
        out.append(parse_item(node))
    return out


def get_by_code(item_code):
    app_id, access_key, aff_id = _get_credentials()
    if not app_id or not access_key or not item_code:
        return None
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "format": "json",
        "formatVersion": 2,
        "itemCode": item_code,
    }
    if aff_id:
        params["affiliateId"] = aff_id
    data = _request(params)
    if not data:
        return None
    items = data.get("Items", []) or []
    if not items:
        return None
    it = items[0]
    node = it.get("Item") if isinstance(it, dict) and "Item" in it else it
    return parse_item(node)
