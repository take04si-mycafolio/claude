"""新規テーマの狙いクエリが既存記事とバッティングしないか検査する(LLM不使用・読み取りのみ)。

カニバリ防止(2026-09-06ユーザー指示)。照合は3層:
  1. Article.seo_keyword / meta_title / title … 既存記事が「狙っている」キーワード
  2. 進行中RewriteDraft(status=applied以外の作業中+観測中applied)の target_grow / target_keep
     … いま押し上げ中・維持中のクエリ
  3. 最新TriageRunのArticleTriage.queries … Googleが実際にそのクエリを割り当てているURL
     (順位30位以内なら「既に受け皿がある」とみなす)

判定:
  - CONFLICT: トークン集合が包含関係(candidate⊆existing または existing⊆candidate)
              または triage実績で30位以内の受けURLがある
  - NEAR    : トークンの過半が一致(2語中1語などは除く) … 人/編集長の判断材料
  - CLEAR   : 衝突なし

使い方:
    python manage.py kw_conflict --query "くるくるドライヤー おすすめ"
    python manage.py kw_conflict --query "A" --query "B" --json
"""
import json
import re

from django.core.management.base import BaseCommand

from apps.analytics.models import ArticleTriage, RewriteDraft, TriageRun
from apps.products.models import Article


def _norm_tokens(s):
    s = (s or "").replace("　", " ").lower()
    s = re.sub(r"[|｜/／・、。「」【】\[\]()（）:：〜~-]", " ", s)
    return frozenset(t for t in s.split() if t)


def _overlap(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def check_query(query):
    """1クエリの衝突判定。{verdict, hits:[{kind, slug, detail}]} を返す。"""
    cand = _norm_tokens(query)
    hits = []

    # 1) 既存記事の明示ターゲット(seo_keyword)とタイトル
    for a in Article.objects.filter(is_published=True).only(
            "slug", "title", "seo_keyword", "meta_title"):
        for kind, text in (("seo_keyword", a.seo_keyword),
                           ("title", a.meta_title or a.title)):
            toks = _norm_tokens(text)
            if not toks:
                continue
            if cand <= toks or toks <= cand:
                hits.append({"kind": f"article_{kind}", "slug": a.slug,
                             "detail": text[:80], "level": "conflict"})
            elif _overlap(cand, toks) >= 0.67 and len(cand) >= 2:
                hits.append({"kind": f"article_{kind}", "slug": a.slug,
                             "detail": text[:80], "level": "near"})

    # 2) 進行中リライトの grow / keep
    active = RewriteDraft.objects.exclude(status="rejected").select_related("article")
    for d in active:
        for field in ("target_grow", "target_keep"):
            for q in (getattr(d, field) or []):
                qs = q.get("query", "") if isinstance(q, dict) else str(q)
                toks = _norm_tokens(qs)
                if not toks:
                    continue
                if cand <= toks or toks <= cand:
                    hits.append({"kind": f"draft_{field}", "slug": d.article.slug,
                                 "detail": f"#{d.id} {qs}", "level": "conflict"})

    # 3) トリアージ実績: 既にこのクエリを受けているURL(30位以内)
    run = TriageRun.objects.order_by("-id").first()
    if run:
        cand_exact = " ".join(sorted(cand))
        for t in ArticleTriage.objects.filter(run=run).select_related("article"):
            # article は null 許容(商品ページ・トップ等の記事以外URL)。その場合は url を識別子にする
            slug = t.article.slug if t.article_id and t.article else (t.url or f"triage#{t.id}")
            for q in (t.queries or []):
                if not isinstance(q, dict):
                    continue
                toks = _norm_tokens(q.get("query", ""))
                if " ".join(sorted(toks)) == cand_exact:
                    pos = q.get("position")
                    level = "conflict" if (pos is not None and pos <= 30) else "near"
                    hits.append({"kind": "triage", "slug": slug,
                                 "detail": f"{q.get('query')} {round(pos,1) if pos else '?'}位",
                                 "level": level})

    # 重複除去(同一slug×kindは最初のみ)
    seen, uniq = set(), []
    for h in hits:
        k = (h["kind"], h["slug"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(h)

    if any(h["level"] == "conflict" for h in uniq):
        verdict = "CONFLICT"
    elif uniq:
        verdict = "NEAR"
    else:
        verdict = "CLEAR"
    return {"query": query, "verdict": verdict, "hits": uniq}


class Command(BaseCommand):
    help = "新規テーマの狙いクエリが既存記事とバッティングしないか検査する(カニバリ防止)"

    def add_arguments(self, parser):
        parser.add_argument("--query", action="append", required=True)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **opts):
        results = [check_query(q) for q in opts["query"]]
        if opts["json"]:
            self.stdout.write(json.dumps(results, ensure_ascii=False))
            return
        for r in results:
            mark = {"CONFLICT": "🛑", "NEAR": "⚠️", "CLEAR": "✅"}[r["verdict"]]
            self.stdout.write(f'{mark} {r["verdict"]}: {r["query"]}')
            for h in r["hits"][:6]:
                s = h["slug"]
                ref = s if (s.startswith("http") or s.startswith("/")) else f"/{s}/"
                self.stdout.write(f'    [{h["level"]}] {h["kind"]} {ref} {h["detail"]}')
