# -*- coding: utf-8 -*-
"""収集したスペック(JSON)を specifications へ取り込む。

  python manage.py spec_ingest --slug bigankiki --in /path/collected.json [--apply]

入力フォーマット: [{"id": 123, "specs": {"weight": "約280g", ...}}, ...]
- スキーマ外キーは警告して無視
- 空値・プレースホルダはスキップ
- 既存 _internal は温存。既存値は新しい非空値で上書き
"""
import json
from django.core.management.base import BaseCommand
from apps.products.models import Product
from apps.products import spec_schema as S


class Command(BaseCommand):
    help = "収集したスペックJSONを specifications へ取り込む"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--in", dest="infile", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        slug = opts["slug"]
        valid = set(S.get_field_keys(slug)) | {"sale_price", "mirror", "award",
                                               "usable_liquid", "nozzle_angle", "cord_length"}
        placeholders = {"", "要確認", "不明", "-", "—", "未確認"}
        with open(opts["infile"], encoding="utf-8") as f:
            data = json.load(f)
        updated = added_fields = 0
        unknown = set()
        for row in data:
            try:
                p = Product.objects.get(id=row["id"])
            except Product.DoesNotExist:
                self.stderr.write(f"id={row.get('id')} 不在")
                continue
            specs = dict(p.specifications) if isinstance(p.specifications, dict) else {}
            changed = False
            for k, v in (row.get("specs") or {}).items():
                if k not in valid:
                    unknown.add(k)
                    continue
                sval = ("" if v is None else str(v)).strip()
                if sval in placeholders:
                    continue
                if str(specs.get(k, "")).strip() != sval:
                    specs[k] = v
                    changed = True
                    added_fields += 1
            if changed:
                updated += 1
                if opts["apply"]:
                    p.specifications = specs
                    p.save(update_fields=["specifications"])
        if unknown:
            self.stderr.write(self.style.WARNING(f"スキーマ外キー(無視): {sorted(unknown)}"))
        msg = f"{updated}商品 / {added_fields}フィールド更新"
        self.stdout.write(self.style.SUCCESS(msg) if opts["apply"]
                          else self.style.WARNING(msg + "  (ドライラン)"))
