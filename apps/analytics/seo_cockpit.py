"""記事SEOコックピット（管理画面の統合ビュー）。

散らばっていた GSCトリアージ / リライト作業台 / 効果測定 / 記事メトリクスを
「記事」を軸に1画面へ統合する。上位表示までの管理を1記事1行で追えるようにする。

- 一覧: 全記事 × 最新トリアージ × リライト状態 × 次のアクション
- 詳細: 順位・表示のrun横断トレンド、獲得クエリ、リライト履歴と効果測定

データ取得は run_gsc_triage / measure_rewrites（cron・root実行）が担い、
このモジュールは読み取りのみ。LLM・外部APIは呼ばない。
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from apps.products.models import Article

from .models import ArticleTriage, RewriteDraft, TriageRun

# 反映後この日数までは順位判定をしない（観測期間）
OBSERVATION_DAYS = 21

BUCKET_LABELS = {
    "quick_win": "あと一歩",
    "needs_work": "意図ズレ",
    "performing": "上位安定",
    "dead": "圏外",
}

DRAFT_WORKING_STATUSES = ("pending", "instructed", "drafting", "in_review", "approved")


def _action_for(article, triage, draft, days_since_applied):
    """1記事の「次のアクション」を決定論で導出する。(重要度, ラベル, css種別)"""
    if not article.is_published:
        return (90, "非公開", "muted")
    if article.noindex:
        return (80, "noindex中", "muted")
    if draft and draft.status in DRAFT_WORKING_STATUSES:
        return (10, f"作業中: {draft.get_status_display()}", "work")
    if draft and draft.status == "applied" and days_since_applied is not None:
        if days_since_applied < OBSERVATION_DAYS:
            return (30, f"観測中 残{OBSERVATION_DAYS - days_since_applied}日", "observe")
        if draft.keep_damaged:
            return (5, "keep毀損の確認", "bad")
        if draft.eval_status == "declined":
            return (6, "悪化: 原因確認", "bad")
        if draft.eval_status in ("improved", "reached_p1"):
            return (50, "改善: 維持", "good")
    if triage is None:
        return (60, "次回トリアージ待ち", "muted")
    if triage.bucket == "quick_win":
        return (1, "リライト最優先", "hot")
    if triage.bucket == "needs_work":
        return (2, "検索意図の見直し", "warn")
    if triage.bucket == "performing":
        return (40, "維持・毀損監視", "good")
    return (20, "テコ入れ/統合検討", "warn")


def _build_rows(latest_run):
    articles = (Article.objects
                .select_related("product_type")
                .order_by("-updated_at"))

    triage_by_article = {}
    prev_by_article = {}
    if latest_run:
        for t in latest_run.articles.filter(article__isnull=False):
            triage_by_article[t.article_id] = t
        prev_run = (TriageRun.objects
                    .exclude(pk=latest_run.pk)
                    .order_by("-fetched_at")
                    .first())
        if prev_run:
            for t in prev_run.articles.filter(article__isnull=False):
                prev_by_article[t.article_id] = t

    # 記事ごとの最新ドラフト（created_at昇順で回して上書き→最後が最新）
    draft_by_article = {}
    for d in RewriteDraft.objects.order_by("created_at"):
        draft_by_article[d.article_id] = d

    from django.utils import timezone
    now = timezone.now()

    rows = []
    for a in articles:
        t = triage_by_article.get(a.pk)
        d = draft_by_article.get(a.pk)
        days_since_applied = None
        if d and d.applied_at:
            days_since_applied = (now - d.applied_at).days
        prio, action, action_kind = _action_for(a, t, d, days_since_applied)

        pos = t.best_query_position if t else None
        prev_t = prev_by_article.get(a.pk)
        prev_pos = prev_t.best_query_position if prev_t else None
        delta = None
        if pos is not None and prev_pos is not None:
            delta = round(prev_pos - pos, 1)  # 正=上昇

        rows.append({
            "id": a.pk,
            "title": a.title,
            "slug": a.slug,
            "url": a.get_absolute_url(),
            "category": a.product_type.name if a.product_type else "",
            "published": a.is_published,
            "noindex": a.noindex,
            "bucket": t.bucket if t else "",
            "bucket_label": BUCKET_LABELS.get(t.bucket, "—") if t else "—",
            "impressions": t.impressions if t else 0,
            "clicks": t.clicks if t else 0,
            "ctr": round(t.ctr, 1) if t else 0.0,
            "position": round(pos, 1) if pos is not None else None,
            "delta": delta,
            "best_query": t.best_query if t else "",
            "num_queries": t.num_queries if t else 0,
            "draft_id": d.pk if d else None,
            "draft_status": d.get_status_display() if d else "",
            "working": bool(d and d.status in DRAFT_WORKING_STATUSES),
            "eval_status": (d.get_eval_status_display()
                            if d and d.status == "applied" else ""),
            "keep_damaged": bool(d.keep_damaged) if d else False,
            "days_since_applied": days_since_applied,
            "action": action,
            "action_kind": action_kind,
            "priority": prio,
        })
    return rows


@staff_member_required
def cockpit(request):
    latest_run = TriageRun.objects.order_by("-fetched_at").first()
    rows = _build_rows(latest_run)

    live = [r for r in rows if r["published"] and not r["noindex"]]
    counts = {
        "total": len(live),
        "quick_win": sum(1 for r in live if r["bucket"] == "quick_win"),
        "needs_work": sum(1 for r in live if r["bucket"] == "needs_work"),
        "performing": sum(1 for r in live if r["bucket"] == "performing"),
        "dead": sum(1 for r in live if r["bucket"] == "dead"),
        "working": sum(1 for r in rows if r["action_kind"] == "work"),
        "observing": sum(1 for r in rows if r["action_kind"] == "observe"),
        "alerts": sum(1 for r in rows if r["action_kind"] == "bad"),
    }
    rows.sort(key=lambda r: (r["priority"], -r["impressions"]))
    return render(request, "admin/seo/cockpit.html", {
        "run": latest_run,
        "rows": rows,
        "counts": counts,
    })


@staff_member_required
def cockpit_to_workbench(request, article_id):
    """コックピットから記事を作業台（RewriteDraft）へ乗せ、作業画面に遷移する。

    - 未完の下書きが既にあればそれを開く（重複作成しない）
    - 無ければ手動追加と同じ経路（create_manual_rewrite_draft）で
      指示書生成済み(instructed)の下書きを作って開く
    """
    article = get_object_or_404(Article, pk=article_id)
    detail_url = f"/admin/seo/cockpit/{article.pk}/"
    if request.method != "POST":
        return HttpResponseRedirect(detail_url)

    existing = (RewriteDraft.objects
                .filter(article=article, status__in=DRAFT_WORKING_STATUSES)
                .order_by("-created_at")
                .first())
    if existing:
        messages.info(request, f"/{article.slug}/ は既に作業台にあります（下書き #{existing.pk}）。")
        return HttpResponseRedirect(
            f"/admin/analytics/rewritedraft/{existing.pk}/change/")

    from .rewrite_manual import ManualRewriteError, create_manual_rewrite_draft
    try:
        rd = create_manual_rewrite_draft(article)
    except ManualRewriteError as e:
        messages.error(request, f"作業台への追加に失敗: {e}")
        return HttpResponseRedirect(detail_url)

    messages.success(
        request, f"✅ コックピットから作業台に追加: /{article.slug}/（指示書生成済）")
    return HttpResponseRedirect(f"/admin/analytics/rewritedraft/{rd.pk}/change/")


@staff_member_required
def cockpit_article(request, article_id):
    article = get_object_or_404(
        Article.objects.select_related("product_type"), pk=article_id)

    # run横断トレンド（古い順）
    trend = []
    triages = (ArticleTriage.objects
               .filter(article=article)
               .select_related("run")
               .order_by("run__fetched_at"))
    for t in triages:
        trend.append({
            "period": f"{t.run.period_start:%m/%d}〜{t.run.period_end:%m/%d}",
            "fetched": t.run.fetched_at,
            "bucket": t.bucket,
            "bucket_label": BUCKET_LABELS.get(t.bucket, t.bucket),
            "impressions": t.impressions,
            "clicks": t.clicks,
            "ctr": round(t.ctr, 1),
            "best_query": t.best_query,
            "position": (round(t.best_query_position, 1)
                         if t.best_query_position is not None else None),
            "avg_position": round(t.avg_position, 1) if t.avg_position else None,
            "num_queries": t.num_queries,
        })

    latest_triage = triages.last()
    queries = (latest_triage.queries or [])[:40] if latest_triage else []

    drafts = (article.rewrite_drafts
              .select_related("source_triage")
              .order_by("-created_at"))
    draft_rows = []
    for d in drafts:
        gap = getattr(d, "content_gap", None)
        draft_rows.append({
            "d": d,
            "gap_status": gap.get_status_display() if gap else "",
            "keep_count": len(d.target_keep or []),
            "grow_count": len(d.target_grow or []),
        })

    # 折れ線用の座標（順位は小さいほど上に）
    chart = None
    points = [t for t in trend if t["position"] is not None]
    if len(points) >= 2:
        w, h, pad = 640, 180, 24
        positions = [t["position"] for t in points]
        lo, hi = min(positions), max(positions)
        span = (hi - lo) or 1.0
        step = (w - 2 * pad) / (len(points) - 1)
        coords = []
        for i, t in enumerate(points):
            x = pad + i * step
            y = pad + (t["position"] - lo) / span * (h - 2 * pad)
            coords.append({"x": round(x, 1), "y": round(y, 1),
                           "ly": round(y - 8, 1),
                           "label": t["period"], "pos": t["position"]})
        chart = {"w": w, "h": h, "coords": coords,
                 "path": " ".join(f'{c["x"]},{c["y"]}' for c in coords),
                 "lo": lo, "hi": hi}

    working_draft = next(
        (r["d"] for r in draft_rows if r["d"].status in DRAFT_WORKING_STATUSES), None)

    return render(request, "admin/seo/cockpit_article.html", {
        "article": article,
        "working_draft": working_draft,
        "trend": trend,
        "latest": latest_triage,
        "queries": queries,
        "draft_rows": draft_rows,
        "chart": chart,
        "observation_days": OBSERVATION_DAYS,
    })
