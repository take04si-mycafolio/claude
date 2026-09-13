"""
Claude Code が差分分析するための材料を出力する  python manage.py show_content_gap --draft N

bot取得に依存せず、人が管理画面に貼った競合本文(competitor_content)＋自記事＋
target_query/keep/grow を出力する。Claude Code はこれを読んで差分を分析し、
set_gap_analysis で結果(フラグ付き項目)を投入する。★アプリはLLMを呼ばない。

    python manage.py show_content_gap --draft 141            # 材料を表示
    python manage.py show_content_gap --draft 141 --self-content   # 自記事本文も全文
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.html import strip_tags
from apps.analytics.models import ContentGap


class Command(BaseCommand):
    help = "差分分析の材料（貼付競合本文＋自記事＋keep/grow）を出力する"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, required=True)
        parser.add_argument("--self-content", action="store_true", help="自記事本文も全文出力")

    def handle(self, *args, **opts):
        try:
            gap = ContentGap.objects.select_related("rewrite_draft__article").get(
                rewrite_draft_id=opts["draft"])
        except ContentGap.DoesNotExist:
            raise CommandError(f"draft #{opts['draft']} に ContentGap がありません（needs_work専用）")
        rd = gap.rewrite_draft
        a = rd.article
        w = self.stdout.write
        w("=" * 70)
        w(f"RewriteDraft #{rd.id}  /{a.slug}/  差分分析の材料")
        w("=" * 70)
        w(f"\n■ 対象クエリ target_query(grow代表): {gap.target_query}")
        w(f"■ target_grow: {[q.get('query') for q in (rd.target_grow or [])]}")
        w(f"■ target_keep(毀損禁止): {[(q.get('query'), q.get('position')) for q in (rd.target_keep or [])]}")
        so = gap.self_outline or {}
        w(f"\n■ 自記事アウトライン H2({so.get('h2_count')}本)/FAQ={so.get('faq')}:")
        for h in (so.get("h2") or []):
            w(f"    - {h}")
        ext = (gap.external_analysis or "").strip()
        w("\n■ GPT分析結果（現状把握・人が貼付）↓↓↓")
        if ext:
            w(ext)
        else:
            w("    （未貼付：作業台の『GPTに渡すプロンプト』→GPT実行→返答貼り付けでここに載ります）")
        urls = gap.competitor_urls or []
        bodies = gap.competitor_bodies or {}
        w(f"\n■ 競合ページ本文（URLごと・人がコピペ）↓↓↓")
        if not urls:
            w("    （競合URL未設定：先にURLを貼ってください）")
        for i, u in enumerate(urls):
            body = (bodies.get(u) or "").strip()
            w(f"\n--- 競合{i + 1}: {u}（{len(body)}字）---")
            w(body if body else "    （未貼付：管理画面の『競合本文 {}』欄に本文をコピペ）".format(i + 1))
        if opts["self_content"]:
            w(f"\n■ 自記事本文(strip_tags) ↓↓↓\n{strip_tags(a.content or '')}")
        w("\n" + "=" * 70)
        w("→ この材料で差分を分析し、set_gap_analysis --draft "
          f"{rd.id} --items-file <json> で投入（各項目 item/category/primary_info/keep_risk）。")
