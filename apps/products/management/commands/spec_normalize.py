# -*- coding: utf-8 -*-
"""既存 specifications を spec_schema の正規化キーへ寄せ、カバレッジを報告する。

  python manage.py spec_normalize --slug bigankiki            # ドライラン(変更なし・集計のみ)
  python manage.py spec_normalize --slug bigankiki --apply    # DBに正規化を保存
"""
from django.core.management.base import BaseCommand
from apps.products.models import Product, Category
from apps.products import spec_schema as S


class Command(BaseCommand):
    help = "specifications を正規化キーへ寄せ、仕様表カバレッジを集計する"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="製品タイプslug (例: bigankiki)")
        parser.add_argument("--apply", action="store_true", help="正規化結果をDBへ保存")

    def handle(self, *args, **opts):
        slug = opts["slug"]
        apply = opts["apply"]
        schema = S.get_schema(slug)
        if not schema:
            self.stderr.write(f"スキーマ未定義: {slug}")
            return
        try:
            t = Category.objects.get(slug=slug, parent__isnull=True)
        except Category.DoesNotExist:
            self.stderr.write(f"製品タイプが見つかりません: {slug}")
            return

        keys = [f["key"] for f in schema]
        prods = Product.objects.filter(product_type=t)
        n = prods.count()
        filled = {k: 0 for k in keys}
        changed = 0

        for p in prods:
            norm, internal = S.normalize_specifications(slug, p.specifications)
            for k in keys:
                if str(norm.get(k, "")).strip():
                    filled[k] += 1
            if apply:
                merged = dict(norm)
                if internal:
                    merged["_internal"] = internal
                if merged != p.specifications:
                    p.specifications = merged
                    p.save(update_fields=["specifications"])
                    changed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n■ {t.name} ({slug})  商品{n}件  仕様表カラム{len(keys)}列"))
        self.stdout.write(f"{'列(正規化キー)':<22}{'ラベル':<18}充足")
        self.stdout.write("-" * 56)
        for f in schema:
            k = f["key"]
            core = "★" if f.get("core") else " "
            self.stdout.write(f"{core}{k:<21}{f['label']:<18}{filled[k]:>3}/{n}")
        avg = sum(filled.values()) / (len(keys) * n) * 100 if n else 0
        self.stdout.write(f"\n平均充足率: {avg:.1f}%")
        if apply:
            self.stdout.write(self.style.SUCCESS(f"正規化を保存: {changed}件更新"))
        else:
            self.stdout.write(self.style.WARNING("ドライラン(未保存)。保存するには --apply"))
