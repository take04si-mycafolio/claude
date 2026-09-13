"""承認センター（管理画面の統合承認ビュー）。

散らばっていた承認作業を1ページに集約する。AI社員体制（WorkReport id=403）では
人の作業がこのページのクリックだけで完結することを目指す。

集約する承認キュー:
- リライト作業台 (RewriteDraft status=in_review) … 承認反映 / 却下
- 口コミ (reviews.Review is_approved=False) … 承認（承認時にミッション達成判定が走る）
- ミッション特典 (accounts.UserMissionCompletion 承認待ち/準備中) … 承認してコード発行+メール
- アンケート自由記述 (surveys.SurveyResponse 公開待ち) … コメント公開
- 編集長からの判断待ち (DeskDecision status=open) … 選択肢で回答→編集長が計画へ反映

各承認は既存実装と同じ経路を通す（新しい承認ロジックをここに作らない）:
- リライト: apply_article_content（自動バックアップ + last_rewritten_at 更新）。
  /opt/claude-ops/drafts/{slug}_meta_revised.txt があれば meta_description も同時反映。
- 口コミ: 1件ずつ save(update_fields=["is_approved"])（ReviewAdmin.approve と同一）
- ミッション: accounts.missions.approve_completion + send_reward_code_email
"""

import json
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import CompletionStatus, UserMissionCompletion
from apps.products.management.commands.apply_draft import apply_article_content
from apps.reviews.models import Review
from apps.surveys.models import SurveyResponse

from .models import ArticleWorkLog, EditorNote, RewriteDraft, log_article_work

_BACKUP_DIR = "/home/deploy/app/backups"
_DRAFTS_DIR = Path("/opt/claude-ops/drafts")


def _meta_for(slug):
    """作業台フローで書き出された meta_description 下書きがあれば返す。"""
    p = _DRAFTS_DIR / f"{slug}_meta_revised.txt"
    if p.exists():
        text = p.read_text(encoding="utf-8").strip()
        if text:
            return text[:200]
    return None


# ---- 検品(リン様)ゲート: 公開・反映は必ず検品担当を通す(2026-09-08) ----------
# バッジ表示だけでは検品前でもクリックで公開できてしまい実際に素通りが起きたため、
# ここで物理的に止める。verdict が passed / fixed のものだけが「完成した記事」。

_QA_OK = ("passed", "fixed")


def _qa_ok(qa):
    return isinstance(qa, dict) and qa.get("verdict") in _QA_OK


def _qa_block(request, label, qa):
    """検品未了/NG を止めて理由を出す。呼び出し側は必ず return すること。"""
    if isinstance(qa, dict) and qa.get("verdict") == "failed":
        messages.error(
            request,
            f"🛑 {label} は検品担当(リン様)が『要差戻し』と判定しています"
            f"（{qa.get('notes', '理由未記録')}）。修正後に再検品してから反映してください。")
    else:
        messages.error(
            request,
            f"🛑 {label} はまだ検品担当(リン様)の検品を受けていないため公開・反映できません。"
            "検品は毎朝7:30の自動実行です（急ぐ場合は検品担当を手動起動してください）。")


def _approve_rewrite(request, draft_id):
    d = (RewriteDraft.objects.select_related("article")
         .filter(id=draft_id, status="in_review").first())
    if not d:
        messages.warning(request, f"リライト #{draft_id} は承認待ちではありません")
        return
    if not (d.draft_content or "").strip():
        messages.error(request, f"リライト #{d.id} は案本文が空のため反映できません")
        return
    if not _qa_ok(d.qa_result):
        _qa_block(request, f"リライト #{d.id}（/{d.article.slug}/）", d.qa_result)
        return
    title = (d.draft_title or "").strip() or None
    meta = _meta_for(d.article.slug)
    apply_article_content(
        d.article, content=d.draft_content, title=title, meta_title=title,
        meta=meta, backup_dir=_BACKUP_DIR,
        source=f"rewrite_draft#{d.id} (approval_center)")
    d.status = "applied"
    d.applied_at = timezone.now()
    d.save(update_fields=["status", "applied_at"])
    log_article_work("rewrite", d.id, d.article.slug, "human", "applied",
                     f"承認して /{d.article.slug}/ に反映（{len(d.draft_content)}字）")
    extra = "・meta同時反映" if meta else ""
    messages.success(
        request,
        f"✅ リライト #{d.id} を /{d.article.slug}/ に反映しました"
        f"（バックアップ取得済み{extra}）")
    _execute_pending_merges(request, d.article)


