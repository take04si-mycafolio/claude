from django.contrib import admin

admin.site.site_header = "TUSHOU 管理画面"
admin.site.site_title = "TUSHOU Admin"
admin.site.index_title = "サイト管理"
# SEO管理ツールを管理画面のアプリリストに追加
_orig_get_app_list = admin.AdminSite.get_app_list
def _patched_get_app_list(self, request, app_label=None):
    apps = _orig_get_app_list(self, request, app_label)
    if app_label:
        return apps
    apps.append({
        "name": "SEO・サイト分析",
        "app_label": "seo_tools",
        "app_url": "/admin/seo/link-map/",
        "has_module_perms": True,
        "models": [{
            "name": "内部リンクマップ",
            "object_name": "LinkMap",
            "admin_url": "/admin/seo/link-map/",
            "view_only": True,
            "perms": {"view": True, "change": False, "add": False, "delete": False},
        }],
    })
    return apps
admin.AdminSite.get_app_list = _patched_get_app_list

from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path, register_converter

from .sitemaps import sitemaps as _sitemaps

from .converters import UnicodeSlugConverter
from apps.products import admin_seo

register_converter(UnicodeSlugConverter, "uslug")

# --- IndexNow キー配信 -------------------------------------------------------
# IndexNow はサイト所有確認のため {KEY}.txt をサイトルートで公開する必要がある。
# キーは /opt/claude-ops/indexnow_key.txt を単一ソースとして読み込む。
_INDEXNOW_KEY = ""
try:
    _INDEXNOW_KEY = Path("/opt/claude-ops/indexnow_key.txt").read_text(encoding="utf-8").strip()
except OSError:
    _INDEXNOW_KEY = ""


def indexnow_key_view(request):
    """https://sc-tsusho.jp/{KEY}.txt にキー文字列をプレーンテキストで返す。"""
    return HttpResponse(_INDEXNOW_KEY, content_type="text/plain")

urlpatterns = [
    path("sitemap.xml", sitemap, {"sitemaps": _sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
]

# IndexNowキー配信ルート（キーが読めた場合のみ登録。catch-allより前に配置）
if _INDEXNOW_KEY:
    urlpatterns += [
        path(f"{_INDEXNOW_KEY}.txt", indexnow_key_view, name="indexnow_key"),
    ]

urlpatterns += [
    path("admin/seo/link-map/", admin_seo.link_map, name="admin_seo_link_map"),
    path("admin/seo/link-map/data/", admin_seo.link_map_data, name="admin_seo_link_map_data"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("reviews/", include("apps.reviews.urls", namespace="reviews")),
    path("", include("apps.pages.urls", namespace="pages")),
    path("", include("apps.products.urls", namespace="products")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
