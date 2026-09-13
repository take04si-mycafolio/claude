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
    # 承認センターを最上部に（すべての承認作業を1ページで完結させる統合ビュー）
    apps.insert(0, {
        "name": "承認センター",
        "app_label": "approval_center",
        "app_url": "/admin/approvals/",
        "has_module_perms": True,
        "models": [{
            "name": "承認待ち一覧（リライト/口コミ/ミッション特典/アンケートを1画面で承認）",
            "object_name": "ApprovalCenter",
            "admin_url": "/admin/approvals/",
            "view_only": True,
            "perms": {"view": True, "change": False, "add": False, "delete": False},
        }],
    })
    apps.append({
        "name": "SEO・サイト分析",
        "app_label": "seo_tools",
        "app_url": "/admin/seo/cockpit/",
        "has_module_perms": True,
        "models": [{
            "name": "記事SEOコックピット（判定/順位/リライト/次のアクションを1画面で）",
            "object_name": "SeoCockpit",
            "admin_url": "/admin/seo/cockpit/",
            "view_only": True,
            "perms": {"view": True, "change": False, "add": False, "delete": False},
        }, {
            "name": "記事パフォーマンス（アクセス/直帰率/表示回数/キーワード）",
            "object_name": "ArticlePerformance",
            "admin_url": "/admin/seo/article-performance/",
            "view_only": True,
            "perms": {"view": True, "change": False, "add": False, "delete": False},
        }, {
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
from apps.products import admin_image_upload, admin_seo
from apps.analytics import approval_center, article_review, seo_cockpit, seo_dashboard

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


def robots_txt_view(request):
    """robots.txt を配信。sitemap.xml の場所をクローラーに明示する。"""
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")

from apps.analytics.outbound import outbound_click  # noqa: E402

urlpatterns = [
    # 購入リンクのクリック記録（sendBeacon受け口・2026-09-14）
    path("t/oc/", outbound_click, name="outbound_click"),
    path("sitemap.xml", sitemap, {"sitemaps": _sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", robots_txt_view, name="robots_txt"),
]

# IndexNowキー配信ルート（キーが読めた場合のみ登録。catch-allより前に配置）
if _INDEXNOW_KEY:
    urlpatterns += [
        path(f"{_INDEXNOW_KEY}.txt", indexnow_key_view, name="indexnow_key"),
    ]

urlpatterns += [
    # 記事エディタ内の画像アップロード/挿入（admin/ より前に置く）
    path("admin/products/article/<int:article_id>/upload-image/",
         admin_image_upload.upload_article_image, name="admin_article_upload_image"),
    path("admin/products/article/<int:article_id>/images/",
         admin_image_upload.list_article_images, name="admin_article_images"),
    path("admin/products/article-image/<int:image_id>/update/",
         admin_image_upload.update_article_image, name="admin_article_image_update"),
    path("admin/approvals/", approval_center.approvals, name="admin_approval_center"),
    path("admin/approvals/review/<str:kind>/<int:obj_id>/",
         article_review.article_review, name="admin_article_review"),
    path("admin/seo/cockpit/", seo_cockpit.cockpit, name="admin_seo_cockpit"),
    path("admin/seo/cockpit/<int:article_id>/", seo_cockpit.cockpit_article,
         name="admin_seo_cockpit_article"),
    path("admin/seo/cockpit/<int:article_id>/to-workbench/",
         seo_cockpit.cockpit_to_workbench, name="admin_seo_cockpit_to_workbench"),
    path("admin/seo/article-performance/", seo_dashboard.article_performance,
         name="admin_seo_article_performance"),
    path("admin/seo/link-map/", admin_seo.link_map, name="admin_seo_link_map"),
    path("admin/seo/link-map/data/", admin_seo.link_map_data, name="admin_seo_link_map_data"),
    path("admin/", admin.site.urls),
    # ネイティブアプリ連携API。必ず products の catch-all(<uslug:slug>/)より前に置く。
    path("api/", include("config.api_urls")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("reviews/", include("apps.reviews.urls", namespace="reviews")),
    path("survey/", include("apps.surveys.urls", namespace="surveys")),
    path("", include("apps.pages.urls", namespace="pages")),
    path("", include("apps.products.urls", namespace="products")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
