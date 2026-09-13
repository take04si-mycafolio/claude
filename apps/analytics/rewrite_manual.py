"""
リライト作業台(RewriteDraft)への手動追加。

GSCトリアージ由来でない任意の記事を、基準記事(お手本)を設定した上で作業台に入れる。
指示書生成は make_rewrite_instructions と同じ決定論ロジック(_build)を再利用し、LLMは呼ばない。
GSCデータ(ArticleTriage)がその記事にあれば流用し、無ければ空のポートフォリオで開始する。

管理コマンド add_rewrite_draft と admin の「手動で記事を追加」ボタンが共通で使う。
"""
from __future__ import annotations

from types import SimpleNamespace

from django.utils import timezone

from apps.analytics.models import RewriteDraft, ArticleTriage, PlaybookRule
from apps.analytics.management.commands.make_rewrite_instructions import (
    Command as _MakeCmd,
    extract_self_outline,
)

# 未完扱い（この状態の下書きが既にあれば、force なしでは重複追加しない）
ACTIVE_STATUSES = ("pending", "instructed", "in_review", "drafting", "approved")


class ManualRewriteError(Exception):
    """手動追加の失敗（重複など）。呼び出し側でメッセージ表示に使う。"""


def _reference_block(ref) -> str:
    """基準記事(お手本)の見出し構成を指示書冒頭に差し込むブロックを作る。"""
    outline = extract_self_outline(ref.content or "")
    h2 = outline.get("h2") or []
    lines = "\n".join(f"    - {h}" for h in h2) or "    （見出しなし）"
    return (
        "★★ 基準記事（お手本）★★\n"
        f"■ この記事を「{ref.title}」(/{ref.slug}/) の構成・情報粒度・トーンを基準に再構築する。\n"
        "■ 基準記事の見出し構成（H2）:\n"
        f"{lines}\n"
        "■ 使い方: 上の構成・水準・結論の出し方を手本にしつつ、対象記事のテーマに即して作り直す。"
        "基準記事の文章はコピーしない（写すのは構造・粒度・トーン）。target_keep のクエリは毀損しない。\n"
        "─────────────────────────────\n"
    )


def _synthetic_triage(article):
    """GSCデータが無い記事用の、_build が要求する最小限の擬似トリアージ。"""
    return SimpleNamespace(
        article=article,
        bucket="quick_win",          # needs_work 専用処理を避ける（意図判定は手動で足せる）
        best_query="",
        best_query_position=None,
        best_query_impressions=0,
        impressions=0,
        queries=[],
    )


def _norm_keywords(keywords):
    """改行/カンマ区切りの入力を正規化（重複除去・順序保持）。"""
    if isinstance(keywords, str):
        raw = keywords.replace("\r", "\n").replace(",", "\n").split("\n")
    else:
        raw = list(keywords or [])
    out, seen = [], set()
    for k in raw:
        k = (k or "").strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def build_manual_payload(article, reference_article=None, keywords=None):
    """指示書・チェックリスト・ポートフォリオ等を決定論生成して返す（DB書き込みなし）。

    keywords（手入力の狙うクエリ）があれば、先頭を主クエリ(grow)としてタイトル/導入の
    キーワード一致指示が入るように種を与える。GSCの既存クエリ(keep保護用)は保持する。
    keywords が無ければ、その記事の最新 ArticleTriage があればそれを、無ければ空で開始。

    返り値: (meta, instructions, checklist, refs, portfolio, keep, grow)
      meta = {"target_query", "src_best_position", "src_impressions"}
    """
    kws = _norm_keywords(keywords)
    triage = (ArticleTriage.objects.filter(article=article)
              .select_related("run").order_by("-run__fetched_at").first())

    if kws:
        base_q = list(triage.queries) if (triage and triage.queries) else []
        existing = {q.get("query") for q in base_q}
        base_q = base_q + [
            {"query": k, "position": None, "impressions": 0, "clicks": 0}
            for k in kws if k not in existing]
        src = SimpleNamespace(
            article=article,
            bucket=(triage.bucket if triage else "quick_win"),
            best_query=kws[0],
            best_query_position=None,
            best_query_impressions=0,
            impressions=(triage.impressions if triage else 0),
            queries=base_q,
        )
    elif triage is not None:
        src = triage
    else:
        src = _synthetic_triage(article)

    cmd = _MakeCmd()
    rules = list(PlaybookRule.objects.filter(is_active=True).order_by("priority"))
    instr, checklist, refs, portfolio, keep, grow = cmd._build(src, rules)

    if reference_article is not None:
        instr = _reference_block(reference_article) + instr

    meta = {
        "target_query": (src.best_query or ""),
        "src_best_position": getattr(src, "best_query_position", None),
        "src_impressions": getattr(src, "impressions", 0) or 0,
    }
    return meta, instr, checklist, refs, portfolio, keep, grow


def create_manual_rewrite_draft(article, reference_article=None, force=False,
                                keywords=None):
    """記事を手動で作業台に追加し、instructed 状態の RewriteDraft を返す。

    - 同一記事に未完の下書きがあれば force=False で ManualRewriteError。
    - keywords（手入力の狙うクエリ）を指定すると grow/portfolio/指示書に反映する。
    - keywords 未指定なら最新 ArticleTriage があれば query_portfolio/keep/grow に流用する。
    - source_triage は常に None（次回トリアージの掃除で消えないように is_manual=True で保護）。
    """
    if article is None:
        raise ManualRewriteError("記事が指定されていません。")
    if reference_article is not None and reference_article.pk == article.pk:
        raise ManualRewriteError("基準記事に対象記事と同じ記事は指定できません。")

    if not force and RewriteDraft.objects.filter(
            article=article, status__in=ACTIVE_STATUSES).exists():
        raise ManualRewriteError(
            f"/{article.slug}/ には未完のリライト下書きが既にあります"
            "（force で新規作成できます）。")

    meta, instr, checklist, refs, portfolio, keep, grow = build_manual_payload(
        article, reference_article, keywords=keywords)

    rd = RewriteDraft.objects.create(
        article=article,
        source_triage=None,
        is_manual=True,
        reference_article=reference_article,
        target_query=meta["target_query"],
        src_best_position=meta["src_best_position"],
        src_impressions=meta["src_impressions"],
        status="instructed",
        instructions=instr,
        checklist=checklist,
        playbook_refs=refs,
        instructed_at=timezone.now(),
        query_portfolio=portfolio,
        target_keep=keep,
        target_grow=grow,
    )
    return rd