def _execute_pending_merges(request, dest_article):
    """統合先のリライト反映を合図に、予約済みの記事統合(ARTICLE_MERGES)を実行する(2026-09-14)。

    統合元を先に非公開にすると、統合先に内容が入る前に旧URLが301で飛んで中身が薄くなる。
    そこで「統合先に統合元の内容を取り込んだリライトが反映された時点」で統合元を非公開にする。
    """
    from django.core.management import call_command

    from apps.products.article_redirects import ARTICLE_MERGES
    from apps.products.models import Article

    from .models import DeskDecision

    sources = [src for src, dest in ARTICLE_MERGES.items() if dest == dest_article.slug]
    for src in Article.objects.filter(slug__in=sources, is_published=True):
        src.is_published = False
        src.save(update_fields=["is_published"])
        log_article_work("article", src.id, src.slug, "human", "applied",
                         f"統合を実行: 非公開にして /{dest_article.slug}/ へ301")
        try:
            call_command("notify_indexnow", url=[f"https://sc-tsusho.jp/{src.slug}/"])
        except Exception:
            pass
        for dd in DeskDecision.objects.filter(status="dev_pending", key__contains=src.slug):
            dd.status = "done"
            dd.handled_note += (f"\n{timezone.localtime():%m/%d %H:%M} 統合先 /{dest_article.slug}/ の反映に合わせて"
                                f" /{src.slug}/ を非公開にし、301と本文内参照の付け替えを有効にした")
            dd.handled_at = timezone.now()
            dd.save(update_fields=["status", "handled_note", "handled_at"])
        messages.info(request, f"🔀 予約していた統合を実行: /{src.slug}/ を非公開にし、"
                               f"/{dest_article.slug}/ へ301しました（他記事のリンクも統合先に付け替わります）")


def _reject_rewrite(request, draft_id):
    d = RewriteDraft.objects.filter(id=draft_id, status="in_review").first()
    if not d:
        messages.warning(request, f"リライト #{draft_id} は承認待ちではありません")
        return
    d.status = "rejected"
    d.save(update_fields=["status"])
    messages.info(request, f"リライト #{d.id} を却下しました")


def _approve_review(request, review_id):
    r = Review.objects.filter(id=review_id, is_approved=False, is_deleted=False).first()
    if not r:
        messages.warning(request, f"口コミ #{review_id} は承認待ちではありません")
        return
    # ReviewAdmin.approve と同じく1件ずつ save（承認時点でミッション達成判定が走る）
    r.is_approved = True
    r.is_rejected = False
    r.save(update_fields=["is_approved", "is_rejected"])
    messages.success(request, f"✅ 口コミ #{r.id}（{r.product}）を承認しました")


def _reject_review(request, review_id):
    """非承認=掲載しない(薬機法等の運営判断)。削除とは別で、adminから戻せる。"""
    r = Review.objects.filter(id=review_id, is_approved=False, is_deleted=False).first()
    if not r:
        messages.warning(request, f"口コミ #{review_id} は承認待ちではありません")
        return
    r.is_rejected = True
    r.save(update_fields=["is_rejected"])
    messages.info(
        request,
        f"口コミ #{r.id}（{r.product}）を非承認にしました（掲載されません・"
        "口コミ管理画面から承認待ちに戻せます）")


def _approve_mission(request, completion_id):
    from apps.accounts.missions import approve_completion, send_reward_code_email
    c = (UserMissionCompletion.objects.select_related("user", "mission")
         .filter(id=completion_id).first())
    if not c or c.status not in (CompletionStatus.WAITING, CompletionStatus.PENDING):
        messages.warning(request, f"ミッション達成 #{completion_id} は承認対象外です")
        return
    c = approve_completion(c)
    if c.status == CompletionStatus.PENDING:
        messages.warning(
            request,
            f"ミッション達成 #{c.id} を承認しましたが、コード不足のため準備中です"
            "（コード補充後にもう一度承認してください）")
        return
    try:
        sent = send_reward_code_email(c, request=request)
    except Exception:
        sent = False
    if sent:
        messages.success(request, f"✅ ミッション達成 #{c.id} を承認・コード案内メールを送信しました")
    else:
        messages.warning(request, f"ミッション達成 #{c.id} のコードは発行済みですが、メール送信に失敗しました")


def _publish_article(request, article_id):
    """AI執筆の新規記事(非公開・承認待ち)を公開する。IndexNow通知も試みる。"""
    from datetime import date as _date

    from django.core.management import call_command

    from apps.products.models import Article

    a = Article.objects.filter(
        id=article_id, is_published=False, wp_post_id__isnull=True).first()
    if not a:
        messages.warning(request, f"記事 #{article_id} は公開承認の対象ではありません")
        return
    qa = (a.seo_check_result or {}).get("qa")
    if not _qa_ok(qa):
        _qa_block(request, f"記事 /{a.slug}/", qa)
        return
    a.is_published = True
    if not a.published_at:
        a.published_at = timezone.now()
    a.save(update_fields=["is_published", "published_at"])
    log_article_work("article", a.id, a.slug, "human", "applied", "承認して公開")
    try:
        call_command("notify_indexnow", url=[f"https://sc-tsusho.jp{a.get_absolute_url()}"])
        note = "・IndexNow通知済み"
    except Exception:
        note = "（IndexNow通知は失敗・後で再通知可）"
    messages.success(request, f"✅ 記事 /{a.slug}/ を公開しました{note}")


# 新規記事の公開承認キューに載せる下限日: これ以前に作られた非公開記事
# (ドラフト復活プール等)は対象外。AI執筆体制の開始日。
_NEW_ARTICLE_QUEUE_SINCE = "2026-09-06"


