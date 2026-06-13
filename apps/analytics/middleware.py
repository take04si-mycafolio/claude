import re
from .models import AccessLog


SKIP_PREFIXES = ("/static/", "/media/", "/favicon.ico", "/robots.txt", "/sitemap")
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".css", ".js", ".ico",
            ".svg", ".webp", ".woff", ".woff2", ".ttf", ".map")
BOT_PATTERNS = re.compile(
    r"bot|crawler|spider|slurp|baiduspider|bingbot|googlebot|yandex|duckduck|"
    r"facebookexternalhit|claudebot|gptbot|chatgpt|perplexity|meta-externalagent",
    re.IGNORECASE,
)


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._log(request, response)
        except Exception:
            pass
        return response

    def _log(self, request, response):
        path = request.path
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return
        if any(path.endswith(e) for e in SKIP_EXT):
            return
        ua = request.META.get("HTTP_USER_AGENT", "")[:500]
        AccessLog.objects.create(
            url=path[:500],
            method=request.method[:10],
            status_code=response.status_code,
            ip=self._get_ip(request),
            user_agent=ua,
            referer=request.META.get("HTTP_REFERER", "")[:500],
            user=request.user if request.user.is_authenticated else None,
            is_bot=bool(BOT_PATTERNS.search(ua)),
        )

    @staticmethod
    def _get_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
