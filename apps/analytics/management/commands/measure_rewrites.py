"""リライト効果測定（パートC-1）。

applied な RewriteDraft を対象に、反映前順位(src_best_position / query_portfolio)と
反映後の最新 run(applied_at より後に fetch された ArticleTriage)の順位を比較する。

★ observation_status とは別時計（applied_at 起点で days_since_applied を数える）。
★ LLM API は呼ばない（決定論的な数値比較のみ）。
★ 観察期間中(REWRITE_EVAL_DAYS 未満) や 反映後 run 未取得なら pending_eval に留め、
  improved/flat/declined の分類・keep毀損判定はしない（早すぎる判定を避ける）。

順位は小さいほど良い。閾値は settings（REWRITE_*）。

grow クエリが「反映後 run に出てこない」場合の扱い:
  - 反映後 run 自体が無い(まだ triage 未実行) → pending_eval（await_triage）。悪化にはしない。
  - 反映後 run はあるが grow クエリが queries に無い → 圏外化とみなし declined。
    ただし低表示クエリは週次ノイズで消えることもあるため keep_detail/note に警告を残す。
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import RewriteDraft, ArticleTriage


def _norm_q(s):
    """クエリ文字列の空白正規化（全角→半角・連続空白は1つ・前後trim）。

    GSC は半角スペース区切りで返すため、全角スペースで登録された
    target_query が exact 一致に失敗し「圏外化→declined」と誤判定される
    （2026-07-26 復活記事6件で実発生）。照合は常にこの正規化を通す。
    """
    return " ".join((s or "").replace("　", " ").split())


def _q_position(queries, query):
    """run の queries(JSON list) から指定クエリの position を返す。無ければ None。"""
    target = _norm_q(query)
    for q in (queries or []):
        if isinstance(q, dict) and _norm_q(q.get("query")) == target:
            return q.get("position")
    return None


def _latest_post_apply_triage(article, applied_at):
    """applied_at より後に fetch された最新の ArticleTriage を返す。無ければ None。"""
    return (ArticleTriage.objects
            .filter(article=article, run__fetched_at__gt=applied_at)
            .select_related("run")
            .order_by("-run__fetched_at")
            .first())


def _keep_detail(triage, target_keep, keep_min):
    """keep クエリの反映前後を突き合わせ、(detail, damaged) を返す。

    damaged は判定期間に入った Draft でのみ意味を持つ。観測モード（21日未経過）では
    呼び出し側が damaged を捨て、detail だけを保存する（早すぎるアラートを避ける）。
    """
    detail, damaged = [], False
    for k in (target_keep or []):
        if not isinstance(k, dict):
            continue
        kq, kb = k.get("query"), k.get("position")
        if kb is None:
            continue
        ka = _q_position(triage.queries, kq)
        if ka is None:
            detail.append({"query": kq, "before": kb, "after": None, "delta": None,
                           "note": "圏外化(低表示のノイズの可能性)"})
            damaged = True
            continue
        delta = ka - kb  # 正なら順位悪化
        entry = {"query": kq, "before": kb, "after": ka, "delta": round(delta, 2)}
        if delta >= keep_min:
            entry["note"] = "毀損"
            damaged = True
        detail.append(entry)
    return detail, damaged


class Command(BaseCommand):
    help = "applied な RewriteDraft の効果測定（順位軸・keep毀損チェック込み）"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, default=None,
                            help="特定の RewriteDraft id のみ測定（省略時は applied 全件）")
        parser.add_argument("--dry-run", action="store_true",
                            help="DBを更新せず結果だけ表示")
        parser.add_argument("--observe", action="store_true",
                            help="観察期間中(REWRITE_EVAL_DAYS未満)でも現在順位を記録する。"
                                 "eval_status は pending_eval のままで keep毀損アラートも立てない")

    def handle(self, *args, **opts):
        EVAL_DAYS = settings.REWRITE_EVAL_DAYS
        IMPROVE_MIN = settings.REWRITE_IMPROVE_MIN
        P1_MAX = settings.REWRITE_REACHED_P1_MAX
        KEEP_MIN = settings.REWRITE_KEEP_DAMAGE_MIN

        qs = RewriteDraft.objects.filter(status="applied").select_related("article", "source_triage")
        if opts["draft"]:
            qs = qs.filter(id=opts["draft"])
        qs = qs.order_by("id")

        now = timezone.now()
        counts = {}
        pending_reasons = {}
        rows = []

        for rd in qs:
            a = rd.article
            grow_before = rd.src_best_position
            grow_q = rd.target_query or (
                (rd.target_grow or [{}])[0].get("query") if rd.target_grow else "")
            days = (now - rd.applied_at).days if rd.applied_at else None

            triage = _latest_post_apply_triage(a, rd.applied_at) if rd.applied_at else None

            # 既定値（この測定でのスナップショット）
            eval_status = "pending_eval"
            grow_after = None
            keep_damaged = False
            keep_detail = []
            reason = ""

            if triage is None:
                # 反映後 run がまだ無い → 判定不能（悪化にしない）
                reason = "await_triage(反映後runなし)"
            elif days is not None and days < EVAL_DAYS:
                # 観察期間中 → 判定保留（アラートも出さない）
                reason = f"observation({EVAL_DAYS}日未経過)"
                if opts["observe"]:
                    # 判定はせず、現在の順位だけスナップショットする。
                    # keep_damaged は立てない（3日おきの観測では週次ノイズと区別できない）。
                    grow_after = _q_position(triage.queries, grow_q)
                    keep_detail, _ = _keep_detail(triage, rd.target_keep, KEEP_MIN)
                    reason = f"observation({EVAL_DAYS}日未経過・観測値のみ／判定なし)"
            else:
                # ── 判定可能：grow分類 + keep毀損チェック ──
                grow_after = _q_position(triage.queries, grow_q)

                # keep 毀損チェック（grow の結果と独立に必ず行う）
                keep_detail, keep_damaged = _keep_detail(triage, rd.target_keep, KEEP_MIN)

                # grow 分類
                if grow_after is None and grow_before is None:
                    # 反映前後とも表示実績なし（復活/新規記事の立ち上がり待ち）。
                    # 悪化のしようがないので declined にしない。
                    eval_status = "pending_eval"
                    reason = "表示実績なし(前後ともGSCにクエリなし・立ち上がり待ち)"
                elif grow_after is None:
                    eval_status = "declined"
                    reason = "grow圏外化(反映後runにクエリなし・低表示ノイズの可能性あり要確認)"
                elif grow_before is None:
                    # 反映前は未表示（圏外）→ 表示到達。復活記事はここに入る。
                    eval_status = "reached_p1" if grow_after <= P1_MAX else "improved"
                    reason = "新規表示(反映前は未表示→表示到達)"
                else:
                    improve = grow_before - grow_after  # 正なら改善
                    if improve > IMPROVE_MIN:
                        eval_status = "reached_p1" if grow_after <= P1_MAX else "improved"
                    elif abs(improve) <= IMPROVE_MIN:
                        eval_status = "flat"
                    else:
                        eval_status = "declined"

            # 書き込み
            if not opts["dry_run"]:
                rd.eval_status = eval_status
                rd.days_since_applied = days
                rd.grow_before = grow_before
                rd.grow_after = grow_after
                rd.keep_damaged = keep_damaged
                rd.keep_detail = keep_detail
                rd.measured_at = now
                rd.save(update_fields=["eval_status", "days_since_applied", "grow_before",
                                       "grow_after", "keep_damaged", "keep_detail", "measured_at"])

            counts[eval_status] = counts.get(eval_status, 0) + 1
            if eval_status == "pending_eval":
                pending_reasons[reason] = pending_reasons.get(reason, 0) + 1
            rows.append((rd, eval_status, grow_before, grow_after, days, keep_damaged, reason))

        # ── レポート出力 ──
        w = self.stdout.write
        w(self.style.SUCCESS(f"measure_rewrites 完了: {len(rows)}件 (EVAL_DAYS={EVAL_DAYS})"))
        w(f"内訳: {counts}")
        if pending_reasons:
            w(f"pending内訳: {pending_reasons}")
        w("-" * 78)
        for rd, st, gb, ga, days, kd, reason in rows:
            eta = ""
            if st == "pending_eval" and rd.applied_at:
                from datetime import timedelta
                ready = rd.applied_at + timedelta(days=EVAL_DAYS)
                left = (ready.date() - now.date()).days
                eta = f" 最短判定可能日={ready.date()}({'あと'+str(left)+'日' if left>0 else '判定可'})"
            ga_s = ga if ga is not None else "-"
            w(f"#{rd.id} {rd.article.slug:24s} {st:12s} grow {gb}→{ga_s} "
              f"days={days} keep毀損={'⚠' if kd else '-'}{eta}")
            if reason:
                w(f"      reason: {reason}")
            if kd:
                w(f"      keep_detail: {rd.keep_detail}")
