"""
Claude Code の競合ギャップ差分分析を ContentGap に投入する。

役割分担:
  - 競合URLを貼る = 人（どの競合と戦うか）
  - 競合本文の取得・自記事との差分分析 = Claude Code（網羅的・構造的）★アプリはLLMを呼ばない
  - 差分の採否 = 人（増量の歯止め・事業判断。初期すべて reflect=False）

Claude Code が分析した差分項目(JSON)を渡すと gap_decisions に格納し status=analyzed にする。
各項目: {"item": 説明, "category": 種別, "primary_info": bool, "keep_risk": bool}
  → 保存時に "reflect": False を付与（人がオプトインで選ぶ）。

    python manage.py set_gap_analysis --draft 134 --items-file /tmp/items.json \
        --summary "競合3本と比較した差分分析メモ"
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.analytics.models import ContentGap


class Command(BaseCommand):
    help = "Claude Code の差分分析(フラグ付き項目)を ContentGap.gap_decisions に投入する"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, required=True, help="RewriteDraft id")
        parser.add_argument("--items-file", type=str, required=True,
                            help="[{item,category,primary_info,keep_risk}, ...] のJSONファイル")
        parser.add_argument("--summary", type=str, default=None,
                            help="gap_findings に入れる分析メモ（任意）")
        parser.add_argument("--append", action="store_true",
                            help="既存 gap_decisions に追記（既定は置換）")

    def handle(self, *args, **opts):
        try:
            gap = ContentGap.objects.get(rewrite_draft_id=opts["draft"])
        except ContentGap.DoesNotExist:
            raise CommandError(
                f"draft #{opts['draft']} に ContentGap がありません（needs_work専用）")
        try:
            raw = json.load(open(opts["items_file"], encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"items-file の読み込みに失敗: {e}")
        if not isinstance(raw, list):
            raise CommandError("items-file は項目の配列(JSON list)である必要があります")

        new_items = []
        for it in raw:
            if not isinstance(it, dict) or not it.get("item"):
                continue
            new_items.append({
                "item": str(it["item"]).strip(),
                "category": str(it.get("category", "")).strip(),
                "primary_info": bool(it.get("primary_info", False)),
                "keep_risk": bool(it.get("keep_risk", False)),
                "reflect": False,   # ★初期すべて未反映（人がオプトインで選ぶ）
            })
        if not new_items:
            raise CommandError("有効な項目がありません（各項目に 'item' が必要）")

        if opts["append"]:
            existing = gap.gap_decisions or []
            seen = {d.get("item") for d in existing}
            gap.gap_decisions = existing + [d for d in new_items if d["item"] not in seen]
        else:
            gap.gap_decisions = new_items
        if opts["summary"] is not None:
            gap.gap_findings = opts["summary"]
        if gap.status in ("pending", "urls_set"):
            gap.status = "analyzed"
        gap.save(update_fields=["gap_decisions", "gap_findings", "status", "updated_at"])

        n_prim = sum(1 for d in new_items if d["primary_info"])
        n_risk = sum(1 for d in new_items if d["keep_risk"])
        self.stdout.write(self.style.SUCCESS(
            f"✅ draft #{opts['draft']}: 差分{len(new_items)}項目を投入（全て未反映）。"
            f"一次情報要={n_prim} / keep毀損リスク={n_risk}"))
        self.stdout.write(
            f"レビュー: https://sc-tsusho.jp/admin/analytics/rewritedraft/{opts['draft']}/change/"
            "\n→ 人が各項目の『反映する/しない』を選び、『gap反映を指示書へ追記』で確定。")
