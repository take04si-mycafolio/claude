"""リライト学習ループの共有語彙とダイジェスト生成（LLM不使用）。

役割:
- TACTICS: リライトで「何を変えたか」を記録する戦術スラッグの正本。
  Claude Code は反映時に RewriteDraft.applied_tactics へこのキーで記録する。
- extract_tactics(): applied_tactics が空の旧ドラフト向けに、diff_summary /
  instructions のテキストから戦術を決定論抽出するフォールバック。
- build_learning_digest(): RewriteTactic の成績と直近の lesson を、
  make_rewrite_instructions が指示書へ差し込めるテキストにまとめる。
"""

# slug: (label, 抽出キーワード)
TACTICS = {
    "title_query_match": ("タイトルへのクエリ語挿入・一致",
                          ["タイトルにクエリ", "タイトルへ", "タイトル変更", "タイトルを変更", "新タイトル"]),
    "intent_realign":    ("検索意図に合わせた切り口の再構築",
                          ["意図ズレ", "検索意図", "切り口"]),
    "intro_direct_answer": ("導入でクエリに即答",
                            ["導入の即答", "導入で即答", "導入文", "リード文", "冒頭で答え"]),
    "structure_rebuild": ("見出し構成の全面再設計",
                          ["見出し構成", "H2/H3", "構成を再", "全面リライト", "再構築"]),
    "compare_table":     ("比較表・先に結論表の導入",
                          ["比較表", "先に結論", "compare-table", "スペック表"]),
    "primary_info":      ("一次情報の追加（公式仕様突合・測定根拠）",
                          ["公式仕様", "一次情報", "JIS", "公表値", "メーカー公式", "突合"]),
    "product_swap":      ("掲載商品の入替（販売終了排除・現行機化）",
                          ["商品を入替", "商品入替", "差し替え", "販売終了", "現行機"]),
    "faq_expand":        ("FAQの追加・拡充",
                          ["FAQ", "よくある質問"]),
    "notes_footer":      ("注釈の記事末尾集約",
                          ["注釈", "記事末尾", "#notes", "折りたたみ"]),
    "compliance_fix":    ("薬機法/景表法の表現適正化",
                          ["薬機法", "景表法", "効能", "断定を回避", "最強級"]),
    "commercial_restraint": ("商業リンクの整理",
                             ["商業リンク", "楽天リンクを整理", "リンクを削減"]),
    "meta_rewrite":      ("メタディスクリプション改善",
                          ["メタディスクリプション", "meta", "抜粋"]),
    "internal_links":    ("内部リンクの配線（card/related）",
                          ["内部リンク", "[card", "[related", "相互リンク"]),
    "gap_integration":   ("競合ギャップ要素の統合",
                          ["gap", "ギャップ", "競合に", "競合が"]),
    "review_pain_mining": ("口コミの不安・不満の傾向を材料化（STEP2型）",
                           ["口コミ傾向", "不満の傾向", "購入前の不安", "STEP2", "レビュー傾向"]),
}

# 効果測定の判定 → 集計カウンタのフィールド名
OUTCOME_FIELD = {
    "reached_p1": "n_reached_p1",
    "improved": "n_improved",
    "flat": "n_flat",
    "declined": "n_declined",
}
SETTLED = tuple(OUTCOME_FIELD.keys())


def extract_tactics(text):
    """diff_summary / instructions から戦術スラッグを決定論抽出（フォールバック用）。"""
    text = text or ""
    found = []
    for slug, (_label, keywords) in TACTICS.items():
        if any(k in text for k in keywords):
            found.append(slug)
    return found