def _approve_survey(request, response_id):
    s = SurveyResponse.objects.filter(
        id=response_id, is_approved=False, is_deleted=False).first()
    if not s:
        messages.warning(request, f"アンケート回答 #{response_id} は公開待ちではありません")
        return
    s.is_approved = True
    s.save(update_fields=["is_approved"])
    messages.success(request, f"✅ アンケート回答 #{s.id} のコメントを公開しました")


_ACTIONS = {
    "rw_apply": _approve_rewrite,
    "rw_reject": _reject_rewrite,
    "review_approve": _approve_review,
    "review_reject": _reject_review,
    "mission_approve": _approve_mission,
    "survey_approve": _approve_survey,
    "article_publish": _publish_article,
}

# ---- AI社員の稼働状況(2026-09-07) ----------------------------------------
# 予定(cron定義のミラー)・前回実行(ログ解析)・前回報告(WorkReport)を承認センターに可視化。

import re as _sre
from datetime import datetime as _dt, timedelta as _td

_AGENTS = [
    {"key": "desk", "name": "編集長", "duty": "週次計画・収益進捗・KW横展開・検収",
     "sched": "月曜 7:00", "rule": ("weekly", (0,), 7, 0),
     "log": "/opt/claude-ops/logs/agents/desk.log", "prefix": "週次ダイジェスト"},
    {"key": "researcher", "name": "リサーチ担当",
     "duty": "新規テーマのブリーフ作成／リサーチ依頼対応(兼任・情報不足の記事を調査)",
     "sched": "火・木 5:00 ＋ 依頼時に即", "rule": ("weekly", (1, 3), 5, 0),
     "log": "/opt/claude-ops/logs/agents/researcher.log", "prefix": "リサーチ"},
    {"key": "writer", "name": "新規執筆担当", "duty": "復活3本/回・Track C執筆",
     "sched": "水・金 5:00", "rule": ("weekly", (2, 4), 5, 0),
     "log": "/opt/claude-ops/logs/agents/writer.log", "prefix": "新規執筆"},
    {"key": "qa", "name": "検品担当", "duty": "新規記事の全数検品+最終調整",
     "sched": "水・金 7:30", "rule": ("weekly", (2, 4), 7, 30),
     "log": "/opt/claude-ops/logs/agents/qa.log", "prefix": "検品"},
    {"key": "product_writer", "name": "商品記事v2担当", "duty": "商品ページ記事の量産(別トラック・1本/回)",
     "sched": "火・木・土 4:30", "rule": ("weekly", (1, 3, 5), 4, 30),
     "log": "/opt/claude-ops/logs/agents/product_writer.log", "prefix": "商品記事v2"},
    {"key": "followup", "name": "リライト後続処理",
     "duty": "判定確定後のノイズ検証/再リライト／修正対応(兼任・人の差し戻しを直す)",
     "sched": "毎日 6:40 ＋ 差し戻し時に即", "rule": ("daily", None, 6, 40),
     "log": "/opt/claude-ops/logs/agents/rewrite_followup.log", "prefix": "リライト後続処理"},
    {"key": "observe", "name": "観測cron(決定論)", "duty": "GSC再取得→効果測定→21日判定→学習集計",
     "sched": "3日おき 6:00", "rule": ("dom3", None, 6, 0),
     "log": "/opt/claude-ops/logs/observe_rewrites.log", "prefix": "リライト効果 定期観測"},
]

_LOG_LINE = _sre.compile(r"=====\s+([\d-]{10}[_ ][\d:]{8})\s+(start|end)")


def _next_run(rule):
    kind, wdays, h, m = rule
    now = timezone.localtime()
    for i in range(0, 32):
        cand = (now + _td(days=i)).replace(hour=h, minute=m, second=0, microsecond=0)
        if cand <= now:
            continue
        if kind == "daily":
            return cand
        if kind == "weekly" and cand.weekday() in wdays:
            return cand
        if kind == "dom3" and (cand.day - 1) % 3 == 0:
            return cand
    return None


def _last_log_run(path):
    """ログ末尾から前回実行(開始時刻・実行中か)を返す。"""
    try:
        text = _Path(path).read_text(encoding="utf-8", errors="replace")[-20000:]
    except OSError:
        return None, False
    last_start = last_end = None
    for m in _LOG_LINE.finditer(text):
        ts = m.group(1).replace("_", " ")
        if m.group(2) == "start":
            last_start = ts
        else:
            last_end = ts
    running = bool(last_start and (not last_end or last_end < last_start))
    return last_start, running


_CHARACTERS_FILE = Path("/opt/claude-ops/agents/characters.json")
_MEDIA_ROOT = Path("/home/deploy/app")


