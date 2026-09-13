import csv

from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    AccessLog, WorkReport, ArticleMetricSnapshot,
    TriageRun, ArticleTriage, PlaybookRule,
)


@admin.register(ArticleMetricSnapshot)
class ArticleMetricSnapshotAdmin(admin.ModelAdmin):
    """記事パフォーマンス・スナップショットの素データ閲覧（可視化は専用ダッシュボード）。"""
    list_display = ("fetched_at_jst", "period", "total_impressions",
                    "total_clicks", "total_sessions", "bounce", "open_dashboard")
    readonly_fields = [f.name for f in ArticleMetricSnapshot._meta.fields]
    ordering = ("-fetched_at",)

    @admin.display(description="取得日時", ordering="-fetched_at")
    def fetched_at_jst(self, obj):
        from django.utils.timezone import localtime
        return localtime(obj.fetched_at).strftime("%Y-%m-%d %H:%M")

    @admin.display(description="集計期間")
    def period(self, obj):
        return f"{obj.period_start} 〜 {obj.period_end}"

    @admin.display(description="平均直帰率")
    def bounce(self, obj):
        return f"{obj.avg_bounce_rate * 100:.1f}%"

    @admin.display(description="ダッシュボード")
    def open_dashboard(self, obj):
        return format_html(
            '<a href="/admin/seo/article-performance/" target="_blank">📊 可視化を開く</a>')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


_STATUS_STYLE = {
    "success": ("#047857", "#ECFDF5", "完了"),
    "info": ("#1D4ED8", "#EFF6FF", "情報"),
    "warning": ("#B45309", "#FFFBEB", "注意"),
    "error": ("#FFFFFF", "#991B1B", "エラー"),
}


