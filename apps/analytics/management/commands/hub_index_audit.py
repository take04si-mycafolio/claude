"""ハブ配下(商品カテゴリ)記事のインデックス監査(編集長の週次工程・2026-09-07ユーザー指示)。

公開から --days 日(既定30)以上経っているのに Google にインデックスされていない記事を洗い出し、
編集長が「ペルソナから設計し直す全面リライト」に回すか、「カニバリの統合/分離(人判断)」に回すか、
「反映直後の様子見」にするかを判断できる材料を出す(判断そのものは編集長 desk.md 3d)。

対象 = ハブ(カテゴリページ /dryer/ /hair-iron/ 等)からリンクされる記事 = Article.product_type が
商品カテゴリ(コラム biyou / colam-ipan 以外)の公開記事。--all-categories でコラムも含める。

使い方:
    python manage.py hub_index_audit                       # 一覧(前回の index_status を使う)
    python manage.py hub_index_audit --refresh             # index_checked_at が7日超の対象を URL検査で更新してから一覧
    python manage.py hub_index_audit --refresh --stale-days 3
    python manage.py hub_index_audit --json                # 編集長がshellで扱う用
    python manage.py hub_index_audit --category hair-iron  # カテゴリ絞り込み

推奨アクション(action)の判定:
    watch      … 本文リライト反映から30日以内(再クロール待ち。判断しない)
    open_draft … 作業台に未完ドラフト(instructed/in_review)がある(実行中。二重投入しない)
    cannibal   … 同カテゴリの別記事と狙いが衝突(kw_conflict 同ロジック)→ 統合か分離かの人判断
    rewrite    … 上記に当たらない未インデックス → ペルソナ再設計の全面リライト候補
"""
import json
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import ArticleTriage, RewriteDraft, TriageRun
from apps.products.models import Article

from .kw_conflict import _norm_tokens

COLUMN_SLUGS = ("biyou", "colam-ipan")   # ハブを持たないコラム系(views.COLUMN_SLUGS と同じ)
NOT_INDEXED = ("crawled_not_indexed", "discovered_not_indexed", "unknown_to_google", "excluded")


def _cannibal_hits(article, siblings):
    """同カテゴリ内で、狙い(seo_keyword or タイトル)のトークンが包含関係にある別記事を返す。"""
    cand = _norm_tokens(article.seo_keyword or article.title)
    hits = []
    if not cand:
        return hits
    for s in siblings:
        if s.pk == article.pk:
            continue
        for text in (s.seo_keyword, s.meta_title or s.title):
            toks = _norm_tokens(text)
            if toks and (cand <= toks or toks <= cand):
                hits.append(s.slug)
                break
    return hits