def _characters():
    """AI社員のキャラクター設定(名前・あだ名・アバター)。ユーザーが愛着づけのため命名。"""
    try:
        return json.loads(_CHARACTERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _agent_statuses():
    from apps.analytics.models import WorkReport
    chars = _characters()
    rows = []
    for a in _AGENTS:
        last_start, running = _last_log_run(a["log"])
        report = (WorkReport.objects.filter(title__startswith=a["prefix"])
                  .order_by("-id").first())
        nr = _next_run(a["rule"])
        ch = chars.get(a["key"]) or {}
        avatar = ch.get("avatar", "")
        if avatar and not (_MEDIA_ROOT / avatar.lstrip("/")).exists():
            avatar = ""  # 画像未転送の間は非表示
        # ホバー用イラスト: {avatar名}_hover.png が存在すればマウスオンで画面中央に大きく表示。
        # 無ければ原寸(_full)→通常版の順でフォールバック。
        # URLに更新時刻(?v=)を付け、差し替え時にブラウザキャッシュで古い画像が残らないようにする。
        def _v(rel):
            try:
                return f"{rel}?v={int((_MEDIA_ROOT / rel.lstrip('/')).stat().st_mtime)}"
            except OSError:
                return rel
        avatar_hover = ""
        popup_src = ""
        if avatar:
            base = avatar.rsplit(".", 1)[0]
            hv = base + "_hover.png"
            full = base + "_full.png"
            if (_MEDIA_ROOT / hv.lstrip("/")).exists():
                avatar_hover = _v(hv)
            if avatar_hover:
                popup_src = avatar_hover
            elif (_MEDIA_ROOT / full.lstrip("/")).exists():
                popup_src = _v(full)
            else:
                popup_src = _v(avatar)
            avatar = _v(avatar)
        rows.append({
            "key": a["key"],
            "name": a["name"], "duty": a["duty"], "sched": a["sched"],
            "next_run": nr, "last_start": last_start, "running": running,
            "report": report,
            "char_name": ch.get("name", ""), "char_nick": ch.get("nick", ""),
            "char_profile": ch.get("profile", ""), "avatar": avatar,
            "avatar_hover": avatar_hover, "popup_src": popup_src,
            "char_color": ch.get("color", "#c97b84"),
        })
    return rows


# ---- 商品記事v2の承認キュー(2026-09-07・量産トラック) ----------------------
# 商品記事v2担当(火木土)が draft+preview+queue json を出力し、人がここで承認すると
# Product.description/メタに反映される。反映済み(本文=draft)は自動でキューから消える。

_PV2_QUEUE_DIR = Path("/opt/claude-ops/agents/product_v2_queue")
_PV2_BACKUP_DIR = Path("/opt/claude-ops/backups")


def _product_v2_queue():
    from apps.products.models import Product
    items = []
    if not _PV2_QUEUE_DIR.exists():
        return items
    for f in sorted(_PV2_QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            draft = Path(data["draft_path"]).read_text(encoding="utf-8")
        except (ValueError, OSError, KeyError):
            continue
        p = Product.objects.filter(pk=data.get("product_pk")).first() \
            or Product.objects.filter(slug=data.get("slug", "")).first()
        if not p:
            continue
        if (p.description or "").strip() == draft.strip():
            continue  # 反映済み
        items.append({
            "product": p, "slug": p.slug,
            "title": data.get("meta_title") or data.get("title") or p.name,
            "meta_description": data.get("meta_description", ""),
            "preview_url": data.get("preview_url", ""),
            "created": data.get("created", ""),
            "qa": data.get("qa") or {},
            "chars": len(draft),
        })
    return items


def _pv2_data_for(product_pk):
    for f in _PV2_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if data.get("product_pk") == product_pk:
            return f, data
    return None, None


def _apply_product_v2(request, product_pk):
    from django.core.management import call_command

    from apps.products.models import Product
    f, data = _pv2_data_for(product_pk)
    p = Product.objects.filter(pk=product_pk).first()
    if not f or not p:
        messages.warning(request, "商品記事v2の承認対象が見つかりません")
        return
    if not _qa_ok(data.get("qa")):
        _qa_block(request, f"商品記事v2（/{p.slug}/）", data.get("qa"))
        return
    try:
        draft = Path(data["draft_path"]).read_text(encoding="utf-8")
    except OSError:
        messages.error(request, "下書きファイルを読めませんでした")
        return
    backup = {"slug": p.slug, "saved_at": timezone.now().isoformat(),
              "description": p.description, "meta_title": p.meta_title,
              "meta_description": p.meta_description}
    bpath = _PV2_BACKUP_DIR / f"product_{p.slug}_v2apply_{timezone.now():%Y%m%d_%H%M%S}.json"
    try:
        _PV2_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bpath.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        # 典型例: 保存先が root 所有で、deploy 実行の gunicorn から書けない。
        # 反映前バックアップが取れないまま本文を差し替えるのは危険なので中止する。
        messages.error(
            request,
            f"バックアップを書き込めないため反映を中止しました（{e.strerror}: {bpath.parent}）。"
            "保存先の所有者と権限を確認してください（グループ www-data・2775 が必要）。"
            "記事とキューはそのまま残っているので、直してからもう一度承認してください。")
        return
    p.description = draft
    if data.get("meta_title"):
        p.meta_title = data["meta_title"][:100]
    if data.get("meta_description"):
        p.meta_description = data["meta_description"][:200]
    p.save(update_fields=["description", "meta_title", "meta_description"])
    log_article_work("product_v2", p.pk, p.slug, "human", "applied",
                     f"承認して /{p.slug}/ に反映（{len(draft)}字・meta同時更新）")
    try:
        call_command("notify_indexnow",
                     url=[f"https://sc-tsusho.jp{p.get_absolute_url()}"])
        note = "・IndexNow通知済み"
    except Exception:
        note = "（IndexNow通知は失敗・後で再通知可）"
    messages.success(request, f"✅ 商品記事v2を /{p.slug}/ に反映しました{note}")


def _reject_product_v2(request, product_pk):
    """商品記事v2の案を承認キューから取り下げる（差し戻しとは別物）。

    担当AIには何も伝わらない“取り下げ”なので、修正させたいときは使わない。
    修正させたいときはレビューページで指示を書いて差し戻すこと（そちらは担当が起動する）。
    """
    f, data = _pv2_data_for(product_pk)
    if not f:
        messages.warning(request, "商品記事v2の承認対象が見つかりません")
        return
    try:
        f.unlink()
    except OSError:
        messages.error(request, "キューから外せませんでした")
        return
    messages.info(
        request,
        f"商品記事v2（{data.get('slug')}）を承認キューから取り下げました。"
        "下書きファイルは残っていますが、担当AIには何も伝わっていません"
        "（直させたい場合はレビューページで修正指示を書いて差し戻してください）")


_ACTIONS["pv2_apply"] = _apply_product_v2
_ACTIONS["pv2_reject"] = _reject_product_v2


# ---- 編集長からの判断待ち(2026-09-14) -------------------------------------
# 週次ダイジェストの「要対応(人)」に答える場所が無く、ターミナルで指示するか放置されるかだった。
# ここで選択肢を押すと: 選択肢の action を実行 → 編集長を「判断反映モード」で起動するトリガーを置く。

_DECISION_TRIGGER_DIR = Path("/opt/claude-ops/agents/triggers")


def _run_decision_action(decision, action):
    """選択肢に紐づく決定論の処理だけを実行する（許可リスト制）。戻り値=実行結果の説明。"""
    from apps.products.models import Product
    atype = (action or {}).get("type")
    if atype not in ("set_discontinued", "set_current"):
        return ""
    value = atype == "set_discontinued"
    done = []
    for slug in action.get("products") or []:
        p = Product.objects.filter(slug=slug).first()
        if not p:
            done.append(f"{slug}: 商品が見つからず未実行")
            continue
        data = dict(p.api_data or {})
        check = dict(data.get("discontinued_check") or {})
        check["flag_set"] = {"value": value, "at": timezone.now().isoformat(),
                             "by": f"運営(承認センター・判断#{decision.id})"}
        data["discontinued_check"] = check
        p.is_discontinued = value
        p.api_data = data
        p.save(update_fields=["is_discontinued", "api_data"])
        done.append(f"{slug}: is_discontinued={value}")
    return " / ".join(done)


def _answer_decision(request, decision_id):
    from .models import DeskDecision
    d = DeskDecision.objects.filter(id=decision_id, status="open").first()
    if not d:
        messages.warning(request, f"判断#{decision_id} は回答待ちではありません")
        return
    key = request.POST.get("choice", "")
    comment = (request.POST.get("comment") or "").strip()
    op = d.option(key)
    if not op and not (key == "other" and comment):
        messages.error(request, f"判断#{d.id}: 選択肢を選ぶか、「その他」ではコメントを書いてください")
        return
    d.choice = key
    d.choice_label = op["label"] if op else "その他（コメントで指示）"
    d.answer_comment = comment
    d.answered_by = request.user.get_username()
    d.answered_at = timezone.now()
    d.action_result = _run_decision_action(d, (op or {}).get("action"))
    d.status = "answered"
    d.save()

    trig = _DECISION_TRIGGER_DIR / f"desk-decision-{d.id}.json"
    try:
        trig.write_text(json.dumps({
            "source": "desk_decision", "decision_id": d.id, "choice": key,
            "created_at": timezone.now().isoformat()}, ensure_ascii=False), encoding="utf-8")
        relay = "5分以内に編集長（レイカさん）が回答を計画へ反映します"
    except OSError:
        relay = "⚠️ 編集長の起動トリガーを置けませんでした（次の月曜の定期実行で反映されます）"
    done = f"（実行済み: {d.action_result}）" if d.action_result else ""
    messages.success(request, f"✅ 判断#{d.id}「{d.choice_label}」で回答しました{done}。{relay}")


_ACTIONS["decision_answer"] = _answer_decision


def _handle_avatar_upload(request):
    """AI社員のアバター画像をボードから直接アップロードする(scp不要化・2026-09-07)。"""
    key = request.POST.get("agent_key", "")
    upload = request.FILES.get("image")
    ch = _characters().get(key)
    if not ch or not upload:
        messages.error(request, "アバターのアップロード対象が不正です")
        return
    if not (upload.content_type or "").startswith("image/"):
        messages.error(request, "画像ファイルをアップロードしてください")
        return
    # 保存先は characters.json の avatar パス(例: /media/agents/mio.png)に固定。
    # kind=hover はマウスオン表示用({名前}_hover.png)。
    rel = ch.get("avatar", "").lstrip("/")
    if not rel.startswith("media/agents/"):
        messages.error(request, "アバターの保存先が未設定です")
        return
    kind = request.POST.get("kind", "main")
    if kind == "hover":
        rel = rel.rsplit(".", 1)[0] + "_hover.png"
    dest = _MEDIA_ROOT / rel
    try:
        with open(dest, "wb") as f:
            for chunk in upload.chunks():
                f.write(chunk)
        # ボード用に軽量化(原寸が大きい場合)
        try:
            from PIL import Image
            img = Image.open(dest)
            # hover=画面中央に大きく出すため高解像度を維持(1200px)、mainはボード用(360px)
            limit = 1200 if kind == "hover" else 360
            if max(img.size) > limit:
                img.thumbnail((limit, limit), Image.LANCZOS)
                img.save(dest, optimize=True)
        except Exception:
            pass
    except OSError:
        messages.error(request, "画像を保存できませんでした")
        return
    label = "ホバー用イラスト" if kind == "hover" else "イラスト"
    messages.success(request, f"✅ {ch.get('nick', key)} の{label}を設定しました")


# ---- 画像生成待ちキュー(2026-09-06) --------------------------------------
# 執筆AIが記事ごとの画像プロンプトを JSON で出力し、人が ChatGPT(Proプラン)で
# 生成した画像をこのページへドラッグ&ドロップする。
# アイキャッチ→Article.thumbnail 自動設定 / 解説図→指定H2の直後へ自動挿入。
# 完了判定: アイキャッチ=thumbnail有無 / 解説図=imgq-{slug}-{figid} 名の画像有無。

import re as _re
from pathlib import Path as _Path

_IMAGE_PROMPTS_DIR = _Path("/opt/claude-ops/agents/image_prompts")


def _image_queue():
    from apps.products.models import Article
    items = []
    if not _IMAGE_PROMPTS_DIR.exists():
        return items
    for f in sorted(_IMAGE_PROMPTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        slug = data.get("slug") or f.stem
        article = Article.objects.filter(slug=slug).first()
        if not article:
            continue
        ec = data.get("eyecatch") or {}
        # 暫定テンプレ版(eyecatch-*)のままなら生成待ち。人がドロップした版(ecq-*)で完了。
        # JSONに "replace": true を書くと、設定済みでも差し替え待ちとして再掲する
        # (2026-09-09。差し替え後はアップロード処理がフラグを落とす)。
        ec_replace = bool(ec.get("replace"))
        ec_pending = (not article.thumbnail
                      or "eyecatch-" in (article.thumbnail.name or ""))
        if ec.get("prompt") and (ec_pending or ec_replace):
            items.append({
                "kind": "eyecatch", "slug": slug, "article": article,
                "label": "アイキャッチ（差し替え）" if ec_replace and not ec_pending
                         else "アイキャッチ",
                "fig_id": "",
                "prompt": ec["prompt"], "note": ec.get("note", ""),
            })
        for fig in data.get("figures") or []:
            fid = fig.get("id") or ""
            if not fid or not fig.get("prompt"):
                continue
            fig_replace = bool(fig.get("replace"))
            done = article.images.filter(
                image__icontains=f"imgq-{slug}-{fid}").exists()
            if done and not fig_replace:
                continue
            items.append({
                "kind": "figure", "slug": slug, "article": article,
                "label": (f"解説図（差し替え）: {fig.get('title', fid)}" if done
                          else f"解説図: {fig.get('title', fid)}"),
                "fig_id": fid,
                "prompt": fig["prompt"],
                "note": f"挿入位置: H2「{fig.get('insert_after_h2', '(指定なし・画像リストへ)')}」の直後",
            })
    return items


def _clear_replace_flag(slug, kind, fig_id=""):
    """差し替え待ちフラグ("replace": true)を落とす。書き込めない場合は黙って諦める
    (キューに残るだけで実害はない)。"""
    f = _IMAGE_PROMPTS_DIR / f"{slug}.json"
    if not f.exists():
        return
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if kind == "eyecatch":
            (data.get("eyecatch") or {}).pop("replace", None)
        else:
            for fig in data.get("figures") or []:
                if fig.get("id") == fig_id:
                    fig.pop("replace", None)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    except (ValueError, OSError):
        pass


def _handle_image_upload(request):
    from apps.products.models import Article, ArticleImage
    slug = request.POST.get("slug", "")
    kind = request.POST.get("kind", "")
    fig_id = _re.sub(r"[^A-Za-z0-9_-]", "", request.POST.get("fig_id", ""))
    upload = request.FILES.get("image")
    article = Article.objects.filter(slug=slug).first()
    if not article or not upload:
        messages.error(request, "アップロード対象が見つかりません")
        return
    if not (upload.content_type or "").startswith("image/"):
        messages.error(request, "画像ファイルをアップロードしてください")
        return
    ext = (upload.name.rsplit(".", 1)[-1] if "." in upload.name else "png").lower()[:5]

    if kind == "eyecatch":
        # ecq- 接頭辞=人がドロップした完成版(暫定テンプレ版 eyecatch- と区別)
        article.thumbnail.save(f"ecq-{slug}.{ext}", upload, save=False)
        article.save(update_fields=["thumbnail"])
        _clear_replace_flag(slug, "eyecatch")
        messages.success(request, f"✅ /{slug}/ のアイキャッチを設定しました")
        return

    if kind == "figure" and fig_id:
        # 挿入位置とaltはプロンプトJSONから引く
        meta = {}
        f = _IMAGE_PROMPTS_DIR / f"{slug}.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                meta = next((x for x in data.get("figures", [])
                             if x.get("id") == fig_id), {})
            except (ValueError, OSError):
                pass
        alt = meta.get("title", "") or f"解説図 {fig_id}"
        # 差し替え(2026-09-09): 同じ fig_id の図が既にある場合は、本文中の旧画像の
        # <p><img ...></p> を先に取り除き、旧レコードも消してから新しい図を挿入する。
        # (取り除かないと同じH2の直後に新旧2枚が並ぶ)
        olds = list(article.images.filter(image__icontains=f"imgq-{slug}-{fig_id}"))
        if olds:
            content = article.content or ""
            for o in olds:
                content = _re.sub(
                    r"\s*<p>\s*<img[^>]*src=\"" + _re.escape(o.image.url) + r"\"[^>]*>\s*</p>",
                    "", content)
            article.content = content
            article.save(update_fields=["content"])
            for o in olds:
                o.delete()   # ファイル本体は残す(復元用)。判定は imgq-{slug}-{fig_id} の部分一致
        img = ArticleImage(article=article, alt_text=alt[:200],
                           order=(article.images.count() + 1))
        img.image.save(f"imgq-{slug}-{fig_id}.{ext}", upload, save=False)
        img.save()
        # 指定H2の直後へ自動挿入
        h2_key = (meta.get("insert_after_h2") or "").strip()
        inserted = False
        if h2_key:
            pat = _re.compile(r"(<h2[^>]*>[^<]*" + _re.escape(h2_key) + r"[^<]*</h2>)")
            html_img = (f'\n<p><img src="{img.image.url}" alt="{alt}" '
                        f'loading="lazy"></p>')
            new_content, n = pat.subn(r"\1" + html_img, article.content, count=1)
            if n:
                article.content = new_content
                article.save(update_fields=["content"])
                inserted = True
        _clear_replace_flag(slug, "figure", fig_id)
        if inserted:
            messages.success(
                request, f"✅ /{slug}/ の解説図を H2「{h2_key}」直後に挿入しました")
        else:
            messages.warning(
                request,
                f"解説図を /{slug}/ の画像リストに追加しました（挿入位置のH2が"
                "見つからないため、本文への配置は記事編集画面から行ってください）")
        return
    messages.error(request, "不正な画像アップロードです")


@staff_member_required
@require_http_methods(["GET", "POST"])
def approvals(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "img_upload":
            _handle_image_upload(request)
            return HttpResponseRedirect(reverse("admin_approval_center"))
        if action == "avatar_upload":
            _handle_avatar_upload(request)
            return HttpResponseRedirect(reverse("admin_approval_center"))
        handler = _ACTIONS.get(action)
        try:
            obj_id = int(request.POST.get("id", ""))
        except (TypeError, ValueError):
            obj_id = None
        if handler and obj_id:
            handler(request, obj_id)
        else:
            messages.error(request, "不正な操作です")
        return HttpResponseRedirect(reverse("admin_approval_center"))

    all_rewrites = list(RewriteDraft.objects.filter(status="in_review")
                        .select_related("article").order_by("-reviewed_at"))
    reviews = (Review.objects.filter(is_approved=False, is_deleted=False,
                                     is_rejected=False)
               .select_related("product", "user").order_by("created_at"))
    missions = (UserMissionCompletion.objects
                .filter(status__in=[CompletionStatus.WAITING, CompletionStatus.PENDING])
                .select_related("user", "mission").order_by("completed_at"))
    surveys = (SurveyResponse.objects
               .filter(is_approved=False, is_deleted=False)
               .exclude(reason="").order_by("created_at"))
    from apps.products.models import Article
    all_new_articles = list(Article.objects.filter(
        is_published=False, wp_post_id__isnull=True,
        created_at__date__gte=_NEW_ARTICLE_QUEUE_SINCE)
        .select_related("product_type").order_by("created_at"))

    image_queue = _image_queue()
    all_product_v2 = _product_v2_queue()

    # 各対象の「人からの修正指示(未対応)」件数。レビューページ(article_review)で
    # 起票され、差し戻し中のものはここに件数が出る(2026-09-08)。
    open_notes = {}
    for n in EditorNote.objects.filter(status="open").values_list("kind", "target_id"):
        open_notes[n] = open_notes.get(n, 0) + 1

    def _notes(kind, obj_id):
        return open_notes.get((kind, obj_id), 0)

    # 各記事の最後の作業（誰が何をしたか）。レビューを開かなくても工程の最新状況が分かる。
    last_work = {}
    for w in ArticleWorkLog.objects.order_by("created_at"):
        last_work[(w.kind, w.target_id)] = w

    def _last(kind, obj_id):
        return last_work.get((kind, obj_id))

    for d in all_rewrites:
        d.open_notes = _notes("rewrite", d.id)
        d.last_work = _last("rewrite", d.id)
    for a in all_new_articles:
        a.open_notes = _notes("article", a.id)
        a.last_work = _last("article", a.id)
    for it in all_product_v2:
        it["open_notes"] = _notes("product_v2", it["product"].pk)
        it["last_work"] = _last("product_v2", it["product"].pk)

    # 検品(リン様)が終わって修正まで済んだものだけを承認キューに載せる(2026-09-08)。
    # 未検品/差戻しは人に回さず「検品中」に分けて表示だけする(存在は見えるが承認できない)。
    qa_pending = []

    def _days_since(datestr):
        """qa記録の日付(YYYY-MM-DD)から今日までの日数。差し戻しの放置を可視化する。"""
        try:
            d = _dt.strptime(str(datestr)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None
        return (timezone.localdate() - d).days

    def _split(items, get_qa, row):
        ready = []
        for it in items:
            qa = get_qa(it)
            if _qa_ok(qa):
                ready.append(it)
            else:
                verdict = (qa or {}).get("verdict", "")
                r = {**row(it), "verdict": verdict,
                     "notes": (qa or {}).get("notes", "")}
                if verdict == "failed":
                    r["days"] = _days_since((qa or {}).get("date"))
                    # 担当AIのキューに載っているか（qa_sendback 済みか）を出す
                    r["sendback_open"] = EditorNote.objects.filter(
                        kind=r["note_kind"], target_id=r["note_target"],
                        source="qa", status="open").count()
                qa_pending.append(r)
        return ready

    rewrites = _split(
        all_rewrites, lambda d: d.qa_result,
        lambda d: {"kind": "リライト案", "title": f"#{d.id} {d.draft_title or d.article.title}",
                   "sub": f"/{d.article.slug}/", "notes_open": d.open_notes,
                   "note_kind": "rewrite", "note_target": d.id,
                   "review_url": f"/admin/approvals/review/rewrite/{d.id}/",
                   "url": f"/admin/analytics/rewritedraft/{d.id}/change/"})
    new_articles = _split(
        all_new_articles, lambda a: (a.seo_check_result or {}).get("qa"),
        lambda a: {"kind": "新規記事", "title": a.title, "sub": f"/{a.slug}/",
                   "notes_open": a.open_notes,
                   "note_kind": "article", "note_target": a.id,
                   "review_url": f"/admin/approvals/review/article/{a.id}/",
                   "url": f"/admin/products/article/{a.id}/change/"})
    product_v2 = _split(
        all_product_v2, lambda it: it.get("qa"),
        lambda it: {"kind": "商品記事v2", "title": it["title"], "sub": f"/{it['slug']}/",
                    "notes_open": it["open_notes"],
                    "note_kind": "product_v2", "note_target": it["product"].pk,
                    "review_url": f"/admin/approvals/review/product_v2/{it['product'].pk}/",
                    "url": it.get("preview_url", "")})
    # 要差戻し（人が気づくべきもの）を先頭に、放置の長い順で並べる
    qa_pending.sort(key=lambda r: (r.get("verdict") != "failed",
                                   -(r.get("days") or 0)))
    from apps.analytics.models import DeskDecision, WorkReport
    recent_reports = WorkReport.objects.order_by("-id")[:8]
    decisions = list(DeskDecision.objects.filter(status="open")
                     .select_related("source_report").order_by("first_raised_at"))
    from .workreport_render import render_body
    for d in decisions:
        d.background_html = render_body(d.background)[0]
    decisions_in_flight = list(DeskDecision.objects.filter(
        status__in=["answered", "dev_pending"]).order_by("-answered_at"))
    decisions_recent_done = list(DeskDecision.objects.filter(
        status__in=["done", "withdrawn"]).order_by("-handled_at")[:5])

    ctx = {
        "decisions": decisions,
        "decisions_in_flight": decisions_in_flight,
        "decisions_recent_done": decisions_recent_done,
        "agent_statuses": _agent_statuses(),
        "recent_reports": recent_reports,
        "product_v2": product_v2,
        "title": "承認センター",
        "rewrites": rewrites,
        "qa_pending": qa_pending,
        "reviews": reviews,
        "missions": missions,
        "surveys": surveys,
        "new_articles": new_articles,
        "image_queue": image_queue,
        # 人が実際に処理できる件数だけを数える(検品中は含めない)
        "total": (len(decisions) + len(rewrites) + reviews.count() + missions.count()
                  + surveys.count() + len(new_articles) + len(image_queue)
                  + len(product_v2)),
    }
    return render(request, "admin/approval_center.html", ctx)
