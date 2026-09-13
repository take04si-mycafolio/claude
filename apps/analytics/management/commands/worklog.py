"""記事1本ごとの作業履歴を残す／読む（AI社員が各工程の完了時に使う）。

承認センターに上がるまでに誰がどの工程を通したかを記録する。記録が無い工程は
「やっていない」と読まれる（検品が空振りしていたのに気づけなかった事故の再発防止）。
やっていない作業を記録することは絶対にしない。

記録:
  manage.py worklog --kind product_v2 --target 634 --slug tescom-japan-10000133 \
      --agent qa --action qa_fixed \
      --summary "meta_descriptionを138字に磨き込み・6ゲート全0" \
      --detail "タイトルは狙い語が前方で問題なし。価格は楽天DBと一致を確認"

確認:
  manage.py worklog --show --kind product_v2 --target 634
  manage.py worklog --show --slug tescom-japan-10000133
"""
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.models import ArticleWorkLog


class Command(BaseCommand):
    help = "記事の作業履歴を記録／確認する"

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=[k for k, _ in ArticleWorkLog.KIND_CHOICES])
        parser.add_argument("--target", type=int)
        parser.add_argument("--slug", default="")
        parser.add_argument("--agent", choices=[k for k, _ in ArticleWorkLog.AGENT_CHOICES])
        parser.add_argument("--action", choices=[k for k, _ in ArticleWorkLog.ACTION_CHOICES])
        parser.add_argument("--summary", default="")
        parser.add_argument("--detail", default="")
        parser.add_argument("--show", action="store_true", help="履歴を表示する")

    def handle(self, *a, **o):
        if o["show"]:
            qs = ArticleWorkLog.objects.all()
            if o["kind"]:
                qs = qs.filter(kind=o["kind"])
            if o["target"] is not None:
                qs = qs.filter(target_id=o["target"])
            if o["slug"]:
                qs = qs.filter(slug=o["slug"])
            rows = list(qs.order_by("created_at"))
            if not rows:
                self.stdout.write("履歴なし（この記事はまだどの工程も記録されていません）")
                return
            for r in rows:
                self.stdout.write(
                    f"{r.created_at:%m/%d %H:%M} [{r.get_agent_display()}] "
                    f"{r.get_action_display()}: {r.summary}")
                if r.detail:
                    for line in r.detail.splitlines():
                        self.stdout.write(f"        {line}")
            return

        for f in ("kind", "target", "agent", "action"):
            if o.get(f) in (None, ""):
                raise CommandError(f"--{f} は必須です（--show で確認のみもできます）")
        if not o["summary"].strip():
            raise CommandError("--summary に「何をしたか」を1行で書いてください")
        r = ArticleWorkLog.objects.create(
            kind=o["kind"], target_id=o["target"], slug=o["slug"],
            agent=o["agent"], action=o["action"],
            summary=o["summary"].strip()[:300], detail=o["detail"].strip())
        self.stdout.write(self.style.SUCCESS(
            f"✅ 作業履歴を記録しました: {r}"))
