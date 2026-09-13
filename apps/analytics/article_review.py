"""記事レビューページ（承認前の記事に修正指示を書き込む画面・2026-09-08新設）。

承認センターから各記事の「✏️ レビュー」で開く。人がやることは3つだけ:
  1. 本文を読み、直してほしい箇所をマウスで選択する
  2. 「ここを修正」で指示を書く（種類を選ぶ＝学習の集計軸になる）
  3. 「担当に差し戻す」で担当AI社員へ戻す

差し戻すと対象は承認キューから外れ、検品記録（qa）も消えるので、
担当AIの修正 → 検品担当の再検品 → 承認キュー再掲、という既存の流れに戻る。
新しい反映経路はここに作らない（承認・反映は approval_center のまま）。

修正指示は EditorNote に残り、learning.build_editor_note_digest() 経由で
指示書へ還流する（同じ指摘を繰り返さないための学習）。
"""

import json
import re
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import (ArticleWorkLog, EditorNote, RewriteDraft, WorkReport,
                     log_article_work)

_PV2_QUEUE_DIR = Path("/opt/claude-ops/agents/product_v2_queue")
# 差し戻しをここに置くと、5分おきの dispatch_revision.sh が担当AIを即起動する
_TRIGGER_DIR = Path("/opt/claude-ops/agents/triggers")
_RESEARCH_REQ_DIR = Path("/opt/claude-ops/agents/research_requests")

# 差し戻し先（kind → 担当AI社員キー）
# 人の差し戻しの修正対応は、種別を問わず「なお姉」が兼任する（2026-09-08 ユーザー指示）。
# 失敗した記事を立て直すのが元々の役目で、修正対応と地続きのため。
ASSIGNEE_FOR_KIND = {
    "rewrite": "followup",
    "article": "followup",
    "product_v2": "followup",
}
_AGENT_LABEL = {
    "writer": "新規執筆担当（ふみちゃん）",
    "product_writer": "商品記事v2担当（アズ）",
    "followup": "修正対応担当（なお姉）",
    "qa": "検品担当（リン様）",
}

_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_SHORTCODE_RE = re.compile(r"\[(product|card|related|survey|spec_table)\b[^\]]*\]")


def _safe_body(html):
    """レビュー表示用に本文を整える。

    - <script>/<style> は画面が壊れるので中身ごと除去（本文にstyleを入れない方針）
    - ショートコードは展開せず、そこに何が入るかが分かるバッジにして見せる
      （展開すると引用位置とDB本文の対応が取れなくなるため）
    """
    s = _SCRIPT_RE.sub("", html or "")
    return _SHORTCODE_RE.sub(
        lambda m: f'<span class="sc-badge">{m.group(0)}</span>', s)


