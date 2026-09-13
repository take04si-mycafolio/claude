"""
リライト指示書の決定論的生成  python manage.py make_rewrite_instructions

対象バケット（既定 quick_win）の記事について、本文と PlaybookRule を照合し、
**LLMを一切使わず**に「何をどう直すか」の指示書とチェックリストを生成して
RewriteDraft(status=instructed) を作る。実際の本文執筆は Claude Code（アプリ外）が担う。

優先順位: best_query_impressions 降順 ×（1ページ目への近さ＝best_query_position 昇順）。

使い方:
    python manage.py make_rewrite_instructions                 # 最新run・quick_win
    python manage.py make_rewrite_instructions --run=4 --bucket=quick_win
    python manage.py make_rewrite_instructions --force         # 既存の未完Draftがあっても新規作成
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.html import strip_tags

from apps.analytics.learning import build_learning_digest
from apps.analytics.models import TriageRun, PlaybookRule, RewriteDraft, ContentGap


def extract_self_outline(html: str) -> dict:
    """自記事の見出し(H2/H3)・FAQ有無を決定論抽出（LLM不使用）。"""
    html = html or ""

    def texts(tag):
        out = []
        for h in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.S):
            t = re.sub(r"<[^>]+>", "", h).strip()
            if t:
                out.append(t[:100])
        return out
    h2 = texts("h2")
    h3 = texts("h3")
    return {"h2": h2, "h3": h3, "h2_count": len(h2), "h3_count": len(h3),
            "faq": ("よくある質問" in html or "bk-mc-faq" in html)}

RAKUTEN_MAX = 2            # 商業リンクの目安上限（dead平均3.4/live1.2）
INTRO_CHARS = 400          # 「導入でクエリに答えているか」を見る先頭文字数
REWRITE_EVAL_DAYS = 21     # 反映後この日数は効果判定しない（パートCで使用）


def _query_tokens(q: str) -> list[str]:
    return [w for w in (q or "").split() if len(w) >= 2]


class Command(BaseCommand):
    help = "PlaybookRule から決定論的にリライト指示書を生成し RewriteDraft を作る（LLM不使用）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--run", type=int, default=None, help="対象TriageRun id（省略時:最新）")
        parser.add_argument("--bucket", type=str, default="quick_win", help="対象バケット")
        parser.add_argument("--force", action="store_true",
                            help="既存の未完Draft(pending/instructed/in_review)があっても新規作成")

    def handle(self, *args, **opts) -> None:
        run = (TriageRun.objects.get(id=opts["run"]) if opts["run"]
               else TriageRun.objects.order_by("-fetched_at").first())
        if not run:
            raise CommandError("TriageRun がありません。")
        bucket = opts["bucket"]
        rules = list(PlaybookRule.objects.filter(is_active=True).order_by("priority"))

        qs = (run.articles.filter(bucket=bucket, article__isnull=False)
              .select_related("article")
              .order_by("-best_query_impressions", "best_query_position"))
        self.stdout.write(self.style.SUCCESS(
            f"=== make_rewrite_instructions run={run.id} bucket={bucket} 対象{qs.count()}本 ==="))

        made, skipped = 0, 0
        ACTIVE = ["pending", "instructed", "in_review", "drafting", "approved"]
        for t in qs:
            # 1記事1下書き（URL単位）: 別run/旧世代の下書きは掃除して重複表示を防ぐ。
            # ContentGap も CASCADE で消える。現runの下書き(source_triage=t)は残す。
            # ★手動追加(is_manual)の下書きは掃除しない（トリアージ由来でないため保護）。
            RewriteDraft.objects.filter(article=t.article, is_manual=False)\
                .exclude(source_triage=t).delete()
            if not opts["force"] and RewriteDraft.objects.filter(
                    article=t.article, status__in=ACTIVE).exists():
                skipped += 1
                continue
            instr, checklist, refs, portfolio, keep, grow = self._build(t, rules)
            rd = RewriteDraft.objects.create(
                article=t.article, source_triage=t, target_query=t.best_query or "",
                src_best_position=t.best_query_position, src_impressions=t.impressions,
                status="instructed", instructions=instr, checklist=checklist,
                playbook_refs=refs, instructed_at=timezone.now(),
                query_portfolio=portfolio, target_keep=keep, target_grow=grow,
            )
            # needs_work 専用: コンテンツギャップ(上位比較)を空で開始（self_outlineは決定論抽出）
            if t.bucket == "needs_work":
                ContentGap.objects.create(
                    rewrite_draft=rd, target_query=t.best_query or "",
                    self_outline=extract_self_outline(t.article.content),
                    status="pending",
                )
            made += 1
        self.stdout.write(self.style.SUCCESS(f"\n✅ 指示書生成: {made}件 / スキップ(既存){skipped}件"))
        self.stdout.write("管理画面: https://sc-tsusho.jp/admin/analytics/rewritedraft/")

    # ------------------------------------------------------------------
    KEEP_POSITION_MAX = 20     # これ以内で拾っている既存クエリは keep 候補（毀損禁止）
    KEEP_MAX = 8               # keep 提案の上限（表示回数の多い順）

    def _portfolio_keep_grow(self, triage):
        """query_portfolio と keep/grow の初期提案（機械提案・最終確定は人間/Claude Code）。"""
        portfolio = list(triage.queries or [])
        best = triage.best_query or ""
        grow = [q for q in portfolio if q["query"] == best] or (
            [{"query": best, "position": triage.best_query_position,
              "impressions": triage.best_query_impressions, "clicks": 0}] if best else [])
        # keep = 既に上位(<=20位)で拾っている、grow以外のクエリ（表示多い順）
        keep = [q for q in portfolio
                if q["query"] != best and (q["position"] or 999) <= self.KEEP_POSITION_MAX]
        keep = sorted(keep, key=lambda q: -(q.get("impressions") or 0))[:self.KEEP_MAX]
        return portfolio, keep, grow

    def _build(self, triage, rules):
        a = triage.article
        html = a.content or ""
        text = strip_tags(html)
        intro = text[:INTRO_CHARS]
        q = triage.best_query or ""
        toks = _query_tokens(q)
        title = a.title or ""
        portfolio, keep, grow = self._portfolio_keep_grow(triage)

        title_has = bool(toks) and any(w in title for w in toks)
        intro_has = bool(toks) and any(w in intro for w in toks)
        rakuten = len(re.findall(r"hb\.afl\.rakuten", html))
        faq = ("よくある質問" in html or "bk-mc-faq" in html)

        steps, checklist, refs = [], [], []

        def add(rule_key, ok, note):
            r = next((x for x in rules if x.key == rule_key), None)
            if not r:
                return
            refs.append(rule_key)
            checklist.append({"key": rule_key, "label": r.check_item, "ok": ok, "note": note})

        # 0) needs_work は「検索意図のズレ」が本丸＝意図判定を必須項目にする
        if triage.bucket == "needs_work":
            steps.append(
                f"【needs_work 最重要・意図判定】『{q}』の検索意図（情報型／比較型／購入型）を"
                "まず判定し、現記事の切り口がその意図に答えているかを評価せよ。"
                "ズレていれば切り口・見出し構成・結論の出し方を作り直す。"
                "★タイトルにクエリ語を挿入するだけで済ませないこと（意図のズレが本丸）。")
            checklist.append({
                "key": "intent-match-evaluation",
                "label": "検索意図(情報/比較/購入)を判定し、記事の切り口が意図に答えているか",
                "ok": None,
                "note": "needs_work必須：意図を判定→切り口を意図に合わせる。タイトル挿入だけで済ませない。",
            })

        # 1) タイトル/H1 とクエリ一致（最重要）
        if toks and not title_has:
            steps.append(
                f"【最優先】タイトルとH1(記事冒頭のH1相当)に『{q}』の主要語（{'／'.join(toks)}）を"
                f"自然に含める。現タイトル「{title}」にはクエリ語が入っていない。"
                "※プレイブック根拠: タイトルにクエリ語を含む率 live71%/dead8%（最大の差別化要因）。")
            add("title-query-match", False, f"現タイトルにクエリ語なし: {title}")
        elif toks:
            steps.append(f"タイトルは『{q}』の語を既に含む。維持しつつ、より検索意図に沿う表現か点検。")
            add("title-query-match", True, "タイトルにクエリ語あり")

        # 2) 導入でクエリに直接答える（title-query-match ルールの一部＝チェックは重複させない）
        if toks and not intro_has:
            steps.append(
                f"導入（本文冒頭）で『{q}』に直接答えるパラグラフを置く。"
                f"現状、先頭{INTRO_CHARS}字にクエリ語が出てこない＝検索意図への即答が弱い。")

        # 3) 商業リンクの整理（過多はdead相関）
        if rakuten > RAKUTEN_MAX:
            steps.append(
                f"楽天/商業リンクが{rakuten}本と多い。検索意図（多くは情報・比較）に対し過剰。"
                f"本当に必要な{RAKUTEN_MAX}本程度に整理し、解説を主・リンクを従にする。"
                "※プレイブック根拠: 楽天リンク平均 live1.2/dead3.4。")
            add("intent-commerce-restraint", False, f"商業リンク{rakuten}本→{RAKUTEN_MAX}本目安に整理")
        else:
            add("intent-commerce-restraint", True, f"商業リンク{rakuten}本（過剰でない）")

        # 4) FAQ
        if not faq:
            steps.append("検索意図に沿ったFAQ（よくある質問）が無い。ロングテール疑問をFAQで補う。")
            add("faq-coverage", False, "FAQなし→追加")
        else:
            add("faq-coverage", True, "FAQあり")

        # 5) 増量しない（アンチパターンの明示）
        steps.append(
            "【禁止】文字数・見出し・内部リンクを増やす目的の加筆はしない。"
            "現状は十分な分量がある（生死で文字数差は無い）。直すのは"
            "『タイトル/導入のクエリ一致』と『意図適合』であって増量ではない。")
        add("depth-is-not-the-lever", None, "増量目的の加筆をしていないか（人間確認）")

        # 6) 具体性（機械判定不可＝人間/Claude Code判断）
        add("specificity-primary-info", None, "一般論でなく実測・比較・独自の具体情報があるか（人間確認）")

        # 0') 巻き添え毀損の防止（最上位制約）＝keep保護のチェック項目
        checklist.insert(0, {
            "key": "keep-not-damaged",
            "label": "target_keep の既存クエリ（一覧参照）を毀損していないか（特にタイトル変更の影響）",
            "ok": None,
            "note": "URL単位・全クエリ考慮。grow優先の単一クエリ寄せ最適化をしない。両立不可ならkeepの強い方を守る。",
        })
        # 0'') keep/grow の優先度判断（keep-not-damaged の次）
        checklist.insert(1, {
            "key": "keep-grow-priority-judged",
            "label": "keep/grow の優先度を順位に基づき判断したか（強いkeepは防衛優先・大差なら別記事化も可）",
            "ok": None,
            "note": "keep順位が高いほど防衛優先。growがkeepより大幅低順位ならkeepを1ミリも損なわない範囲のみ、別記事化も選択肢。",
        })

        # ── 最上位制約（指示書・Claude Code依頼文の冒頭に必ず置く）──
        # 【keep/grow 優先度判断の具体例】
        #   hair_color = keep「市販ヘアカラー」4位 vs grow「傷まない ランキング」29位
        #     → 順位差25・grow は20位より下。keep 防衛を最優先し、grow は4位を損なわない範囲のみ。
        #        両取りが難しければ grow は別記事化も選択肢（diff_summary に明記）。
        constraint = (
            "★★ 最上位制約（必読）★★\n"
            "① この記事は複数クエリで表示されている（下の query_portfolio 参照）。リライトは "
            "target_grow を伸ばすことが目的だが、target_keep の既存クエリを毀損してはならない。\n"
            "② 【keep/grow 優先度判断（順位に基づく）】\n"
            "  ・keep クエリの順位が高い（数値が小さい）ほど、その防衛を強く優先する。\n"
            "  ・grow が keep より大幅に低順位（順位差が概ね10以上、かつ grow が概ね20位より下）の場合、"
            "grow のために keep を毀損するリスクを取らない。keep を1ミリも損なわない範囲でのみ grow に触れる。"
            "grow は別記事で狙うべきと判断したら、その旨を diff_summary に明記してよい（無理に1記事で両取りしない）。\n"
            "  ・keep と grow が近接（順位差が小さく両者とも中〜下位）なら、統合（両クエリを自然に含む構成）を積極的に狙ってよい。\n"
            "  ・トレードオフが避けられない場合は target_keep の強い方（順位・表示の高い方）を優先して守る。\n"
            "③ 単一クエリへの機械的な寄せ最適化をしない。keep と grow が同義・統合可能かはクエリの意味理解を要する。"
            "決定論チェックに委ねず Claude Code が判断すること。\n"
            "─────────────────────────────\n"
        )

        def _qline(x):
            return (f"    - 「{x['query']}」 {x.get('position')}位 / "
                    f"{x.get('impressions', 0)}表示 / {x.get('clicks', 0)}click")
        pf_lines = "\n".join(_qline(x) for x in portfolio[:20]) or "    （クエリ明細なし）"
        keep_lines = "\n".join(_qline(x) for x in keep) or "    （なし）"
        grow_lines = "\n".join(_qline(x) for x in grow) or "    （なし）"

        # 学習ループ（パートD）: 実測に基づく戦術成績と直近の学びを毎回差し込む。
        # データが無い間は空文字＝従来と同じ指示書になる。
        learning = build_learning_digest()

        header = (
            constraint + learning +
            f"■ 対象記事: {a.title}\n"
            f"■ URL: /{a.slug}/\n"
            f"■ bucket: {triage.bucket} / このURLの獲得クエリ数: {len(portfolio)}\n"
            f"■ query_portfolio（このURLが拾っている全クエリ・順位昇順・上位20）:\n{pf_lines}\n"
            f"■ target_grow（伸ばす・機械提案／要レビュー確定）:\n{grow_lines}\n"
            f"■ target_keep（守る・毀損禁止・機械提案／要レビュー確定）:\n{keep_lines}\n"
            f"■ 方針: 増量しない。keepを守りつつ grow のタイトル/導入のクエリ一致と意図適合を直す。\n"
            f"─────────────────────────────\n"
        )
        body = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        footer = (
            "\n─────────────────────────────\n"
            "この指示書に沿って Claude Code が draft_title / draft_content を執筆し、"
            "管理画面の RewriteDraft に投入（またはコマンド set_rewrite_draft）→ 人間がレビュー→承認反映。"
            "\n★ 反映前に keep クエリを壊していないか必ず自己点検すること。"
            f"\n※反映後 {REWRITE_EVAL_DAYS} 日間は効果判定しない（順位反映ラグのため・パートC）。"
        )
        return header + body + footer, checklist, refs, portfolio, keep, grow
