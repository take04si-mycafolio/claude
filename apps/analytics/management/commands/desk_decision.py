"""編集長の「要対応(人)」を、人が承認センターで答えられる判断待ちとして扱う（2026-09-14新設）。

使い方（編集長）:
  # 1論点1件で登録。同じ --key が回答待ちで残っていれば新規作成せず「提起回数」を増やして更新する
  manage.py desk_decision add --key cannibal:datsumouki-cool:datsumouki-itami \
     --category cannibal --title "/datsumouki-cool/ と /datsumouki-itami/ を統合するか分離するか" \
     --background-file /tmp/bg.md --recommend "itami へ統合（冷却は1節に収める）" \
     --option "merge|itami へ統合する（301）|cool を非公開にして itami へ301|rec,dev" \
     --option "split|分離する（ペルソナを分ける）|cool=夏場・肌の火照り…" \
     --slugs datsumouki-cool datsumouki-itami --report 539

  --option は "key|表示名|説明|フラグ" 。フラグは rec(推奨) / dev(実行にコード変更が要る) をカンマ区切り。
  --action "key=set_discontinued:slug1,slug2" で、その選択肢が選ばれた瞬間に生産終了フラグを立てる
  （"key=set_current:slug" は現行扱いに戻す）。

  # 回答済み（編集長が反映すべきもの）を読む
  manage.py desk_decision list --status answered
  # 反映が済んだら閉じる（コード変更が要るものは --dev で開発作業待ちへ）
  manage.py desk_decision resolve --id 3 --note "queue.md 今週のリライト決定に itami 全面を追加"
  manage.py desk_decision resolve --id 3 --dev --note "ARTICLE_MERGES への追記と cool 非公開が必要"
  # 論点自体が消えたとき
  manage.py desk_decision withdraw --id 3 --note "cool が自然にインデックスされたため不要"
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models import DeskDecision, WorkReport

_ACTION_TYPES = {"set_discontinued": True, "set_current": False}


class Command(BaseCommand):
    help = "編集長の判断待ち(DeskDecision)を登録・一覧・完了する"

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="cmd", required=True)

        a = sub.add_parser("add", help="判断待ちを登録（同じkeyが未完なら更新）")
        a.add_argument("--key", required=True)
        a.add_argument("--category", default="other",
                       choices=[c for c, _ in DeskDecision.CATEGORY_CHOICES])
        a.add_argument("--title", required=True)
        a.add_argument("--background", default="")
        a.add_argument("--background-file", default="")
        a.add_argument("--recommend", default="")
        a.add_argument("--option", action="append", default=[],
                       help='"key|表示名|説明|rec,dev"（2件以上）')
        a.add_argument("--action", action="append", default=[],
                       help='"optionkey=set_discontinued:slug1,slug2"')
        a.add_argument("--slugs", nargs="*", default=[])
        a.add_argument("--report", type=int, default=None, help="出典のWorkReport id")

        ls = sub.add_parser("list", help="一覧")
        ls.add_argument("--status", default="open",
                        choices=[s for s, _ in DeskDecision.STATUS_CHOICES] + ["all", "active"])

        r = sub.add_parser("resolve", help="反映済みにする")
        r.add_argument("--id", type=int, required=True)
        r.add_argument("--note", required=True)
        r.add_argument("--dev", action="store_true", help="コード変更が要るので開発作業待ちにする")

        w = sub.add_parser("withdraw", help="論点が不要になったので取り下げる")
        w.add_argument("--id", type=int, required=True)
        w.add_argument("--note", required=True)

    def handle(self, *args, **o):
        getattr(self, "_" + o["cmd"])(o)

    # ------------------------------------------------------------------
    def _add(self, o):
        options = [self._parse_option(s) for s in o["option"]]
        if len(options) < 2:
            raise CommandError("--option は2件以上指定してください（選べない判断は判断待ちにしない）")
        keys = {op["key"] for op in options}
        if len(keys) != len(options):
            raise CommandError("--option の key が重複しています")
        for spec in o["action"]:
            okey, _, act = spec.partition("=")
            atype, _, slugs = act.partition(":")
            if okey not in keys or atype not in _ACTION_TYPES or not slugs:
                raise CommandError(f"--action の形式が不正です: {spec}")
            self._check_products(slugs.split(","))
            next(op for op in options if op["key"] == okey)["action"] = {
                "type": atype, "products": [s.strip() for s in slugs.split(",") if s.strip()]}

        background = o["background"]
        if o["background_file"]:
            background = Path(o["background_file"]).read_text(encoding="utf-8")
        report = WorkReport.objects.filter(id=o["report"]).first() if o["report"] else None

        fields = dict(category=o["category"], title=o["title"][:200], background=background,
                      recommendation=o["recommend"], options=options,
                      slugs=" ".join(o["slugs"])[:500])
        now = timezone.now()
        cur = (DeskDecision.objects.filter(key=o["key"])
               .exclude(status__in=["done", "withdrawn"]).order_by("-id").first())
        if cur and cur.status != "open":
            self.stdout.write(self.style.WARNING(
                f"判断#{cur.id} は既に回答済み（{cur.get_status_display()}・"
                f"選択: {cur.choice_label}）です。登録し直さず、回答を反映してください。"))
            return
        if cur:
            for k, v in fields.items():
                setattr(cur, k, v)
            cur.times_raised += 1
            cur.last_raised_at = now
            if report:
                cur.source_report = report
            cur.save()
            self.stdout.write(self.style.SUCCESS(
                f"判断#{cur.id} を更新（{cur.times_raised}回目の提起・{cur.days_open}日回答待ち）: {cur.title}"))
            return
        d = DeskDecision.objects.create(key=o["key"], source_report=report, **fields)
        self.stdout.write(self.style.SUCCESS(f"判断#{d.id} を登録: {d.title}"))

    def _parse_option(self, s):
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise CommandError(f'--option は "key|表示名|説明|フラグ" の形式です: {s}')
        flags = {f.strip() for f in (parts[3] if len(parts) > 3 else "").split(",") if f.strip()}
        return {"key": parts[0][:40], "label": parts[1][:200],
                "detail": parts[2] if len(parts) > 2 else "",
                "recommended": "rec" in flags, "needs_dev": "dev" in flags}

    def _check_products(self, slugs):
        from apps.products.models import Product
        missing = [s for s in slugs if not Product.objects.filter(slug=s.strip()).exists()]
        if missing:
            raise CommandError(f"商品slugが見つかりません: {', '.join(missing)}")

    def _list(self, o):
        qs = DeskDecision.objects.order_by("id")
        if o["status"] == "active":
            qs = qs.exclude(status__in=["done", "withdrawn"])
        elif o["status"] != "all":
            qs = qs.filter(status=o["status"])
        if not qs.exists():
            self.stdout.write("対象なし")
            return
        for d in qs:
            self.stdout.write(f"\n=== 判断#{d.id} [{d.get_status_display()}] {d.title}")
            self.stdout.write(f"key={d.key} / 種類={d.get_category_display()} / "
                              f"提起{d.times_raised}回・初回から{d.days_open}日 / slugs={d.slugs or '-'}")
            if d.recommendation:
                self.stdout.write(f"推奨案: {d.recommendation}")
            for op in d.options or []:
                mark = "★" if op.get("recommended") else "・"
                extra = []
                if op.get("needs_dev"):
                    extra.append("要コード変更")
                if op.get("action"):
                    extra.append(f"回答時に{op['action']['type']}:{','.join(op['action']['products'])}")
                self.stdout.write(f"  {mark}{op['key']}: {op['label']}"
                                  f"{'（' + '・'.join(extra) + '）' if extra else ''} {op.get('detail', '')}")
            if d.answered_at:
                self.stdout.write(f"▶ 回答({timezone.localtime(d.answered_at):%m/%d %H:%M} {d.answered_by}): "
                                  f"{d.choice_label or '(選択なし)'}")
                if d.answer_comment:
                    self.stdout.write(f"  コメント: {d.answer_comment}")
                if d.action_result:
                    self.stdout.write(f"  実行済み: {d.action_result}")
            if d.handled_note:
                self.stdout.write(f"▶ 反映: {d.handled_note}")

    def _resolve(self, o):
        d = self._get(o["id"])
        if d.status not in ("answered", "dev_pending"):
            raise CommandError(f"判断#{d.id} は {d.get_status_display()} のため閉じられません"
                               "（回答待ちのものを編集長が勝手に閉じない）")
        d.status = "dev_pending" if o["dev"] else "done"
        d.handled_note = (d.handled_note + "\n" if d.handled_note else "") + o["note"]
        d.handled_at = timezone.now()
        d.save(update_fields=["status", "handled_note", "handled_at"])
        self.stdout.write(self.style.SUCCESS(f"判断#{d.id} → {d.get_status_display()}"))

    def _withdraw(self, o):
        d = self._get(o["id"])
        if d.status in ("done", "withdrawn"):
            raise CommandError(f"判断#{d.id} は既に {d.get_status_display()} です")
        d.status = "withdrawn"
        d.handled_note = (d.handled_note + "\n" if d.handled_note else "") + o["note"]
        d.handled_at = timezone.now()
        d.save(update_fields=["status", "handled_note", "handled_at"])
        self.stdout.write(self.style.SUCCESS(f"判断#{d.id} を取り下げました"))

    def _get(self, pk):
        d = DeskDecision.objects.filter(id=pk).first()
        if not d:
            raise CommandError(f"判断#{pk} が見つかりません")
        return d
