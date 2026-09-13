"""購入リンクのクリック記録の受け口（2026-09-14新設）。

templates/includes/_outbound_click.html のスクリプトが、楽天・Amazon等のリンクが押された瞬間に
navigator.sendBeacon で POST する。リンク自体は変えない（遷移は通常どおりブラウザが行う）。
記録に失敗しても利用者の遷移には影響しないので、ここでは常に 204 を返す。
"""
import hashlib
import json
import time
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .middleware import BOT_PATTERNS
from .models import OutboundClick

_MAX_BODY = 4096
_MAX_PER_IP_HOUR = 120
_ALLOWED_HOSTS = ("sc-tsusho.jp", "www.sc-tsusho.jp")

_url_map = {"at": 0.0, "map": {}}


def _norm(url):
    return (url or "").strip().rstrip("/")


def _product_slug_for(href):
    """リンクURL → 商品slug。商品のaffiliate/rakuten/amazon URLと完全一致したものだけ。10分キャッシュ。"""
    if time.time() - _url_map["at"] > 600:
        from apps.products.models import Product
        m = {}
        for slug, *urls in Product.objects.values_list(
                "slug", "affiliate_url", "rakuten_url", "amazon_url"):
            for u in urls:
                if u:
                    m.setdefault(_norm(u), slug)
        _url_map.update(at=time.time(), map=m)
    return _url_map["map"].get(_norm(href), "")


def _network(host):
    host = host.lower()
    if "rakuten" in host:
        return "rakuten"
    if "amazon." in host or host.startswith("amzn."):
        return "amazon"
    return "other"


def _ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()[:16]


@csrf_exempt
@require_POST
def outbound_click(request):
    empty = HttpResponse(status=204)
    # 自サイトのページから送られたものだけ受ける（外部からの水増し投稿を避ける）
    origin = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER", "")
    if urlparse(origin).hostname not in _ALLOWED_HOSTS:
        return empty
    if len(request.body) > _MAX_BODY:
        return empty
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return empty
    href = str(data.get("href", ""))[:1000]
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return empty

    ip_hash = _ip(request)
    since = timezone.now() - timedelta(hours=1)
    if OutboundClick.objects.filter(ip_hash=ip_hash, created_at__gte=since).count() >= _MAX_PER_IP_HOUR:
        return empty

    ua = request.META.get("HTTP_USER_AGENT", "")[:300]
    user = getattr(request, "user", None)
    OutboundClick.objects.create(
        network=_network(parsed.hostname),
        page=str(data.get("page", ""))[:500],
        href=href,
        product_slug=_product_slug_for(href),
        link_text=" ".join(str(data.get("text", "")).split())[:120],
        section=" ".join(str(data.get("section", "")).split())[:200],
        container=str(data.get("container", ""))[:200],
        device="mobile" if data.get("mobile") else "pc",
        referrer=str(data.get("ref", ""))[:300],
        ip_hash=ip_hash,
        user_agent=ua,
        is_bot=bool(BOT_PATTERNS.search(ua)),
        is_staff=bool(user and user.is_authenticated and user.is_staff),
    )
    return empty