def _pv2_entry(product_pk):
    """商品記事v2キューの JSON を（ファイル, データ）で返す。"""
    if not _PV2_QUEUE_DIR.exists():
        return None, None
    for f in sorted(_PV2_QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if data.get("product_pk") == product_pk:
            return f, data
    return None, None


def _load_target(kind, obj_id):
    """レビュー対象を種別によらない共通の形に読み出す。"""
    if kind == "rewrite":
        d = (RewriteDraft.objects.select_related("article")
             .filter(id=obj_id).first())
        if not d:
            return None
        return {
            "obj": d,
            "title": (d.draft_title or "").strip() or d.article.title,
            "slug": d.article.slug,
            "body": d.draft_content or "",
            "meta": "",
            "sub": f"リライト案 #{d.id} ／ 現行記事 /{d.article.slug}/",
            "qa": d.qa_result or {},
            "detail_url": f"/admin/analytics/rewritedraft/{d.id}/change/",
            "live_url": f"/{d.article.slug}/",
            "in_queue": d.status == "in_review",
        }
    if kind == "article":
        from apps.products.models import Article
        a = Article.objects.filter(id=obj_id).first()
        if not a:
            return None
        return {
            "obj": a,
            "title": a.title,
            "slug": a.slug,
            "body": a.content or "",
            "meta": a.meta_description or "",
            "sub": f"新規記事（{'公開中' if a.is_published else '未公開'}）",
            "qa": (a.seo_check_result or {}).get("qa") or {},
            "detail_url": f"/admin/products/article/{a.id}/change/",
            "live_url": f"/{a.slug}/",
            "in_queue": not a.is_published,
        }
    if kind == "product_v2":
        from apps.products.models import Product
        p = Product.objects.filter(pk=obj_id).first()
        f, data = _pv2_entry(obj_id)
        if not p or not f:
            return None
        try:
            draft = Path(data["draft_path"]).read_text(encoding="utf-8")
        except (OSError, KeyError):
            draft = ""
        return {
            "obj": p,
            "title": data.get("meta_title") or data.get("title") or p.name,
            "slug": p.slug,
            "body": draft,
            "meta": data.get("meta_description", ""),
            "sub": "商品記事v2（下書き・未反映）",
            "qa": data.get("qa") or {},
            "detail_url": data.get("preview_url", "") or p.get_absolute_url(),
            "live_url": p.get_absolute_url(),
            "in_queue": True,
        }
    return None


def _request_agent_run(assignee, kind, obj_id, target, notes):
    """担当AIを即起動するための依頼ファイルを置く（cronの定期枠を待たない）。

    アプリからプロセスを起動はしない（gunicorn は deploy 実行・エージェントは root 実行）。
    JSON を1枚置くだけにして、実行は root の dispatch_revision.sh（5分おき）に任せる。
    置けなくても差し戻し自体は成立するので、失敗しても止めない（次の定期枠で拾われる）。
    """
    payload = {
        "assignee": assignee, "kind": kind, "target_id": obj_id,
        "slug": target["slug"], "title": target["title"],
        "note_ids": [n.id for n in notes],
        "requested_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        _TRIGGER_DIR.mkdir(parents=True, exist_ok=True)
        f = _TRIGGER_DIR / f"{assignee}-{kind}-{obj_id}.json"
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _send_back(request, kind, obj_id, target, notes):
    """対象を承認キューから外して担当AIへ差し戻す。

    検品記録(qa)を消すのは「修正したら必ずもう一度検品を通す」ため
    （検品ゲート: approval_center._qa_ok）。
    """
    assignee = ASSIGNEE_FOR_KIND.get(kind, "")
    if kind == "rewrite":
        d = target["obj"]
        d.status = "drafting"
        d.qa_result = {}
        d.save(update_fields=["status", "qa_result"])
    elif kind == "article":
        a = target["obj"]
        res = dict(a.seo_check_result or {})
        res.pop("qa", None)
        res["revision_requested_at"] = timezone.now().strftime("%Y-%m-%d %H:%M")
        a.seo_check_result = res
        if a.is_published:
            # 公開中の記事は落とさない（読者に見えている記事を消さない）。
            a.save(update_fields=["seo_check_result"])
        else:
            a.save(update_fields=["seo_check_result"])
    elif kind == "product_v2":
        f, data = _pv2_entry(obj_id)
        if f:
            data.pop("qa", None)
            data["revision_requested_at"] = timezone.now().strftime("%Y-%m-%d %H:%M")
            try:
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")
            except OSError as e:
                # 典型例: root の cron が書いたJSONが root 所有のままで、
                # deploy 実行の gunicorn から書けない（所有者は deploy:www-data・664）。
                messages.error(
                    request,
                    f"キューJSONを更新できませんでした（{e.strerror}: {f}）。"
                    "ファイルの所有者と権限を確認してください（deploy:www-data / 664）。"
                    "書き込んだ修正指示は保存されているので、直してからもう一度"
                    "「差し戻す」を押してください。")
                return

    now = timezone.now()
    for n in notes:
        n.assignee = assignee
        n.sent_back_at = now
        n.save(update_fields=["assignee", "sent_back_at"])

    lines = [f"対象: /{target['slug']}/ {target['title']}",
             f"種別: {dict(EditorNote.KIND_CHOICES).get(kind, kind)}",
             f"レビュー画面: /admin/approvals/review/{kind}/{obj_id}/", "",
             "## 修正指示"]
    for i, n in enumerate(notes, 1):
        lines.append(f"### {i}. [{n.get_category_display()}] (note#{n.id})")
        if n.quote:
            lines.append(f"> 該当箇所: {n.quote[:300]}")
        lines.append(n.comment)
        lines.append("")
    lines.append("## 担当の対応方法")
    lines.append("0. この差し戻しで dispatch_revision.sh が起動します"
                 "（revision.md の手順で対応してください）")
    lines.append("1. `manage.py editor_notes` で自分宛の指示を確認する")
    lines.append("2. 指示どおり本文を修正し、6ゲート(check_draft.py)を全0にする")
    lines.append("3. `manage.py editor_notes --resolve <id> --note \"対応内容\" "
                 "--lesson \"次に活かす学び\"` で記録する")
    lines.append("4. 検品担当（リン様）の再検品を通ると承認センターに戻る")

    WorkReport.objects.create(
        title=f"修正指示（人）: /{target['slug']}/",
        status="warning",
        summary=f"{_AGENT_LABEL.get(assignee, assignee)}へ{len(notes)}件の修正指示を差し戻し",
        body="\n".join(lines),
    )
    log_article_work(
        kind, obj_id, target["slug"], "human", "sent_back",
        f"{_AGENT_LABEL.get(assignee, assignee)}へ{len(notes)}件の修正指示を差し戻し",
        detail="\n".join(f"- [{n.get_category_display()}] {n.comment.splitlines()[0][:120]}"
                          for n in notes))
    queued = _request_agent_run(assignee, kind, obj_id, target, notes)
    when = ("担当AIが数分以内に着手します" if queued
            else "担当AIは次回の定期起動で着手します")
    messages.success(
        request,
        f"✅ {_AGENT_LABEL.get(assignee, assignee)}へ{len(notes)}件の修正指示を差し戻しました"
        f"（{when}。承認キューからは一旦外れ、修正→再検品後に戻ります）")


_QA_ACTION = {"passed": "qa_passed", "fixed": "qa_fixed", "failed": "qa_failed"}


def _sync_worklogs(kind, obj_id, target, notes):
    """記録漏れを既存データ（検品記録・指示への対応記録）から補完する。

    履歴は「担当が自分で記録する」のが原則だが、記録し忘れても検品や修正の事実は
    別のところに残っている。人が履歴を見たときに実態と食い違わないよう、ここで埋める。
    """
    logs = list(ArticleWorkLog.objects.filter(kind=kind, target_id=obj_id))
    slug = target["slug"]
    qa = target.get("qa") or {}
    action = _QA_ACTION.get(qa.get("verdict"))
    if action:
        marker = f"[qa:{qa.get('date', '')}:{qa.get('verdict')}]"
        if not any(marker in (w.detail or "") for w in logs):
            log_article_work(kind, obj_id, slug, "qa", action,
                             (qa.get("notes") or "検品記録あり")[:300], detail=marker)
    for n in notes:
        if n.status != "fixed" or not n.resolution or not n.resolved_at:
            continue
        near = any(w.action == "revised"
                   and abs((w.created_at - n.resolved_at).total_seconds()) < 3600
                   for w in logs)
        if near:
            continue
        log_article_work(kind, obj_id, slug, n.assignee or "followup", "revised",
                         n.resolution[:300],
                         detail=f"[note:{n.id}]" + (f"\n学び: {n.lesson}" if n.lesson else ""))


def _missing_steps(worklogs):
    """工程が飛んでいないかの警告文（今回のような検品の空振りを見つけるため）。"""
    if not worklogs:
        return ["作業履歴がありません（どの工程も記録されていません）"]
    last_work = max((w.created_at for w in worklogs
                     if w.action in ("written", "revised")), default=None)
    last_qa = max((w.created_at for w in worklogs if w.agent == "qa"), default=None)
    out = []
    if last_work and (not last_qa or last_qa < last_work):
        out.append("最後の執筆・修正のあとに検品担当（リン様）の記録がありません"
                   "（検品が動いていない可能性）")
    if not last_work:
        out.append("執筆・修正の記録がありません")
    return out


def _progress(kind, obj_id, notes, target):
    """差し戻したあと、いまどこで止まっているのかを1行で返す（人が状態を追えるように）。"""
    open_notes = [n for n in notes if n.status == "open"]
    sent = [n for n in open_notes if n.sent_back_at]
    if (_RESEARCH_REQ_DIR / f"{kind}-{obj_id}.json").exists():
        return ("research", "🔍 リサーチ担当（しおりん）が調査中です。"
                "情報が揃うと修正担当が自動で再開します")
    if (_TRIGGER_DIR / f"followup-{kind}-{obj_id}.json").exists():
        return ("queued", "⏳ 差し戻し済み。数分以内に修正対応担当（なお姉）が着手します")
    if sent:
        when = max(n.sent_back_at for n in sent)
        return ("working", f"🛠 {when:%-m/%-d %H:%M} に差し戻し済み。"
                           f"修正対応担当（なお姉）が対応中です（未対応 {len(sent)}件）")
    if open_notes:
        return ("draft", f"✏️ 未送信の修正指示が {len(open_notes)}件 あります。"
                         "下の「差し戻す」を押すと担当AIに渡ります")
    if notes and not open_notes:
        qa = target.get("qa") or {}
        if qa.get("verdict") in ("passed", "fixed"):
            return ("done", "✅ 修正と検品が終わっています。承認センターの承認キューに戻っています")
        return ("qa", "🔍 修正は終わり、検品担当（リン様）の再検品待ちです")
    return ("none", "")


@never_cache          # 画面を直したのに古いHTMLがブラウザに残る事故を防ぐ
@staff_member_required
@require_http_methods(["GET", "POST"])
def article_review(request, kind, obj_id):
    if kind not in dict(EditorNote.KIND_CHOICES):
        raise Http404("不明な対象種別です")
    target = _load_target(kind, obj_id)
    if not target:
        raise Http404("レビュー対象が見つかりません")
    here = f"/admin/approvals/review/{kind}/{obj_id}/"

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "note_add":
            comment = (request.POST.get("comment") or "").strip()
            if not comment:
                messages.error(request, "修正指示が空です")
            else:
                EditorNote.objects.create(
                    kind=kind, target_id=obj_id, slug=target["slug"],
                    target_title=target["title"][:500],
                    quote=(request.POST.get("quote") or "").strip()[:2000],
                    comment=comment,
                    category=request.POST.get("category", "other"),
                    assignee=ASSIGNEE_FOR_KIND.get(kind, ""),
                )
                log_article_work(
                    kind, obj_id, target["slug"], "human", "note_added",
                    f"修正指示を記入: {comment.strip().splitlines()[0][:120]}")
                messages.success(request, "✅ 修正指示を追加しました")
        elif action == "note_delete":
            EditorNote.objects.filter(id=request.POST.get("note_id"),
                                      kind=kind, target_id=obj_id).delete()
            messages.info(request, "修正指示を削除しました")
        elif action == "send_back":
            notes = list(EditorNote.objects.filter(
                kind=kind, target_id=obj_id, status="open").order_by("id"))
            if not notes:
                messages.error(request, "差し戻す修正指示がありません")
            else:
                _send_back(request, kind, obj_id, target, notes)
        else:
            messages.error(request, "不正な操作です")
        return HttpResponseRedirect(here)

    notes = list(EditorNote.objects.filter(kind=kind, target_id=obj_id)
                 .order_by("status", "-created_at"))
    state, state_msg = _progress(kind, obj_id, notes, target)
    # この記事に誰が何をしたか（工程が飛んでいないかを人が確認できるように）
    _sync_worklogs(kind, obj_id, target, notes)
    worklogs = list(ArticleWorkLog.objects.filter(kind=kind, target_id=obj_id)
                    .order_by("created_at"))
    missing = _missing_steps(worklogs)
    qa = target.get("qa") or {}
    ctx = {
        "scores": qa.get("scores") or {},
        "worklogs": worklogs,
        "missing_steps": missing,
        "state": state,
        "state_msg": state_msg,
        "kind": kind,
        "kind_label": dict(EditorNote.KIND_CHOICES)[kind],
        "obj_id": obj_id,
        "t": target,
        "body_html": _safe_body(target["body"]),
        "notes": notes,
        "open_notes": [n for n in notes if n.status == "open"],
        "categories": EditorNote.CATEGORY_CHOICES,
        "assignee_label": _AGENT_LABEL.get(ASSIGNEE_FOR_KIND.get(kind, ""), "担当"),
        "chars": len(target["body"]),
    }
    return render(request, "admin/article_review.html", ctx)