class Command(BaseCommand):
    help = "ハブ配下記事のインデックス監査(公開30日超で未インデックスの記事を洗い出す)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="公開からの最低経過日数(既定30)")
        parser.add_argument("--refresh", action="store_true",
                            help="index_checked_at が --stale-days 超の対象を check_indexing で更新してから集計")
        parser.add_argument("--stale-days", type=int, default=7)
        parser.add_argument("--category", action="append", default=None, help="カテゴリslugで絞り込み(複数可)")
        parser.add_argument("--all-categories", action="store_true", help="コラム系(biyou/colam-ipan)も含める")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **opts):
        now = timezone.now()
        min_age = now - timedelta(days=opts["days"])
        qs = (Article.objects.filter(is_published=True, noindex=False, published_at__lte=min_age)
              .select_related("product_type"))
        if opts["category"]:
            qs = qs.filter(product_type__slug__in=opts["category"])
        elif not opts["all_categories"]:
            qs = qs.filter(product_type__isnull=False).exclude(product_type__slug__in=COLUMN_SLUGS)
        articles = list(qs.order_by("product_type__slug", "-published_at"))

        # 1) 必要なら URL検査で index_status を更新(1req/秒。対象は古いものだけ)
        if opts["refresh"]:
            stale_cut = now - timedelta(days=opts["stale_days"])
            stale = [a.slug for a in articles if not a.index_checked_at or a.index_checked_at < stale_cut]
            if stale:
                self.stderr.write(f"URL検査を更新: {len(stale)}件(index_checked_at が{opts['stale_days']}日超)")
                call_command("check_indexing", slug=stale)
                for a in articles:
                    a.refresh_from_db(fields=["index_status", "index_checked_at", "index_raw_status"])
            else:
                self.stderr.write("URL検査の更新対象なし(全件が期限内)")

        # 2) 補助データ: 最新トリアージの表示/クリック、未完ドラフト
        run = TriageRun.objects.order_by("-id").first()
        tri = {}
        if run:
            for t in ArticleTriage.objects.filter(run=run, article__isnull=False):
                tri[t.article_id] = t
        open_drafts = {}
        for d in RewriteDraft.objects.filter(status__in=["instructed", "in_review"]).select_related("article"):
            open_drafts.setdefault(d.article_id, []).append(d.id)

        by_cat = {}
        for a in articles:
            by_cat.setdefault(a.product_type.slug if a.product_type else "none", []).append(a)

        rows = []
        for a in articles:
            cat = a.product_type.slug if a.product_type else "none"
            indexed = a.index_status == "indexed"
            t = tri.get(a.pk)
            recently_rewritten = bool(a.last_rewritten_at and a.last_rewritten_at > now - timedelta(days=30))
            cann = _cannibal_hits(a, by_cat.get(cat, [])) if not indexed else []
            if indexed:
                action = "ok"
            elif a.pk in open_drafts:
                action = "open_draft"
            elif recently_rewritten:
                action = "watch"
            elif cann:
                action = "cannibal"
            else:
                action = "rewrite"
            rows.append({
                "slug": a.slug, "category": cat, "title": a.title,
                "published_at": a.published_at.date().isoformat() if a.published_at else None,
                "age_days": (now - a.published_at).days if a.published_at else None,
                "last_rewritten_at": a.last_rewritten_at.date().isoformat() if a.last_rewritten_at else None,
                "index_status": a.index_status,
                "index_raw_status": (a.index_raw_status or "")[:60],
                "index_checked_at": a.index_checked_at.date().isoformat() if a.index_checked_at else None,
                "impressions_28d": t.impressions if t else 0,
                "clicks_28d": t.clicks if t else 0,
                "avg_position": round(t.avg_position, 1) if (t and t.avg_position) else None,
                "seo_keyword": a.seo_keyword or "",
                "cannibal_with": cann,
                "open_drafts": open_drafts.get(a.pk, []),
                "action": action,
            })

        summary = {}
        for r in rows:
            s = summary.setdefault(r["category"], {"total": 0, "indexed": 0, "not_indexed": 0,
                                                   "rewrite": 0, "cannibal": 0, "watch": 0, "open_draft": 0})
            s["total"] += 1
            if r["action"] == "ok":
                s["indexed"] += 1
            else:
                s["not_indexed"] += 1
                s[r["action"]] += 1

        if opts["json"]:
            self.stdout.write(json.dumps({"checked_at": now.isoformat(), "min_age_days": opts["days"],
                                          "summary": summary, "rows": rows}, ensure_ascii=False))
            return

        self.stdout.write(f"# ハブ配下記事 インデックス監査(公開{opts['days']}日超・{len(rows)}本)\n")
        self.stdout.write("| カテゴリ | 対象 | indexed | 未 | rewrite候補 | カニバリ | 様子見 | 作業中 |")
        self.stdout.write("|---|---|---|---|---|---|---|---|")
        for cat, s in summary.items():
            self.stdout.write(f"| {cat} | {s['total']} | {s['indexed']} | {s['not_indexed']} | {s['rewrite']} | "
                              f"{s['cannibal']} | {s['watch']} | {s['open_draft']} |")
        self.stdout.write("\n## 未インデックス一覧(action順: rewrite → cannibal → watch → open_draft)")
        order = {"rewrite": 0, "cannibal": 1, "watch": 2, "open_draft": 3}
        for r in sorted((r for r in rows if r["action"] != "ok"),
                        key=lambda r: (order[r["action"]], r["category"], -(r["impressions_28d"] or 0))):
            extra = ""
            if r["cannibal_with"]:
                extra = " 衝突: " + ", ".join(f"/{s}/" for s in r["cannibal_with"])
            if r["open_drafts"]:
                extra += " Draft#" + ",".join(map(str, r["open_drafts"]))
            self.stdout.write(
                f"- [{r['action']}] /{r['slug']}/ ({r['category']}) {r['index_status']} "
                f"| 公開{r['age_days']}日 | 本文反映 {r['last_rewritten_at'] or '-'} "
                f"| 28日 表示{r['impressions_28d']}/クリック{r['clicks_28d']} | 狙い「{r['seo_keyword']}」{extra}")
