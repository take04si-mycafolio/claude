"""
last_rewritten_at バックフィル

リライト専用日 last_rewritten_at の初期値を埋める。reversion未導入・LogEntryは
管理画面編集のみで大量リライト（スクリプト経由）を捕捉できないため、方針(B)＝
現状の updated_at を暫定の初期値としてコピーする（「ここ1ヶ月でほぼ全リライト」前提）。

- 既に last_rewritten_at が入っている行は上書きしない（--force で上書き）。
- period_end 後に updated_at が動いた行（機械的更新の混入が疑われる）も、ユーザー決定により
  そのまま updated_at を seed する（observing=削除されない安全側。将来の本物のリライトで自然に正確化）。

使い方:
    python manage.py backfill_last_rewritten --dry-run     # 件数のみ表示
    python manage.py backfill_last_rewritten               # 実行（null の行だけ seed）
    python manage.py backfill_last_rewritten --force        # 既存値も updated_at で上書き
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import F

from apps.products.models import Article, Product


class Command(BaseCommand):
    help = "last_rewritten_at を updated_at から初期化する（方針B）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="件数のみ表示し更新しない")
        parser.add_argument("--force", action="store_true",
                            help="既に値がある行も updated_at で上書きする")

    def handle(self, *args, **opts) -> None:
        dry = opts["dry_run"]
        force = opts["force"]
        self.stdout.write(self.style.SUCCESS("=== last_rewritten_at バックフィル（方針B: updated_at をseed）==="))

        total_seeded = 0
        for model, label in ((Article, "記事"), (Product, "商品")):
            base = model.objects.all()
            target = base if force else base.filter(last_rewritten_at__isnull=True)
            n_all = base.count()
            n_target = target.count()
            n_already = n_all - base.filter(last_rewritten_at__isnull=True).count()
            self.stdout.write(
                f"\n[{label}] 全{n_all}件 / 対象{n_target}件 "
                f"（既に値あり {n_already}件{'・--forceで上書き' if force else 'はスキップ'}）")
            if dry:
                # 例示: 対象のうち先頭数件
                for o in target.only("slug" if hasattr(model, "slug") else "id",
                                     "updated_at")[:3]:
                    ident = getattr(o, "slug", o.pk)
                    self.stdout.write(f"   例: {ident} ← updated_at={o.updated_at}")
                continue
            # updated_at の値をそのまま last_rewritten_at にコピー（DB側でF式）
            updated = target.update(last_rewritten_at=F("updated_at"))
            total_seeded += updated
            self.stdout.write(self.style.SUCCESS(f"   → {updated}件を seed しました"))

        if dry:
            self.stdout.write(self.style.WARNING("\n(dry-run) 実際の更新は行っていません。"))
        else:
            # 仕上げの内訳
            a_null = Article.objects.filter(last_rewritten_at__isnull=True).count()
            p_null = Product.objects.filter(last_rewritten_at__isnull=True).count()
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ 完了: 計{total_seeded}件 seed。"
                f" 残nullの記事 {a_null}件 / 商品 {p_null}件"))