@admin.register(WorkReport)
class WorkReportAdmin(admin.ModelAdmin):
    # 閲覧ページは templates/admin/analytics/workreport/change_form.html で読み手向けに整形(2026-09-07)。
    change_form_template = "admin/analytics/workreport/change_form.html"
    list_display = ("created_at_jst", "agent_col", "status_badge", "title_col")
    list_display_links = ("title_col",)
    list_filter = ("status", "created_at")
    search_fields = ("title", "summary", "body", "files_changed")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    fields = ("created_at", "status", "title", "summary",
              "body_rendered", "files_rendered", "body", "files_changed")
    readonly_fields = ("created_at", "body_rendered", "files_rendered")

    class Media:
        css = {"all": ("admin/workreport_list.css",)}

    @admin.display(description="報告日時", ordering="-created_at")
    def created_at_jst(self, obj):
        from django.utils.timezone import localtime
        return localtime(obj.created_at).strftime("%Y-%m-%d %H:%M")

    @admin.display(description="報告者")
    def agent_col(self, obj):
        from .workreport_render import agent_for_title
        a = agent_for_title(obj.title)
        if a["avatar"]:
            icon = format_html(
                '<img src="{}" alt="" style="width:26px;height:26px;border-radius:50%;'
                'object-fit:cover;border:2px solid {};vertical-align:middle;margin-right:6px">',
                a["avatar"], a["color"])
        else:
            icon = format_html(
                '<span style="display:inline-block;width:26px;height:26px;border-radius:50%;'
                'background:#e8e8e8;text-align:center;line-height:26px;vertical-align:middle;'
                'margin-right:6px">🛠</span>')
        return format_html('<span style="white-space:nowrap">{}<b style="color:{}">{}</b></span>',
                           icon, a["color"], a["nick"])

    @admin.display(description="作業タイトル / 要点", ordering="title")
    def title_col(self, obj):
        from .workreport_render import summary_html_for_list
        return format_html('<div class="wr-ttl">{}</div>{}', obj.title,
                           summary_html_for_list(obj.summary, limit=220))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        from django.utils.timezone import localtime
        from .workreport_render import (agent_for_title, files_list, render_body,
                                        summary_items)
        extra = dict(extra_context or {})
        obj = self.get_object(request, object_id)
        if obj is not None:
            html, toc = render_body(obj.body)
            fg, bg, label = _STATUS_STYLE.get(obj.status, ("#666", "#EEE", obj.status))
            extra.update({
                "wr_agent": agent_for_title(obj.title),
                "wr_summary_items": summary_items(obj.summary),
                "wr_body_html": html,
                "wr_toc": toc,
                "wr_files": files_list(obj.files_changed),
                "wr_status_fg": fg, "wr_status_bg": bg, "wr_status_label": label,
                "wr_created": localtime(obj.created_at).strftime("%Y-%m-%d %H:%M"),
                "wr_newer": WorkReport.objects.filter(pk__gt=obj.pk).order_by("pk").first(),
                "wr_older": WorkReport.objects.filter(pk__lt=obj.pk).order_by("-pk").first(),
            })
        return super().change_view(request, object_id, form_url, extra_context=extra)

    @admin.display(description="状態", ordering="status")
    def status_badge(self, obj):
        color, bg, label = _STATUS_STYLE.get(obj.status, ("#666", "#EEE", obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;border-radius:8px;'
            'font-size:11px;font-weight:700">{}</span>', bg, color, label)

    @admin.display(description="作業報告")
    def body_rendered(self, obj):
        if not obj.body:
            return "-"
        import markdown
        html = markdown.markdown(
            obj.body, extensions=["fenced_code", "tables", "nl2br", "sane_lists"])
        return mark_safe(
            '<div style="max-width:860px;line-height:1.7;font-size:13px">' + html + "</div>")

    @admin.display(description="変更ファイル")
    def files_rendered(self, obj):
        files = [f.strip() for f in obj.files_changed.splitlines() if f.strip()]
        if not files:
            return "-"
        items = "".join(
            format_html(
                '<li style="font-family:monospace;font-size:12px;padding:1px 0">{}</li>', f)
            for f in files)
        return mark_safe('<ul style="margin:0;padding-left:18px">' + items + "</ul>")

    def has_change_permission(self, request, obj=None):
        # 報告は記録なので編集不可（追加・削除は可）。
        return False


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ("created_at_jst", "status_badge", "method", "url_short",
                    "user", "ip", "bot_label", "referer_short")
    list_filter = ("status_code", "method", "is_bot", "created_at")
    search_fields = ("url", "ip", "user_agent", "referer", "user__email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "url", "method", "status_code", "ip",
                       "user_agent", "referer", "user", "is_bot")
    list_per_page = 100
    actions = ("delete_old_logs",)

    @admin.display(description="日時", ordering="-created_at")
    def created_at_jst(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")

    @admin.display(description="ステータス", ordering="status_code")
    def status_badge(self, obj):
        c = obj.status_code or 0
        if 200 <= c < 300:
            color, bg = "#047857", "#ECFDF5"
        elif 300 <= c < 400:
            color, bg = "#1D4ED8", "#EFF6FF"
        elif c == 404:
            color, bg = "#B45309", "#FFFBEB"
        elif 400 <= c < 500:
            color, bg = "#991B1B", "#FEF2F2"
        elif 500 <= c:
            color, bg = "#FFFFFF", "#991B1B"
        else:
            color, bg = "#666", "#EEE"
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700">{}</span>',
            bg, color, c)

    @admin.display(description="URL")
    def url_short(self, obj):
        return obj.url if len(obj.url) <= 60 else obj.url[:60] + "…"

    @admin.display(description="リファラ")
    def referer_short(self, obj):
        return obj.referer[:40] + "…" if len(obj.referer) > 40 else (obj.referer or "-")

    @admin.display(description="Bot")
    def bot_label(self, obj):
        if obj.is_bot:
            return format_html(
                '<span style="background:#FEF2F2;color:#991B1B;padding:2px 8px;border-radius:8px;font-size:11px">BOT</span>')
        return ""

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

    @admin.action(description="30日以上前のログを削除")
    def delete_old_logs(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        n = AccessLog.objects.filter(created_at__lt=cutoff).delete()[0]
        self.message_user(request, f"{n}件削除しました")


# =============================================================================
# GSC記事トリアージ
# =============================================================================

_BUCKET_STYLE = {
    "quick_win":  ("#1e7a40", "#e7f6ec", "quick_win｜あと一歩"),
    "needs_work": ("#9a5b00", "#fdf0dd", "needs_work｜意図のズレ"),
    "performing": ("#1456a0", "#e6effb", "performing｜上位"),
    "dead":       ("#666666", "#eeeeee", "dead｜統合/削除候補"),
}
# get_queryset で使うバケットの並び順（quick_win を最優先で上に）
_BUCKET_ORDER = {"quick_win": 0, "needs_work": 1, "performing": 2, "dead": 3}

# 観察ステータスの色分け（bucket とは独立した第2軸）
_OBS_STYLE = {
    "observing": ("#1456a0", "#e6effb", "observing｜様子見"),
    "evaluable": ("#9a5b00", "#fdf0dd", "evaluable｜評価中"),
    "settled":   ("#555555", "#e6e6e6", "settled｜判定済み"),
    "unknown":   ("#999999", "#f4f4f4", "unknown｜更新日不明"),
}


@admin.register(TriageRun)
class TriageRunAdmin(admin.ModelAdmin):
    """トリアージ実行の履歴一覧（スナップショットと同じ感覚で過去実行を確認）。"""
    list_display = ("period", "fetched_at", "total_articles",
                    "count_quick_win", "count_needs_work",
                    "count_performing", "count_dead", "view_articles")
    readonly_fields = [f.name for f in TriageRun._meta.fields]
    ordering = ("-fetched_at",)

    @admin.display(description="期間")
    def period(self, obj):
        return f"{obj.period_start}〜{obj.period_end}"

    @admin.display(description="記事一覧")
    def view_articles(self, obj):
        url = reverse("admin:analytics_articletriage_changelist")
        return format_html('<a href="{}?run__id__exact={}">この実行の記事を見る</a>', url, obj.id)


@admin.register(ArticleTriage)
class ArticleTriageAdmin(admin.ModelAdmin):
    """記事ごとのトリアージ結果。quick_win→…→dead、各バケット内は最上位クエリ順位の昇順。"""
    list_display = ("bucket_label", "obs_label", "best_query_position", "impressions",
                    "clicks", "avg_position", "best_query", "last_updated",
                    "days_since_update", "url_link", "run")
    list_filter = ("bucket", "observation_status", "run")
    search_fields = ("url", "best_query")
    list_select_related = ("run", "article")
    actions = ("export_csv",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # quick_win→needs_work→performing→dead、各内は best_query_position 昇順
        # （位置NULL＝dead等は末尾へ）。DBのCASE順で安定ソート。
        from django.db.models import Case, When, Value, IntegerField, F
        order = Case(
            *[When(bucket=b, then=Value(v)) for b, v in _BUCKET_ORDER.items()],
            default=Value(99), output_field=IntegerField(),
        )
        return qs.annotate(_bucket_order=order).order_by(
            "_bucket_order", F("best_query_position").asc(nulls_last=True))

    @admin.display(description="バケット", ordering="bucket")
    def bucket_label(self, obj):
        fg, bg, label = _BUCKET_STYLE.get(obj.bucket, ("#000", "#fff", obj.bucket))
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
            'font-weight:700;color:{};background:{};white-space:nowrap;">{}</span>',
            fg, bg, label)

    @admin.display(description="観察ステータス", ordering="observation_status")
    def obs_label(self, obj):
        if not obj.observation_status:
            return ""
        fg, bg, label = _OBS_STYLE.get(
            obj.observation_status, ("#000", "#fff", obj.observation_status))
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
            'font-weight:700;color:{};background:{};white-space:nowrap;">{}</span>',
            fg, bg, label)

    @admin.display(description="URL")
    def url_link(self, obj):
        # 記事にFKがあれば記事編集画面へ、なければ実URLへ
        if obj.article_id:
            try:
                edit = reverse("admin:products_article_change", args=[obj.article_id])
                return format_html('<a href="{}">{}</a>　<a href="https://sc-tsusho.jp{}" '
                                   'target="_blank" rel="noopener">↗</a>', edit, obj.url, obj.url)
            except Exception:  # noqa: BLE001
                pass
        return format_html('<a href="https://sc-tsusho.jp{}" target="_blank" '
                           'rel="noopener">{}</a>', obj.url, obj.url)

    @admin.action(description="選択行をCSVエクスポート")
    def export_csv(self, request, queryset):
        resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        resp["Content-Disposition"] = 'attachment; filename="article_triage.csv"'
        w = csv.writer(resp)
        w.writerow(["bucket", "observation_status", "last_updated", "days_since_update",
                    "best_query_position", "impressions", "clicks", "ctr",
                    "avg_position", "best_query", "best_query_impressions",
                    "num_queries", "in_sitemap", "url", "run_id"])
        for o in queryset:
            w.writerow([o.bucket, o.observation_status, o.last_updated, o.days_since_update,
                        o.best_query_position, o.impressions, o.clicks, o.ctr,
                        o.avg_position, o.best_query, o.best_query_impressions,
                        o.num_queries, o.in_sitemap, o.url, o.run_id])
        return resp


@admin.register(PlaybookRule)
class PlaybookRuleAdmin(admin.ModelAdmin):
    """順位に効く要素のプレイブック（正本は playbook.md）。人間がレビュー・検証する。"""
    list_display = ("priority", "kind", "category", "title", "evidence_brief",
                    "verified", "is_active", "source_run")
    list_filter = ("category", "is_antipattern", "verified", "is_active")
    search_fields = ("key", "title", "description", "check_item")
    list_editable = ("verified", "is_active")
    readonly_fields = ("created_at", "updated_at", "evidence")
    list_select_related = ("source_run",)
    ordering = ("priority",)

    @admin.display(description="種別")
    def kind(self, obj):
        if obj.is_antipattern:
            return format_html('<span style="color:#c0392b;font-weight:700">🚫 避ける</span>')
        return format_html('<span style="color:#1e7a40;font-weight:700">✅ 効く</span>')

    @admin.display(description="根拠(live/dead)")
    def evidence_brief(self, obj):
        ev = obj.evidence or {}
        return f"{ev.get('metric','')}: live={ev.get('live')} / dead={ev.get('dead')}"


# =============================================================================
# リライト改善ワークフロー（RewriteDraft）
# =============================================================================
from django.utils import timezone as _tz
from django.utils.html import escape as _esc
from apps.analytics.models import RewriteDraft, CompletedRewriteDraft, RewriteEval, ContentGap
from apps.products.management.commands.apply_draft import apply_article_content

# 管理画面(deploy)から書けるバックアップ先（/opt/claude-ops/backups は root専用のため別ディレクトリ）
_ADMIN_BACKUP_DIR = "/home/deploy/app/backups"


from django import forms as _forms


_BODY_MAX = 8   # 競合本文欄の最大数（URLがこれを超える分は先頭8件のみ本文欄を出す）
_GAP_MAX = 30   # 差分項目チェックボックスの最大数


class ContentGapForm(_forms.ModelForm):
    """競合URLは JSON ではなく『1行に1つ貼り付け』のテキストで入力する（コピペでOK）。
    競合URLの数だけ本文欄(body_0..)を出し、URLごとに本文をコピペする。"""
    competitor_urls_text = _forms.CharField(
        label="競合URL（1行に1つ貼り付け）", required=False,
        widget=_forms.Textarea(attrs={
            "rows": 4, "style": "width:90%;font-family:monospace",
            "placeholder": "https://example.com/...\nhttps://example.jp/...\n（1行に1つ・コピペでOK・JSON不要）"}),
        help_text="上位表示の競合URLを1行に1つ貼り付け。カンマ区切りも可。http/httpsが無ければ自動で補います。")

    # 競合本文欄(body_i)・差分項目の反映チェックボックス(reflect_i)を最大数だけクラス本体で静的宣言。
    # ラベル/初期値/表示有無は __init__ と get_fields で件数に応じて制御する。
    locals().update({
        f"body_{_i}": _forms.CharField(
            required=False,
            widget=_forms.Textarea(attrs={
                "rows": 8, "style": "width:95%",
                "placeholder": "このURLのページを開いて本文をコピペで貼り付け"}))
        for _i in range(_BODY_MAX)
    })
    locals().update({
        f"reflect_{_i}": _forms.BooleanField(required=False)
        for _i in range(_GAP_MAX)
    })

    class Meta:
        model = ContentGap
        fields = ("external_analysis", "gap_findings", "status")
        widgets = {
            "external_analysis": _forms.Textarea(attrs={
                "rows": 8, "style": "width:95%",
                "placeholder": "GPTの返答（◆検索意図の推定〜◆keepクエリへの影響注意）をここへそのまま貼り付け"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        urls = ((inst.competitor_urls if inst and inst.pk else []) or [])[:_BODY_MAX]
        bodies = (inst.competitor_bodies if inst and inst.pk else {}) or {}
        if inst and inst.pk:
            self.fields["competitor_urls_text"].initial = "\n".join(
                inst.competitor_urls or [])
        # 競合URLの数だけ本文貼付欄を出す（body_0..）。ラベルにURL・初期値に既存本文。
        self._body_urls = list(urls)
        for i, u in enumerate(urls):
            if f"body_{i}" in self.fields:
                self.fields[f"body_{i}"].label = f"競合本文 {i + 1}: {u}"
                self.fields[f"body_{i}"].initial = bodies.get(u, "")
        # 差分項目ごとに『反映する』チェックボックス（reflect_i）。ラベルに項目文＋フラグ。
        decisions = (inst.gap_decisions if inst and inst.pk else []) or []
        self._gap_n = min(len(decisions), _GAP_MAX)
        for i in range(self._gap_n):
            d = decisions[i]
            flags = ""
            if d.get("primary_info"):
                flags += "　【一次情報=人間の作業】"
            if d.get("keep_risk"):
                flags += "　【⚠keep毀損リスク】"
            cat = f"[{d.get('category', '')}] " if d.get("category") else ""
            self.fields[f"reflect_{i}"].label = f"反映する ▶ {cat}{d.get('item', '')}{flags}"
            self.fields[f"reflect_{i}"].initial = bool(d.get("reflect"))

    def clean_competitor_urls_text(self):
        import re as _re
        raw = self.cleaned_data.get("competitor_urls_text") or ""
        # 貼り付けミスで連結した URL も分離する: 埋め込みの http(s):// の前で改行を入れる。
        text = _re.sub(r"(https?://)", r"\n\1", raw.replace(",", "\n"))
        urls, seen = [], set()
        for line in text.splitlines():
            u = line.strip().rstrip("/")
            if not u:
                continue
            if not u.startswith(("http://", "https://")):
                u = "https://" + u
            if u not in seen:
                seen.add(u)
                urls.append(u)
        return urls

    def save(self, commit=True):
        # 競合URL（テキスト欄をパース）と、URLごとの本文を保存。
        # 本文キーは最終 competitor_urls に一致させる（正規化差でズレないように）。
        urls = self.cleaned_data.get("competitor_urls_text", [])
        self.instance.competitor_urls = urls
        bodies = {}
        for i, u in enumerate(urls[:_BODY_MAX]):
            bodies[u] = self.cleaned_data.get(f"body_{i}", "") or ""
        self.instance.competitor_bodies = bodies
        # 差分項目の反映(reflect)をチェックボックスから gap_decisions に反映
        dec = self.instance.gap_decisions or []
        for i in range(min(len(dec), _GAP_MAX)):
            dec[i]["reflect"] = bool(self.cleaned_data.get(f"reflect_{i}", False))
        self.instance.gap_decisions = dec
        return super().save(commit=commit)


class ContentGapInline(admin.StackedInline):
    """needs_work のリライト画面に表示する「上位比較(コンテンツギャップ)」パネル。
    競合URLは人が貼るだけ（取得・解析はしない）。self_outline はアプリが決定論抽出。"""
    model = ContentGap
    form = ContentGapForm
    extra = 0
    max_num = 1
    can_delete = False
    verbose_name_plural = "コンテンツギャップ（上位比較・needs_work専用）"
    readonly_fields = ("gap_panel", "gpt_prompt_panel")

    def get_fields(self, request, obj=None):
        # 競合URLの数だけ本文欄(body_i)、差分項目の数だけ反映チェック(reflect_i)を差し込む。
        urls, ndec = [], 0
        if obj is not None:
            gap = getattr(obj, "content_gap", None)
            if gap:
                urls = gap.competitor_urls or []
                ndec = len(gap.gap_decisions or [])
        body = [f"body_{i}" for i in range(min(len(urls), _BODY_MAX))]
        reflects = [f"reflect_{i}" for i in range(min(ndec, _GAP_MAX))]
        return (["gap_panel", "gpt_prompt_panel", "external_analysis",
                 "competitor_urls_text"] + body + reflects
                + ["gap_findings", "status"])

    @admin.display(description="③ GPTに渡すプロンプト（コピーして使う）")
    def gpt_prompt_panel(self, obj):
        if obj is None or not obj.pk:
            return "（保存後に表示されます）"
        from apps.analytics.learning import build_gpt_analysis_prompt
        prompt = build_gpt_analysis_prompt(obj)
        ta_id = f"gpt-prompt-{obj.pk}"
        pasted = bool((obj.external_analysis or "").strip())
        state = ('<span style="color:#1e7a40;font-weight:700">✅ GPT分析 貼り付け済み</span>'
                 if pasted else
                 '<span style="color:#9a5b00;font-weight:700">GPT分析 未貼り付け</span>')
        return mark_safe(f"""
<div style="max-width:1000px">
  <div style="background:#f2fbf4;border:1px solid #cde8d4;border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:6px">
    <b>意図ズレの現状把握（GPT併用・手動）:</b>
    下のプロンプトを「コピー」→ ブラウジングできるGPTに貼って実行 →
    返答全文を次の「<b>GPT分析結果(貼り付け)</b>」欄にそのまま貼り付けて保存。
    Claude Code のギャップ分析が、競合本文とあわせてこの内容も材料にします。　{state}
  </div>
  <textarea id="{ta_id}" readonly
    style="width:95%;height:130px;font-family:monospace;font-size:11.5px;color:#333;background:#fafafa;border:1px solid #ddd;border-radius:6px;padding:8px">{_esc(prompt)}</textarea>
  <div style="margin-top:4px">
    <button type="button" class="button"
      onclick="var t=document.getElementById('{ta_id}');navigator.clipboard.writeText(t.value).then(()=>{{this.textContent='✅ コピーしました';}});return false;">
      📋 プロンプトをコピー</button>
  </div>
</div>""")

    @admin.display(description="上位比較パネル")
    def gap_panel(self, obj):
        so = obj.self_outline or {}
        h2 = so.get("h2", []) or []
        h3 = so.get("h3", []) or []
        hrows = "".join(f"<li>{_esc(t)}</li>" for t in h2) or "<li>(なし)</li>"
        h3info = f"／ H3 {len(h3)}本" if h3 else ""
        urls = obj.competitor_urls or []
        ulinks = ("".join(
            f'<li><a href="{_esc(u)}" target="_blank" rel="noopener">{_esc(u)}</a></li>' for u in urls)
            if urls else "<li>（未設定：上のフィールドに上位2〜3本のURLを貼る）</li>")

        # Claude Code の差分分析結果 = フラグ付き選択リスト。人は reflect を選ぶ。
        decisions = obj.gap_decisions or []
        drows = []
        for i, d in enumerate(decisions):
            flags = []
            if d.get("category"):
                flags.append(f'<span style="background:#eee;border-radius:6px;padding:1px 6px">'
                             f'{_esc(str(d["category"]))}</span>')
            if d.get("primary_info"):
                flags.append('<span style="background:#fdf0dd;color:#9a5b00;border-radius:6px;'
                             'padding:1px 6px">一次情報が必要=人間の作業</span>')
            if d.get("keep_risk"):
                flags.append('<span style="background:#fdecea;color:#c0392b;border-radius:6px;'
                             'padding:1px 6px">⚠ keep毀損リスク</span>')
            mark = "☑ 反映する" if d.get("reflect") else "☐ 未反映"
            col = "#0a6" if d.get("reflect") else "#999"
            drows.append(
                f'<tr style="border-top:1px solid #eee">'
                f'<td style="padding:4px 8px;color:{col};white-space:nowrap;font-weight:700">{mark}</td>'
                f'<td style="padding:4px 8px">{_esc(str(d.get("item","")))}<div>{" ".join(flags)}</div></td></tr>')
        gap_list = (
            "<table style='border-collapse:collapse;font-size:12px;width:100%'>"
            "<thead><tr><th style='text-align:left;padding:4px 8px'>採否</th>"
            "<th style='text-align:left;padding:4px 8px'>差分項目（Claude Code分析）／フラグ</th></tr></thead>"
            "<tbody>" + "".join(drows) + "</tbody></table>"
            "<p style='color:#888;font-size:12px'>※採否は下の「<b>反映する ▶ …</b>」チェックボックスで各項目を選ぶ"
            "（初期は全て未反映＝増量の歯止め）→「➕ gap反映を指示書へ追記」。</p>"
        ) if decisions else ("<p style='color:#888'>まだ差分分析がありません。"
                             "競合URLを貼り、Claude Code に分析を依頼してください"
                             "（set_gap_analysis で投入）。</p>")

        return mark_safe(f"""
<div style="max-width:1000px">
  <div style="background:#eef6ff;border:1px solid #cfe0f5;border-radius:8px;padding:10px 14px;font-size:13px">
    <b>運用手順:</b> ①下の「GPTに渡すプロンプト」をコピーしてGPT(ブラウジング可)で実行→返答を『GPT分析結果』欄に貼る（人・任意だが推奨）
    → ②競合URLを貼る（記録・人）→ ③<b>競合ページを開いて本文をコピペで『競合ページ本文』欄に貼る（人）</b>
    ＝bot取得はブロックされるサイトが多いため、貼った本文を分析する → ④「🔍 Claude Codeに差分分析を依頼」→
    Claude Code が対象クエリ「{_esc(obj.target_query)}」の意図でGPT分析＋競合本文を材料に差分を網羅分析しフラグ付きで下の選択リストに投入 →
    ⑤人が<b>反映する/しない</b>を選ぶ（初期は全て未反映）→ ⑥「gap反映を指示書へ追記」。
    <b>網羅分析でも採否で厳選＝増量にしない。keepクエリを壊さない。競合の全コピー禁止。</b>
  </div>
  <div style="display:flex;gap:16px;margin:8px 0">
    <div style="flex:1">
      <b>自記事アウトライン（H2{len(h2)}本{h3info}／FAQ {'あり' if so.get('faq') else 'なし'}）</b>
      <ol style="font-size:12px">{hrows}</ol>
    </div>
    <div style="flex:1">
      <b>競合URL（記録）</b>
      <ul style="font-size:12px">{ulinks}</ul>
      <b>競合ページ本文（URLごとにコピペ）: {('✅ ' + str(sum(1 for v in (obj.competitor_bodies or {}).values() if (v or '').strip())) + '/' + str(len(obj.competitor_urls or [])) + '件 貼付済') if (obj.competitor_urls or []) else '先にURLを貼る'}</b>
    </div>
  </div>
  <b>差分の選択リスト（Claude Code 分析 → 人が採否）</b>
  {gap_list}
</div>""")

_RD_STATUS_STYLE = {
    "pending": ("#666", "#eee"), "instructed": ("#1456a0", "#e6effb"),
    "drafting": ("#9a5b00", "#fdf0dd"), "in_review": ("#9a5b00", "#fff3d6"),
    "approved": ("#1e7a40", "#e7f6ec"), "applied": ("#0b5", "#dff5e8"),
    "rejected": ("#c0392b", "#fdecea"),
}


class ManualRewriteAddForm(_forms.Form):
    """作業台への手動追加フォーム（対象記事＋基準記事）。

    記事の選択は admin 標準の AutocompleteSelect（Select2・title/slug をサーバー側検索）。
    admin_site を渡すとオートコンプリート化する（AJAX先は analytics_rewritedraft の
    article / reference_article フィールド＝autocomplete_fields 宣言済み）。
    """
    article = _forms.ModelChoiceField(
        label="リライト対象記事", queryset=None,
        help_text="作業台に入れて書き直す記事を、タイトル/slugで検索して選びます。")
    reference_article = _forms.ModelChoiceField(
        label="基準記事（お手本・任意）", queryset=None, required=False,
        help_text="この記事の構成・粒度・トーンを基準に再構築します（空でも可）。")
    keywords = _forms.CharField(
        label="狙うキーワード（1行に1つ・任意）", required=False,
        widget=_forms.Textarea(attrs={
            "rows": 4, "style": "width:32em;font-family:monospace",
            "placeholder": "美容家電 買取\n美顔器 売る\n（1行に1つ・カンマ区切りも可）"}),
        help_text="新規記事などGSCデータが無い記事向け。先頭が主クエリ（タイトル/導入の"
                  "キーワード一致指示に反映）。入力すると grow/獲得クエリにも入ります。")
    force = _forms.BooleanField(
        label="未完の下書きがあっても新規作成する", required=False)

    def __init__(self, *args, admin_site=None, **kwargs):
        from django.contrib.admin.widgets import AutocompleteSelect
        from apps.products.models import Article
        super().__init__(*args, **kwargs)
        if admin_site is not None:
            # 先にウィジェットを差し替えてから queryset を設定する
            # （queryset setter が widget.choices に伝播するため順序が重要）。
            _ac_attrs = {"data-width": "32em"}
            self.fields["article"].widget = AutocompleteSelect(
                RewriteDraft._meta.get_field("article"), admin_site, attrs=_ac_attrs)
            self.fields["reference_article"].widget = AutocompleteSelect(
                RewriteDraft._meta.get_field("reference_article"), admin_site, attrs=_ac_attrs)
        qs = Article.objects.all()
        self.fields["article"].queryset = qs
        self.fields["reference_article"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        art, ref = cleaned.get("article"), cleaned.get("reference_article")
        if art and ref and art.pk == ref.pk:
            raise _forms.ValidationError("基準記事に対象記事と同じ記事は選べません。")
        return cleaned


@admin.register(RewriteDraft)
class RewriteDraftAdmin(admin.ModelAdmin):
    """記事(URL)単位のリライト作業台。1本のレビュー画面に指示書・query_portfolio・keep/grow・
    ContentGap(上位比較)・現本文↔案の左右比較・承認反映を集約。全クエリ考慮で keep を守る。"""
    change_form_template = "admin/analytics/rewritedraft/change_form.html"
    change_list_template = "admin/analytics/rewritedraft/change_list.html"
    list_display = ("article_link", "src_disp", "bucket_disp", "grow_disp", "keep_disp",
                    "cur_position", "cur_impressions", "status_badge",
                    "gap_status", "checklist_progress")
    list_filter = ("status", "is_manual", "source_triage__bucket", "source_triage__run")
    search_fields = ("article__slug", "article__title", "target_query",
                     "reference_article__slug", "reference_article__title")
    ordering = ("-src_impressions", "-created_at")
    list_select_related = ("article", "source_triage", "content_gap",
                           "reference_article")
    # article は変更フォームには出さないが、手動追加フォームの記事検索
    # （AutocompleteSelect の AJAX 権限チェック）で必要なため宣言する。
    autocomplete_fields = ("article", "reference_article")
    inlines = (ContentGapInline,)
    actions = ("act_generate", "act_approve_apply", "act_reject")
    # 完了(反映済=applied)ぶんは「リライト完了一覧」に分離するため作業台からは除外する。
    EXCLUDE_STATUSES = ("applied",)

    # 素の追加フォームは readonly の review_panel が未保存(article=None)で壊れるため無効化。
    # 追加は object-tools の「記事を手動で追加」ボタン（add_manual_view）に一本化する。
    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.EXCLUDE_STATUSES:
            qs = qs.exclude(status__in=self.EXCLUDE_STATUSES)
        return qs

    readonly_fields = ("review_panel", "src_best_position", "src_impressions",
                       "target_query", "status", "created_at", "instructed_at",
                       "reviewed_at", "applied_at", "source_triage")
    # target_keep / target_grow は画面で編集して確定する（機械提案の初期値を人間が調整）
    # ※巨大な draft_content 欄を折りたたみにして、下部の ContentGap（差分取得）パネルへ
    #   スクロールで届くようにする。差分の概要は上部の review_panel にも表示する。
    fieldsets = (
        (None, {"fields": ("review_panel",)}),
        ("基準記事（お手本・任意）", {"fields": ("reference_article",),
                            "description": "この記事の構成・粒度・トーンを基準に再構築する。"
                            "変更したら『指示書を再生成』で反映できます。"}),
        ("keep / grow（編集）", {"fields": ("target_grow", "target_keep")}),
        ("本文案（Claude Code が執筆・ここで編集して承認反映）",
         {"fields": ("draft_title", "draft_content", "diff_summary"),
          "classes": ("collapse",)}),
        ("レビュー", {"fields": ("reviewer_note", "status")}),
        ("学習ループ（反映時に戦術を記録・判定確定後に学びを追記）",
         {"fields": ("applied_tactics", "lesson"),
          "classes": ("collapse",),
          "description": "applied_tactics は learning.TACTICS のキーのリスト。"
                         "lesson は learn_rewrites が判定確定後に起票し、"
                         "【分析】行へ要因分析を追記する。次回の指示書に自動で供給される。"}),
        ("メタ情報", {"fields": ("target_query", "src_best_position", "src_impressions",
                              "source_triage", "created_at", "instructed_at",
                              "reviewed_at", "applied_at"),
                   "classes": ("collapse",)}),
    )

    # ---- list 表示 ----
    @admin.display(description="記事(URL)")
    def article_link(self, obj):
        return format_html('/{}/　<a href="https://sc-tsusho.jp/{}/" target="_blank" '
                           'rel="noopener">↗</a>', obj.article.slug, obj.article.slug)

    @admin.display(description="由来")
    def src_disp(self, obj):
        if obj.is_manual:
            ref = (f'<br><span style="color:#888">基準:/{_esc(obj.reference_article.slug)}/</span>'
                   if obj.reference_article_id else "")
            return format_html('<span style="padding:1px 8px;border-radius:8px;font-weight:700;'
                               'color:#5b3a00;background:#ffe9b3">手動</span>{}', mark_safe(ref))
        return format_html('<span style="color:#888">GSC</span>')

    @admin.display(description="種別")
    def bucket_disp(self, obj):
        b = obj.source_triage.bucket if obj.source_triage else "-"
        fg, bg, label = _BUCKET_STYLE.get(b, ("#000", "#fff", b))
        return format_html('<span style="padding:1px 8px;border-radius:8px;font-weight:700;'
                           'color:{};background:{}">{}</span>', fg, bg, b)

    @admin.display(description="📈grow")
    def grow_disp(self, obj):
        g = obj.target_grow or []
        head = g[0].get("query") if g and isinstance(g[0], dict) else ""
        return f"{head}（{len(g)}）" if g else "-"

    @admin.display(description="🛡keep数")
    def keep_disp(self, obj):
        return len(obj.target_keep or [])

    @admin.display(description="gap")
    def gap_status(self, obj):
        g = getattr(obj, "content_gap", None)
        return g.get_status_display() if g else "-"

    @admin.display(description="現順位", ordering="src_best_position")
    def cur_position(self, obj):
        return obj.src_best_position

    @admin.display(description="表示", ordering="src_impressions")
    def cur_impressions(self, obj):
        return obj.src_impressions

    @admin.display(description="状態", ordering="status")
    def status_badge(self, obj):
        fg, bg = _RD_STATUS_STYLE.get(obj.status, ("#000", "#fff"))
        return format_html('<span style="padding:2px 10px;border-radius:10px;font-weight:700;'
                           'color:{};background:{}">{}</span>', fg, bg, obj.get_status_display())

    @admin.display(description="チェック")
    def checklist_progress(self, obj):
        items = obj.checklist or []
        ok = sum(1 for c in items if c.get("ok") is True)
        ng = sum(1 for c in items if c.get("ok") is False)
        return f"OK{ok} / NG{ng} / 計{len(items)}"

    # ---- 詳細レビューパネル（指示書＋左右比較＋チェックリスト）----
    @admin.display(description="レビューパネル")
    def review_panel(self, obj):
        cur = obj.article.content or ""
        draft = obj.draft_content or "(案未投入。Claude Code が指示書に沿って執筆し投入します)"
        rows = []
        for c in (obj.checklist or []):
            mark = {True: "✅OK", False: "🔴要対応", None: "⬜要確認"}.get(c.get("ok"), "⬜")
            rows.append(f'<li><b>{mark}</b> {_esc(c.get("label",""))} '
                        f'<span style="color:#888">— {_esc(c.get("note",""))}</span></li>')
        checklist_html = "<ul>" + "".join(rows) + "</ul>" if rows else "(なし)"

        # query_portfolio 表（keep/grow をマーク）。タイトル変更が keep に与える影響を確認する。
        keepset = {q.get("query") for q in (obj.target_keep or [])}
        growset = {q.get("query") for q in (obj.target_grow or [])}
        prows = []
        for q in (obj.query_portfolio or []):
            name = q.get("query", "")
            tag = ("<span style='color:#0a6;font-weight:700'>📈grow</span>" if name in growset
                   else "<span style='color:#1456a0;font-weight:700'>🛡keep</span>" if name in keepset
                   else "")
            prows.append(
                f"<tr><td style='padding:2px 8px'>{tag}</td>"
                f"<td style='padding:2px 8px'>{_esc(name)}</td>"
                f"<td style='padding:2px 8px;text-align:right'>{q.get('position')}位</td>"
                f"<td style='padding:2px 8px;text-align:right'>{q.get('impressions',0)}</td>"
                f"<td style='padding:2px 8px;text-align:right'>{q.get('clicks',0)}</td></tr>")
        portfolio_html = (
            "<table style='border-collapse:collapse;font-size:12px'><thead><tr>"
            "<th></th><th style='text-align:left;padding:2px 8px'>クエリ</th>"
            "<th style='padding:2px 8px'>順位</th><th style='padding:2px 8px'>表示</th>"
            "<th style='padding:2px 8px'>click</th></tr></thead><tbody>"
            + "".join(prows) + "</tbody></table>") if prows else "(クエリ明細なし)"

        # 差分取得（ContentGap）を上部にも表示＝needs_workで即座に見えるように。
        gap = getattr(obj, "content_gap", None)
        gap_section = ""
        if gap is not None:
            urls = gap.competitor_urls or []
            ulinks = (" ／ ".join(
                f'<a href="{_esc(u)}" target="_blank" rel="noopener">{_esc(u)}</a>' for u in urls)
                if urls else "<span style='color:#c0392b'>競合URL未設定（下部パネルに貼付）</span>")
            decisions = gap.gap_decisions or []
            grows = []
            for d in decisions:
                flags = []
                if d.get("category"):
                    flags.append(f"<span style='background:#eee;border-radius:6px;padding:0 6px'>{_esc(str(d['category']))}</span>")
                if d.get("primary_info"):
                    flags.append("<span style='background:#fdf0dd;color:#9a5b00;border-radius:6px;padding:0 6px'>一次情報=人間作業</span>")
                if d.get("keep_risk"):
                    flags.append("<span style='background:#fdecea;color:#c0392b;border-radius:6px;padding:0 6px'>⚠keep毀損リスク</span>")
                mk = "☑反映" if d.get("reflect") else "☐未反映"
                col = "#0a6" if d.get("reflect") else "#999"
                grows.append(f"<tr><td style='color:{col};font-weight:700;padding:2px 8px;white-space:nowrap'>{mk}</td>"
                             f"<td style='padding:2px 8px'>{_esc(str(d.get('item','')))}<div>{' '.join(flags)}</div></td></tr>")
            gaptbl = ("<table style='border-collapse:collapse;font-size:12px;width:100%'>"
                      "<tbody>" + "".join(grows) + "</tbody></table>") if decisions else \
                     "<span style='color:#888'>まだ差分分析なし（競合URLを貼り、Claude Code が分析投入）</span>"
            gap_section = f"""
  <h3 style="margin:.8em 0 .2em;background:#eef6ff;padding:6px 10px;border-radius:6px">
    🔍 差分取得（コンテンツギャップ）　status: {_esc(gap.get_status_display())}</h3>
  <div style="font-size:12px;margin-bottom:4px">競合URL: {ulinks}</div>
  <div style="font-size:12px">差分の選択リスト（Claude Code 分析／採否）:</div>
  {gaptbl}
  <p style="color:#888;font-size:12px">▼ 競合URL/本文の貼付と、各項目の<b>採否チェックボックス</b>は、このページ下部の
    「<b>コンテンツギャップ（上位比較・needs_work専用）</b>」欄に。選んだら送信行の
    「➕ gap反映を指示書へ追記」ボタンで確定します。</p>"""

        return mark_safe(f"""
<div style="max-width:1100px">
  <div style="background:#fff8e1;border:1.5px solid #ffe08a;border-radius:8px;padding:10px 14px;font-size:13px">
    <b>★ 最上位制約:</b> この記事は複数クエリで表示されている。<b>target_grow を伸ばす</b>のが目的だが、
    <b>target_keep の既存クエリを毀損しない</b>こと。両立可能なら統合、不可なら keep の強い方を守る。
    単一クエリへの機械的な寄せ最適化をしない。keep/grow の最終確定は下のフィールドで人間が調整する。
  </div>
  <h3 style="margin:.6em 0 .2em">獲得クエリ一覧（query_portfolio・順位昇順／🛡keep・📈grow）</h3>
  <div>{portfolio_html}</div>
  {gap_section}
  <h3 style="margin:.6em 0 .2em">指示書
    <button type="button" onclick="(function(b){{navigator.clipboard.writeText(
      document.getElementById('rd-instructions').innerText).then(function(){{
      var t=b.textContent;b.textContent='✅ コピーしました';setTimeout(function(){{b.textContent=t;}},1500);}},
      function(){{b.textContent='コピー失敗(手動で選択してください)';}});}})(this);return false;"
      style="margin-left:10px;padding:3px 12px;font-size:12px;font-weight:700;cursor:pointer;
      background:#6a1b9a;color:#fff;border:none;border-radius:6px">📋 指示書をコピー</button></h3>
  <pre id="rd-instructions" style="white-space:pre-wrap;background:#f7f7f9;border:1px solid #e2e2e8;border-radius:8px;
       padding:12px;font-size:12px;line-height:1.6">{_esc(obj.instructions or '')}</pre>
  <h3 style="margin:.6em 0 .2em">チェックリスト（プレイブック照合）</h3>
  <div style="font-size:13px">{checklist_html}</div>
  <h3 style="margin:.6em 0 .2em">現本文 ↔ 案 の左右比較（HTMLソース）</h3>
  <div style="display:flex;gap:12px">
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;color:#666">現本文（{len(cur)}字）</div>
      <pre style="white-space:pre-wrap;word-break:break-all;height:420px;overflow:auto;
           background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px;
           font-size:11px">{_esc(cur)}</pre>
    </div>
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;color:#0a6">案本文（{len(obj.draft_content or '')}字・下で編集可）</div>
      <pre style="white-space:pre-wrap;word-break:break-all;height:420px;overflow:auto;
           background:#f6fff9;border:1px solid #b9e6cd;border-radius:8px;padding:10px;
           font-size:11px">{_esc(draft)}</pre>
    </div>
  </div>
  <p style="color:#888;font-size:12px">※下の draft_title / draft_content を編集して最終調整→
     「承認して反映」で実記事へ反映（apply_draft 共有経路・last_rewritten_at 自動更新）。</p>
</div>""")

    # ---- 反映ロジック（共有関数を再利用＝last_rewritten_at は二重実装しない）----
    def _apply(self, request, obj):
        if obj.status == "applied":
            self.message_user(request, f"#{obj.id} は既に反映済み", level=30); return
        if not (obj.draft_content or "").strip():
            self.message_user(request, f"#{obj.id} は案本文が空のため反映できません", level=40); return
        title = obj.draft_title.strip() or None
        # draft_title は H1(title) と <title>(meta_title) の両方に反映（タイトル一致レバー）
        apply_article_content(
            obj.article, content=obj.draft_content, title=title, meta_title=title,
            backup_dir=_ADMIN_BACKUP_DIR, source=f"rewrite_draft#{obj.id}")
        obj.status = "applied"; obj.applied_at = _tz.now()
        obj.save(update_fields=["status", "applied_at"])
        self.message_user(
            request,
            f"✅ #{obj.id} を /{obj.article.slug}/ に反映。last_rewritten_at 更新済み"
            f"（title{'変更' if title else '据え置き'}）")

    def _reject(self, request, obj):
        obj.status = "rejected"; obj.save(update_fields=["status"])
        self.message_user(request, f"#{obj.id} を却下しました（理由は reviewer_note に）")

    def _generate(self, request, obj):
        from django.core.management import call_command
        # 該当記事の指示書を作り直す（force=既存があっても新規Draft）
        from io import StringIO
        buf = StringIO()
        run_id = obj.source_triage.run_id if obj.source_triage else None
        opts = {"force": True}
        if run_id:
            opts["run"] = run_id
        call_command("make_rewrite_instructions", stdout=buf, **opts)
        self.message_user(request, "指示書を再生成しました（新しい Draft を確認してください）")

    # ---- change form のボタン（承認反映/却下）----
    def change_view(self, request, object_id, form_url="", extra_context=None):
        """作業台を開いたとき ContentGap が無ければ自動作成する。

        従来は needs_work のトリアージ経由でのみ作成していたため、quick_win や
        手動追加（コックピットの「作業台へ」含む）の下書きにはギャップ欄＝
        GPT分析プロンプトが表示されなかった。作業中の下書きなら常に用意する
        （applied/rejected の閲覧では作らない）。
        """
        obj = self.get_object(request, object_id)
        if (obj is not None and obj.status not in ("applied", "rejected")
                and not ContentGap.objects.filter(rewrite_draft=obj).exists()):
            from apps.analytics.management.commands.make_rewrite_instructions import (
                extract_self_outline)
            ContentGap.objects.create(
                rewrite_draft=obj,
                target_query=obj.target_query or "",
                self_outline=extract_self_outline(obj.article.content),
                status="pending",
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        if "_approve_apply" in request.POST:
            self._apply(request, obj)
            return self._redirect_change(obj)
        if "_reject" in request.POST:
            self._reject(request, obj)
            return self._redirect_change(obj)
        if "_regen_manual" in request.POST:
            self._regen_manual(request, obj)
            return self._redirect_change(obj)
        if "_gap_seed" in request.POST:
            self._gap_seed(request, obj)
            return self._redirect_change(obj)
        if "_gap_request_analysis" in request.POST:
            self._gap_request_analysis(request, obj)
            return self._redirect_change(obj)
        if "_gap_apply" in request.POST:
            self._gap_apply(request, obj)
            return self._redirect_change(obj)
        return super().response_change(request, obj)

    def _gap_request_analysis(self, request, obj):
        """差分分析を Claude Code に依頼（アプリはLLMを呼ばない）。競合URLを確認し状態を進める。
        実際の取得・分析・投入は Claude Code が set_gap_analysis で行う。"""
        gap = getattr(obj, "content_gap", None)
        if not gap:
            self.message_user(request, "この下書きにコンテンツギャップはありません（needs_work専用）", level=30); return
        filled = {u: v for u, v in (gap.competitor_bodies or {}).items() if (v or "").strip()}
        if not filled:
            self.message_user(
                request,
                "先に各競合URLの『競合本文』欄に、競合ページを開いて本文をコピペで貼ってください"
                "（bot取得はブロックされるサイトが多いため、貼った本文を分析します）。", level=40)
            return
        if gap.status == "pending":
            gap.status = "urls_set"
            gap.save(update_fields=["status", "updated_at"])
        total = sum(len(v) for v in filled.values())
        self.message_user(
            request,
            f"🔍 差分分析を依頼しました（貼付本文 {len(filled)}件・計{total}字）。"
            f"Claude Code に『RewriteDraft #{obj.id} の競合ギャップを分析して』と伝えてください。"
            f"Claude Code が貼られた競合本文と自記事の差分をフラグ付きで選択リストに投入します"
            f"（アプリはLLMを呼びません・bot取得もしません）。",
            level=20)

    # ---- コンテンツギャップ（needs_work・上位比較）----
    def _gap_seed(self, request, obj):
        """gap_findings の各行から採否リスト(gap_decisions)を生成（初期は全て reflect=False＝増量の歯止め）。"""
        gap = getattr(obj, "content_gap", None)
        if not gap:
            self.message_user(request, "この下書きにコンテンツギャップはありません（needs_work専用）", level=30); return
        lines = [ln.strip("・-–— \t") for ln in (gap.gap_findings or "").splitlines() if ln.strip()]
        if not lines:
            self.message_user(request, "gap_findings が空です。先に欠けている本質要素を記入してください", level=40); return
        existing = {d.get("item"): d for d in (gap.gap_decisions or [])}
        gap.gap_decisions = [
            existing.get(ln, {"item": ln, "reflect": False, "primary_info": False}) for ln in lines
        ]
        if gap.status in ("pending", "urls_set"):
            gap.status = "analyzed"
        gap.save(update_fields=["gap_decisions", "status", "updated_at"])
        self.message_user(
            request, f"採否リストを{len(lines)}件生成しました（全て未反映で開始）。"
            "reflect を true にした項目だけが『gap反映を指示書へ追記』で渡ります")

    def _gap_apply(self, request, obj):
        """reflect=True の gap 項目のみを instructions に追記（keep保護・非増量の制約つき）。"""
        gap = getattr(obj, "content_gap", None)
        if not gap:
            self.message_user(request, "この下書きにコンテンツギャップはありません", level=30); return
        decisions = gap.gap_decisions or []
        chosen = [d for d in decisions if d.get("reflect")]
        primary = [d for d in chosen if d.get("primary_info")]
        rest = [d for d in chosen if not d.get("primary_info")]
        risk = [d for d in rest if d.get("keep_risk")]
        add_items = [d for d in rest if not d.get("keep_risk")]
        if not chosen:
            self.message_user(request, "『reflect=true』の項目がありません。採否で反映する要素を選んでください", level=40); return
        block = ["\n─────────────────────────────",
                 "■ コンテンツギャップ反映（上位比較で特定・採用した意図充足要素）",
                 "  ※増量目的ではなく、検索意図を満たすための要素追加/構成変更として反映する。"
                 "keepクエリ(query_portfolio)を壊さないこと。競合の全コピーをしない。"]
        if add_items:
            block.append("  【反映する要素（記事に加える/構成を直す）】")
            block += [f"   - {d['item']}" for d in add_items]
        if risk:
            block.append("  【⚠ keep毀損リスクあり＝keepを壊さない条件付きで反映（タイトル/見出しへの影響を必ず確認）】")
            block += [f"   - {d['item']}" for d in risk]
        if primary:
            block.append("  【一次情報が必要＝人間の作業（要素追加では埋まらない）】")
            block += [f"   - {d['item']}" for d in primary]
        if gap.competitor_urls:
            block.append("  参考にした競合URL: " + " / ".join(gap.competitor_urls))
        # 既存の反映ブロックがあれば置換（重複追記を防ぐ）
        marker = "■ コンテンツギャップ反映"
        base = obj.instructions or ""
        if marker in base:
            base = base[:base.index("\n─────────────────────────────\n■ コンテンツギャップ反映")] \
                if "\n─────────────────────────────\n■ コンテンツギャップ反映" in base else base
        obj.instructions = base + "\n".join(block)
        obj.save(update_fields=["instructions"])
        gap.status = "reviewed"
        gap.save(update_fields=["status", "updated_at"])
        self.message_user(
            request, f"gap反映: 要素追加{len(add_items)}件 / keep毀損リスク{len(risk)}件(条件付き) / "
                     f"一次情報要{len(primary)}件(人間作業) を指示書に追記")

    def _redirect_change(self, obj):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(reverse("admin:analytics_rewritedraft_change", args=[obj.id]))

    # ---- 手動で記事を作業台に追加 ----
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path("add-manual/", self.admin_site.admin_view(self.add_manual_view),
                 name="analytics_rewritedraft_add_manual"),
        ]
        return custom + urls

    def add_manual_view(self, request):
        from django.http import HttpResponseRedirect
        from django.shortcuts import render
        from apps.analytics.rewrite_manual import (
            create_manual_rewrite_draft, ManualRewriteError)

        if request.method == "POST":
            form = ManualRewriteAddForm(request.POST, admin_site=self.admin_site)
            if form.is_valid():
                try:
                    rd = create_manual_rewrite_draft(
                        form.cleaned_data["article"],
                        reference_article=form.cleaned_data.get("reference_article"),
                        force=form.cleaned_data.get("force"),
                        keywords=form.cleaned_data.get("keywords"))
                except ManualRewriteError as e:
                    self.message_user(request, str(e), level=40)
                else:
                    ref = rd.reference_article
                    self.message_user(
                        request,
                        f"✅ 作業台に追加: /{rd.article.slug}/（手動・status=指示書生成済"
                        + (f"・基準記事 /{ref.slug}/" if ref else "") + "）")
                    return HttpResponseRedirect(
                        reverse("admin:analytics_rewritedraft_change", args=[rd.id]))
        else:
            form = ManualRewriteAddForm(admin_site=self.admin_site)

        ctx = {
            **self.admin_site.each_context(request),
            "title": "リライト作業台に記事を手動追加",
            "form": form,
            "opts": self.model._meta,
        }
        return render(request, "admin/analytics/rewritedraft/add_manual.html", ctx)

    def _regen_manual(self, request, obj):
        """基準記事の変更などを反映して、この手動下書きの指示書を作り直す（in-place）。
        GSCデータが無い記事は、現在の target_grow の手入力キーワードを引き継いで再生成する。"""
        from apps.analytics.rewrite_manual import build_manual_payload
        if not obj.is_manual:
            self.message_user(
                request, "GSCトリアージ由来の下書きは一覧の『指示書を生成/再生成』を使ってください。",
                level=30)
            return
        # GSCデータが無ければ、既存の query_portfolio（手入力キーワード全件・先頭が主）を
        # 種として引き継ぐ。target_grow だと主クエリしか残らず副キーワードが失われるため。
        kws = None
        if not ArticleTriage.objects.filter(article=obj.article).exists():
            kws = [q.get("query") for q in (obj.query_portfolio or []) if q.get("query")]
        meta, instr, checklist, refs, portfolio, keep, grow = build_manual_payload(
            obj.article, obj.reference_article, keywords=kws)
        obj.target_query = meta["target_query"]
        obj.src_best_position = meta["src_best_position"]
        obj.src_impressions = meta["src_impressions"]
        obj.instructions = instr
        obj.checklist = checklist
        obj.playbook_refs = refs
        obj.query_portfolio = portfolio
        obj.target_keep = keep
        obj.target_grow = grow
        obj.instructed_at = _tz.now()
        obj.save(update_fields=["target_query", "src_best_position", "src_impressions",
                                "instructions", "checklist", "playbook_refs",
                                "query_portfolio", "target_keep", "target_grow",
                                "instructed_at"])
        ref = obj.reference_article
        self.message_user(
            request, "指示書を再生成しました"
            + (f"（基準記事 /{ref.slug}/ を反映）" if ref else "（基準記事なし）")
            + (f"／キーワード{len(kws)}件を引き継ぎ" if kws else ""))

    # ---- list actions ----
    @admin.action(description="✍ 指示書を生成/再生成（quick_win 全体）")
    def act_generate(self, request, obj_qs):
        from django.core.management import call_command
        from io import StringIO
        call_command("make_rewrite_instructions", stdout=StringIO())
        self.message_user(request, "make_rewrite_instructions を実行しました")

    @admin.action(description="✅ 承認して実記事へ反映（apply）")
    def act_approve_apply(self, request, obj_qs):
        for obj in obj_qs:
            self._apply(request, obj)

    @admin.action(description="🚫 却下")
    def act_reject(self, request, obj_qs):
        for obj in obj_qs:
            self._reject(request, obj)


@admin.register(CompletedRewriteDraft)
class CompletedRewriteDraftAdmin(RewriteDraftAdmin):
    """リライト完了一覧（反映済=applied のみ）。作業台から完了ぶんを分離した閲覧用。
    一覧は反映日時の新しい順。既存レビュー画面(review_panel)はそのまま閲覧できる。"""
    # 完了ぶんだけを表示（作業台は applied を除外、こちらは applied だけを含める）
    EXCLUDE_STATUSES = ()

    def get_queryset(self, request):
        return super(RewriteDraftAdmin, self).get_queryset(request).filter(status="applied")

    list_display = ("article_link", "bucket_disp", "grow_disp", "keep_disp",
                    "cur_position", "cur_impressions", "status_badge",
                    "applied_at", "checklist_progress")
    ordering = ("-applied_at", "-src_impressions")
    # 完了ぶんは閲覧のみ：新規追加・生成/承認/却下アクションは出さない
    actions = None
    # 手動追加ボタン付きテンプレは使わない（完了一覧は閲覧専用・素の一覧に戻す）
    change_list_template = None

    # 手動追加の custom URL(add-manual/) は作業台(rewritedraft)だけに置く。
    # ここで RewriteDraftAdmin.get_urls を継承すると URL 名が重複するため素の get_urls に戻す。
    def get_urls(self):
        return super(RewriteDraftAdmin, self).get_urls()

    def has_add_permission(self, request):
        return False


# =============================================================================
# リライト効果測定（パートC-3 可視化）
# =============================================================================
from datetime import timedelta
from django.conf import settings as _settings
from django.utils import timezone as _tz2

# eval_status → (前景色, 背景色, 日本語)
_EVAL_STYLE = {
    "reached_p1": ("#065f46", "#c9f2dc", "1ページ目到達"),
    "improved":   ("#1e7a40", "#e7f6ec", "改善"),
    "flat":       ("#9a5b00", "#fff3d6", "横ばい"),
    "declined":   ("#c0392b", "#fdecea", "悪化"),
    "pending_eval": ("#555", "#eaeaea", "結果待ち"),
}


@admin.register(RewriteEval)
class RewriteEvalAdmin(admin.ModelAdmin):
    """リライト効果測定ビュー（applied のみ）。measure_rewrites が更新した eval_* を可視化。
    ★観察期間中(21日未満)は pending_eval のみ＝アラートは出さない（測定側で保証）。"""
    change_list_template = "admin/analytics/rewriteeval/change_list.html"
    list_display = ("article_link", "grow_query", "grow_move", "grow_delta",
                    "eval_badge", "days_disp", "keep_flag", "lesson_flag", "measured_at")
    list_filter = ("eval_status", "keep_damaged")
    search_fields = ("article__slug", "article__title", "target_query")
    ordering = ("-keep_damaged", "eval_status", "-src_impressions")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # 一覧は見せるが個別編集はさせない（閲覧専用）
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(status="applied").select_related("article", "source_triage")

    @admin.display(description="記事(URL)")
    def article_link(self, obj):
        return format_html('/{}/　<a href="https://sc-tsusho.jp/{}/" target="_blank" rel="noopener">↗</a>',
                           obj.article.slug, obj.article.slug)

    @admin.display(description="target_grow")
    def grow_query(self, obj):
        return obj.target_query or "-"

    @admin.display(description="順位 before→after")
    def grow_move(self, obj):
        gb = obj.grow_before if obj.grow_before is not None else "-"
        ga = obj.grow_after if obj.grow_after is not None else "—"
        return format_html("{} → {}", gb, ga)

    @admin.display(description="改善幅")
    def grow_delta(self, obj):
        if obj.grow_before is None or obj.grow_after is None:
            return "-"
        d = obj.grow_before - obj.grow_after  # 正=改善(順位が小さくなった)
        if d > 0:
            return format_html('<span style="color:#1e7a40;font-weight:700">▲{}位改善</span>', round(d, 2))
        if d < 0:
            return format_html('<span style="color:#c0392b;font-weight:700">▼{}位悪化</span>', round(-d, 2))
        return "±0"

    @admin.display(description="効果判定")
    def eval_badge(self, obj):
        fg, bg, label = _EVAL_STYLE.get(obj.eval_status, ("#000", "#fff", obj.eval_status))
        return format_html('<span style="padding:2px 10px;border-radius:10px;font-weight:700;'
                           'color:{};background:{}">{}</span>', fg, bg, label)

    @admin.display(description="経過日数")
    def days_disp(self, obj):
        if obj.days_since_applied is None:
            return "-"
        eval_days = _settings.REWRITE_EVAL_DAYS
        if obj.eval_status == "pending_eval" and obj.applied_at:
            ready = (obj.applied_at + timedelta(days=eval_days)).date()
            left = (ready - _tz2.now().date()).days
            return format_html('{}日 <span style="color:#888">(判定 {} / あと{}日)</span>',
                               obj.days_since_applied, ready, max(left, 0))
        return format_html("{}日", obj.days_since_applied)

    @admin.display(description="keep", boolean=False)
    def keep_flag(self, obj):
        if obj.keep_damaged:
            return format_html('<span style="color:#c0392b;font-weight:800">⚠ 巻き添え毀損</span>')
        return format_html('<span style="color:#1e7a40">OK</span>')

    @admin.display(description="学び")
    def lesson_flag(self, obj):
        if not obj.lesson_recorded_at:
            return format_html('<span style="color:#888">—</span>')
        url = reverse("admin:analytics_rewritedraft_change", args=[obj.id])
        if "未記入" in (obj.lesson or ""):
            return format_html('<a href="{}" style="color:#9a5b00;font-weight:700">起票済(分析待ち)</a>', url)
        return format_html('<a href="{}" style="color:#1e7a40;font-weight:700">記録済</a>', url)

    def changelist_view(self, request, extra_context=None):
        """効果測定レポートを一覧の上に出す。

        「何を狙って書き換え、順位と露出がどれだけ動いたか」を before→after で見せる。
        着手時(src_* / query_portfolio)と反映後最新トリアージはどちらも直近28日窓なので
        表示回数・クリックは直接比較できる。判定・アラートの規律は measure_rewrites 側の
        ままで、ここは可視化のみ（21日未経過の判定は出さない）。
        """
        from apps.analytics.management.commands.measure_rewrites import (
            _latest_post_apply_triage, _norm_q)

        eval_days = _settings.REWRITE_EVAL_DAYS
        today = _tz2.now().date()
        SETTLED = ("reached_p1", "improved", "flat", "declined")
        _RANK = {"reached_p1": 0, "improved": 1, "flat": 2, "declined": 3}

        judged, observing, stalled, waiting, alerts = [], [], [], [], []
        sum_imp_before = sum_imp_after = sum_clicks_before = sum_clicks_after = 0
        sum_new_queries = 0
        deltas = []

        base = (RewriteDraft.objects.filter(status="applied")
                .select_related("article", "source_triage").order_by("id"))
        for rd in base:
            slug = rd.article.slug
            change_url = reverse("admin:analytics_rewritedraft_change", args=[rd.id])
            triage = _latest_post_apply_triage(rd.article, rd.applied_at) if rd.applied_at else None
            applied_date = _tz2.localtime(rd.applied_at).date() if rd.applied_at else None
            days = (today - applied_date).days if applied_date else None

            # 露出 before/after（どちらも直近28日窓のページ合計）
            imp_before = rd.src_impressions
            clicks_before = rd.source_triage.clicks if rd.source_triage else None
            imp_after = triage.impressions if triage else None
            clicks_after = triage.clicks if triage else None

            # 露出点: 着手時ポートフォリオに無かった獲得クエリ（表示回数降順）
            before_qs = {_norm_q(q.get("query")) for q in (rd.query_portfolio or [])
                         if isinstance(q, dict)}
            new_queries = []
            if triage:
                for q in sorted((triage.queries or []),
                                key=lambda x: -(x.get("impressions") or 0)):
                    if isinstance(q, dict) and _norm_q(q.get("query")) not in before_qs:
                        new_queries.append({"query": q.get("query"),
                                            "position": q.get("position"),
                                            "impressions": q.get("impressions")})

            row = {
                "slug": slug, "url": change_url,
                "site_url": f"https://sc-tsusho.jp/{slug}/",
                "applied": applied_date, "days": days,
                "query": rd.target_query or "-",
                "gb": rd.grow_before, "ga": rd.grow_after,
                "imp_before": imp_before, "imp_after": imp_after,
                "clicks_before": clicks_before, "clicks_after": clicks_after,
                "new_queries": new_queries[:3], "new_count": len(new_queries),
                "keep_damaged": rd.keep_damaged,
            }
            # grow の動き
            if rd.grow_before is not None and rd.grow_after is not None:
                row["delta"] = round(rd.grow_before - rd.grow_after, 1)  # 正=改善
            elif rd.grow_before is None and rd.grow_after is not None:
                row["delta"] = None
                row["new_exposure"] = True  # 未表示→表示到達
            else:
                row["delta"] = None

            if rd.eval_status in SETTLED:
                fg, bg, label = _EVAL_STYLE[rd.eval_status]
                row.update({"eval": rd.eval_status, "eval_label": label,
                            "eval_fg": fg, "eval_bg": bg,
                            "lesson_url": change_url,
                            "lesson_state": ("none" if not rd.lesson_recorded_at
                                             else "todo" if "未記入" in (rd.lesson or "")
                                             else "done"),
                            "keep_notes": [k for k in (rd.keep_detail or [])
                                           if isinstance(k, dict) and k.get("note")][:2]})
                judged.append(row)
                if row["delta"] is not None:
                    deltas.append(row["delta"])
                sum_imp_before += imp_before or 0
                sum_imp_after += imp_after or 0
                sum_clicks_before += clicks_before or 0
                sum_clicks_after += clicks_after or 0
                sum_new_queries += len(new_queries)
                if rd.keep_damaged or rd.eval_status in ("declined", "flat"):
                    level = (("keep毀損(最優先)", "#c0392b") if rd.keep_damaged
                             else ("悪化(高)", "#c0392b") if rd.eval_status == "declined"
                             else ("横ばい(中)", "#9a5b00"))
                    alerts.append({"slug": slug, "url": change_url, "eval": label,
                                   "keep_damaged": rd.keep_damaged,
                                   "level": level[0], "color": level[1]})
            elif triage is None:
                waiting.append(row)
            elif days is not None and days >= eval_days:
                # 期限は過ぎたが判定材料なし（復活/新規記事の表示立ち上がり待ち）
                stalled.append(row)
            else:
                ready = applied_date + timedelta(days=eval_days)
                row.update({"ready": ready, "left": max((ready - today).days, 0)})
                observing.append(row)

        alerts.sort(key=lambda x: (not x["keep_damaged"], x["level"]))
        judged.sort(key=lambda r: (_RANK[r["eval"]],
                                   -(r["delta"] if r["delta"] is not None else 999)))
        observing.sort(key=lambda r: r["ready"])

        wins = sum(1 for r in judged if r["eval"] in ("reached_p1", "improved"))
        extra_context = extra_context or {}
        extra_context["eval_summary"] = {
            "alerts": alerts, "alert_count": len(alerts),
            "judged": judged, "judged_count": len(judged),
            "wins": wins,
            "win_rate": round(100.0 * wins / len(judged)) if judged else None,
            "avg_delta": round(sum(deltas) / len(deltas), 1) if deltas else None,
            "best_delta": max(deltas) if deltas else None,
            "sum_imp_before": sum_imp_before, "sum_imp_after": sum_imp_after,
            "sum_clicks_before": sum_clicks_before, "sum_clicks_after": sum_clicks_after,
            "sum_new_queries": sum_new_queries,
            "observing": observing, "observing_count": len(observing),
            "stalled": stalled, "stalled_count": len(stalled),
            "waiting": waiting, "waiting_count": len(waiting),
            "eval_days": eval_days,
        }
        return super().changelist_view(request, extra_context=extra_context)


# ─────────────────────────────────────────────────────────────
# 学習ループ（パートD）: 戦術別成績と学びの可視化
# ─────────────────────────────────────────────────────────────
from apps.analytics.models import RewriteTactic


@admin.register(RewriteTactic)
class RewriteTacticAdmin(admin.ModelAdmin):
    """リライト戦術の成績（learn_rewrites が判定確定ドラフトから再計算）。
    数値は自動集計のため読み取り専用。note のみ人間/Claude Code が追記できる。"""
    list_display = ("label", "win_badge", "n_reached_p1", "n_improved",
                    "n_flat", "n_declined", "keep_dmg", "updated_at")
    readonly_fields = ("slug", "label", "description", "n_reached_p1", "n_improved",
                       "n_flat", "n_declined", "n_keep_damaged", "samples", "updated_at")
    fields = ("slug", "label", "description", "n_reached_p1", "n_improved",
              "n_flat", "n_declined", "n_keep_damaged", "samples", "note", "updated_at")
    ordering = ("-n_reached_p1", "-n_improved")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="勝率")
    def win_badge(self, obj):
        wr = obj.win_rate
        if wr is None:
            return "—"
        color = "#1e7a40" if wr >= 60 else ("#9a5b00" if wr >= 40 else "#c0392b")
        return format_html('<b style="color:{}">{}%</b> <span style="color:#888">(n={})</span>',
                           color, wr, obj.n_total)

    @admin.display(description="keep毀損")
    def keep_dmg(self, obj):
        if obj.n_keep_damaged:
            return format_html('<span style="color:#c0392b;font-weight:700">⚠ {}回</span>',
                               obj.n_keep_damaged)
        return "-"


from apps.analytics.models import RevenueEntry


@admin.register(RevenueEntry)
class RevenueEntryAdmin(admin.ModelAdmin):
    """月次収益の入力ビュー。楽天/Amazon等の管理画面の確定額を月ごとに入力する。
    編集長AIが週次で目標(2026年12月に月10万円)との差分を検証する。"""
    list_display = ("year_month", "source", "amount_fmt", "is_confirmed", "memo", "updated_at")
    list_filter = ("source", "is_confirmed")
    ordering = ("-year_month", "source")
    list_editable = ("is_confirmed",)

    @admin.display(description="金額", ordering="amount")
    def amount_fmt(self, obj):
        return f"¥{obj.amount:,}"


from apps.analytics.models import EditorNote


@admin.register(EditorNote)
class EditorNoteAdmin(admin.ModelAdmin):
    """人が記事に付けた修正指示の台帳（起票は承認センターのレビューページ）。

    担当AIは manage.py editor_notes で読み書きするが、人がここで
    状態や学びを直接直せるようにしておく。
    """
    list_display = ("created_at", "status", "kind", "slug_link", "category",
                    "assignee", "comment_short", "resolution_short")
    list_filter = ("status", "kind", "category", "assignee")
    search_fields = ("slug", "target_title", "comment", "resolution", "lesson")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "sent_back_at")
    fieldsets = (
        ("指摘（人が記入）", {
            "fields": ("kind", "target_id", "slug", "target_title",
                       "quote", "comment", "category", "assignee")}),
        ("対応（担当AIが記入）", {
            "fields": ("status", "resolution", "lesson",
                       "sent_back_at", "resolved_at", "created_at")}),
    )

    @admin.display(description="対象")
    def slug_link(self, obj):
        return format_html('<a href="{}" target="_blank">/{}/</a>',
                           obj.review_url, obj.slug)

    @admin.display(description="修正指示")
    def comment_short(self, obj):
        return (obj.comment or "")[:60]

    @admin.display(description="対応内容")
    def resolution_short(self, obj):
        return (obj.resolution or "")[:40]


from apps.analytics.models import ArticleWorkLog


@admin.register(ArticleWorkLog)
class ArticleWorkLogAdmin(admin.ModelAdmin):
    """記事1本ごとの作業履歴（誰が何をしたか）。レビューページの「作業履歴」の実体。"""
    list_display = ("created_at", "slug", "agent", "action", "summary")
    list_filter = ("agent", "action", "kind")
    search_fields = ("slug", "summary", "detail")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


from apps.analytics.models import DeskDecision  # noqa: E402


@admin.register(DeskDecision)
class DeskDecisionAdmin(admin.ModelAdmin):
    """編集長からの判断待ち。回答は承認センター(/admin/approvals/#decisions)で行う。
    ここは履歴の確認と、状態の手直し用。"""
    list_display = ("id", "status", "category", "title", "times_raised",
                    "choice_label", "answered_at", "handled_at")
    list_filter = ("status", "category")
    search_fields = ("title", "key", "background", "answer_comment", "handled_note")
    ordering = ("-last_raised_at",)
    readonly_fields = ("created_at", "first_raised_at", "last_raised_at", "answered_at",
                       "action_result", "handled_at")


from apps.analytics.models import OutboundClick  # noqa: E402


@admin.register(OutboundClick)
class OutboundClickAdmin(admin.ModelAdmin):
    """購入リンクのクリック記録。集計は `manage.py outbound_clicks` で見る。"""
    list_display = ("created_at", "network", "page", "product_slug", "link_text",
                    "section", "device", "is_bot", "is_staff")
    list_filter = ("network", "device", "is_bot", "is_staff", "created_at")
    search_fields = ("page", "product_slug", "link_text", "section", "href")
    date_hierarchy = "created_at"
    list_per_page = 100

    def has_add_permission(self, request):
        return False