def build_lesson_skeleton(draft):
    """判定確定ドラフトの「学び」の決定論スケルトン。数値事実のみ。
    ここに Claude Code / 人間が admin で分析を追記する。"""
    delta = None
    if draft.grow_before is not None and draft.grow_after is not None:
        delta = round(draft.grow_before - draft.grow_after, 1)  # 正=改善
    labels = [TACTICS[s][0] for s in (draft.applied_tactics or []) if s in TACTICS]
    lines = [
        f"【判定】{draft.get_eval_status_display()}"
        + (f"（keep毀損あり）" if draft.keep_damaged else ""),
        f"【grow】「{draft.target_query}」 {draft.grow_before} → {draft.grow_after}位"
        + (f"（{'+' if delta and delta > 0 else ''}{delta}）" if delta is not None else ""),
        f"【経過】反映から{draft.days_since_applied}日で判定",
        f"【適用戦術】{('、'.join(labels)) if labels else '（記録なし）'}",
    ]
    if draft.keep_damaged and draft.keep_detail:
        worst = [k.get("query") for k in draft.keep_detail[:3] if isinstance(k, dict)]
        lines.append(f"【keep毀損】{('、'.join(filter(None, worst)))}")
    lines.append("【分析】（未記入：この判定の要因分析をここに追記する）")
    return "\n".join(lines)


def build_learning_digest(max_lessons=5):
    """指示書に差し込む「これまでの学習（実測）」ブロックを生成。

    データが無ければ空文字（指示書には何も足さない）。
    """
    from .models import RewriteDraft, RewriteTactic

    tactics = [t for t in RewriteTactic.objects.all() if t.n_total > 0]
    lessons = (RewriteDraft.objects
               .filter(lesson_recorded_at__isnull=False)
               .exclude(lesson="")
               .select_related("article")
               .order_by("-lesson_recorded_at")[:max_lessons])
    if not tactics and not lessons:
        return build_editor_note_digest()

    lines = ["★★ これまでの学習（実測・自サイトのリライト結果に基づく）★★"]
    if tactics:
        ranked = sorted(tactics, key=lambda t: (-(t.win_rate or 0), -t.n_total))
        lines.append("■ 戦術別の成績（勝率＝1ページ目到達+改善の割合）:")
        for t in ranked:
            warn = f" ⚠keep毀損{t.n_keep_damaged}回" if t.n_keep_damaged else ""
            lines.append(
                f"  - {t.label}: 勝率{t.win_rate}%（P1到達{t.n_reached_p1}/改善{t.n_improved}"
                f"/横ばい{t.n_flat}/悪化{t.n_declined}・n={t.n_total}）{warn}")
        worst = [t for t in ranked if (t.win_rate or 0) < 50 and t.n_total >= 3]
        if worst:
            lines.append("  ※勝率50%未満(n≥3)の戦術は、単独では効かない前提で扱うこと: "
                         + "、".join(t.label for t in worst))
    if lessons:
        lines.append("■ 直近の判定と学び:")
        for d in lessons:
            first = (d.lesson or "").splitlines()[0]
            analysis = ""
            for ln in (d.lesson or "").splitlines():
                if ln.startswith("【分析】") and "未記入" not in ln:
                    analysis = " ／ " + ln
                    break
            lines.append(f"  - /{d.article.slug}/ {first}{analysis}")
    lines.append("→ 上の実測を踏まえ、勝率の高い戦術を優先し、悪化・keep毀損と"
                 "同時に現れた戦術は適用前にリスクを明記すること。")
    lines.append("─────────────────────────────")
    # 人（運営）からの修正指示の傾向も同じブロックで供給する（2026-09-08）
    return "\n".join(lines) + "\n" + build_editor_note_digest()



