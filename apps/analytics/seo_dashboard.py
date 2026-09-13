"""記事パフォーマンス・ダッシュボード（管理画面の可視化ツール）。

ArticleMetricSnapshot / ArticleMetric の最新スナップショットを読み、
記事ごとのアクセス数・直帰率・GSC表示回数・流入キーワード一覧を可視化する。
データ取得は fetch_article_metrics 管理コマンド（cron/root）が担う。
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.timezone import localtime

from .models import ArticleMetricSnapshot


@staff_member_required
def article_performance(request):
    snap = (ArticleMetricSnapshot.objects
            .order_by("-fetched_at")
            .prefetch_related("metrics")
            .first())

    context = {"snapshot": None, "rows": [], "totals": None,
               "history": [], "fetched_at": None}

    if snap:
        metrics = list(snap.metrics.all())
        rows = [{
            "path": m.path,
            "title": m.title or m.path,
            "type": m.content_type,
            "type_label": m.get_content_type_display(),
            "url": m.path,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "ctr": m.ctr,
            "position": m.position,
            "sessions": m.sessions,
            "page_views": m.page_views,
            "active_users": m.active_users,
            "bounce_pct": round(m.bounce_rate * 100, 1),
            "avg_duration_sec": round(m.avg_duration_sec),
            "keyword_count": len(m.keywords or []),
            "keywords": (m.keywords or [])[:50],
        } for m in metrics]
        # 表示回数の多い順
        rows.sort(key=lambda r: r["impressions"], reverse=True)

        context.update(
            snapshot=snap,
            rows=rows,
            fetched_at=localtime(snap.fetched_at),
            totals={
                "clicks": snap.total_clicks,
                "impressions": snap.total_impressions,
                "ctr": snap.avg_ctr,
                "position": snap.avg_position,
                "sessions": snap.total_sessions,
                "page_views": snap.total_page_views,
                "bounce_pct": round(snap.avg_bounce_rate * 100, 1),
                "pages": len(rows),
                "articles": sum(1 for r in rows if r["type"] == "article"),
            },
            history=list(ArticleMetricSnapshot.objects.order_by("-fetched_at")[:8]),
        )

    return render(request, "admin/seo/article_performance.html", context)