def build_editor_note_digest(max_recent=8):
    """人（運営）からの修正指示の傾向を、指示書へ差し込めるテキストにまとめる。

    レビューページ（承認センター）で書かれた EditorNote を集計する。
    「何を何回指摘されたか」＋「担当が記録した学び」を出すことで、
    同じ指摘を次の記事で繰り返さないようにする（人の指摘の学習還流）。

    記録が無ければ空文字（指示書には何も足さない）。
    """
    from .models import EditorNote

    qs = EditorNote.objects.exclude(status="dismissed")
    total = qs.count()
    if not total:
        return ""
    labels = dict(EditorNote.CATEGORY_CHOICES)
    counts = {}
    for cat in qs.values_list("category", flat=True):
        counts[cat] = counts.get(cat, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])

    lines = ["★★ 人（運営）からの修正指示の傾向 ★★",
             f"（承認前レビューで指摘された累計{total}件。ここに出る型は"
             "「人が読んで引っかかった箇所」＝最優先で避けるべき欠陥）"]
    lines.append("■ 指摘の多い種類:")
    for cat, n in ranked[:6]:
        lines.append(f"  - {labels.get(cat, cat)}: {n}件")

    lessons = (qs.exclude(lesson="").order_by("-resolved_at", "-id")[:max_recent])
    if lessons:
        lines.append("■ 指摘から得た学び（担当AIの記録・これを守って書く）:")
        for n in lessons:
            lines.append(f"  - [{labels.get(n.category, n.category)}] {n.lesson.strip()}")

    recent_open = qs.filter(status="open").order_by("-id")[:max_recent]
    if recent_open:
        lines.append("■ 未対応の指摘（自分の担当ぶんは着手前に必ず対応）:")
        for n in recent_open:
            lines.append(f"  - /{n.slug}/ [{labels.get(n.category, n.category)}] "
                         f"{n.comment.strip().splitlines()[0][:80]}"
                         f"（note#{n.id}）")
    lines.append("→ 上は人が実際に差し戻した指摘。同じ型の指摘を再発させないこと。")
    lines.append("─────────────────────────────")
    return "\n".join(lines) + "\n"


def build_gpt_analysis_prompt(gap):
    """作業台からGPT(ブラウジング可)へコピペする「現状把握」プロンプトを生成する。

    needs_work の意図ズレ分析フロー ③ で使う。回答フォーマットを固定し、
    貼り戻された external_analysis を Claude Code のギャップ分析が材料にできるようにする。
    """
    d = gap.rewrite_draft
    a = d.article
    url = f"https://sc-tsusho.jp/{a.slug}/"
    grow = gap.target_query or d.target_query or ""
    pos = d.src_best_position
    imp = d.src_impressions
    keeps = "、".join(
        f"「{k.get('query')}」({k.get('position')}位)"
        for k in (d.target_keep or []) if isinstance(k, dict) and k.get("query")
    ) or "（なし）"

    return f"""あなたは検索意図分析の専門家です。以下の記事は検索クエリ「{grow}」で約{pos}位に留まっており、検索意図とのズレが疑われます。実際に検索結果と記事の両方を確認して、どこがズレているのかを特定してください。

■ 対象記事: {url}
■ 押し上げたいクエリ(grow): {grow}（現在 約{pos}位・過去28日の表示 {imp}回）
■ 守りたいクエリ(keep): {keeps}

【作業手順】
1. Googleで「{grow}」を検索し、上位10件のタイトルとページ種別（情報解説／比較・ランキング／商品ページ／Q&A など）を確認する
2. 上位ページに共通する検索意図（ユーザーが本当に知りたいこと・求めている形式）を推定する
3. 対象記事を開いて全体を読み、上位ページと比べて何がどうズレているかを特定する

【回答フォーマット】※この見出しのまま埋めてください
◆検索意図の推定: （情報型／比較型／購入型の別と、ユーザーが求めている具体的な答え）
◆上位10件の傾向: （ページ種別の内訳・共通する構成要素・タイトルの傾向）
◆対象記事とのズレ（最重要）: （切り口・構成・答えの出し方のうち、何がどうズレているか。箇条書き）
◆記事に欠けている要素: （上位が扱っていて対象記事に無い本質的な要素のみ。増量のための列挙はしない。箇条書き）
◆keepクエリへの影響注意: （守りたいクエリの観点で、変えるとリスクがある部分があれば）

【注意】
- 文字数や見出しを増やす提案ではなく「ズレの特定」を最優先してください
- 医療・効能効果に関する表現の提案はしないでください（薬機法・景表法の制約があります）
- 記事内の商品リンク・広告リンクを減らす提案は不要です"""
