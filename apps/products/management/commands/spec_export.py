# -*- coding: utf-8 -*-
"""仕様収集の元データ(source bundle)をJSONで書き出す。

  python manage.py spec_export --slug bigankiki --out /path/bundles.json

各商品: id / name / brand / official_url / rakuten_caption / features / description抜粋 / 既存specs
サブエージェントはこれを読み、正規スキーマに沿ってスペックを抽出する。
"""
import json, re
from django.core.management.base import BaseCommand
from apps.products.models import Product, Category
from apps.products import spec_schema as S


def strip_html(t):
    return re.sub(r"<[^>]+>", " ", t or "").replace("\xa0", " ")


class Command(BaseCommand):
    help = "仕様収集の元データをJSONで書き出す"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--only-missing", action="store_true",
                            help="コア項目が未充足の商品のみ出力")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        slug = opts["slug"]
        t = Category.objects.get(slug=slug, parent__isnull=True)
        core_keys = [f["key"] for f in S.get_schema(slug) if f.get("core")]
        rows = []
        for p in Product.objects.filter(product_type=t).order_by("sort_order", "id"):
            specs = p.specifications if isinstance(p.specifications, dict) else {}
            if opts["only_missing"]:
                core_filled = sum(1 for k in core_keys if str(specs.get(k, "")).strip())
                if core_filled >= len(core_keys):
                    continue
            cap = ""
            if isinstance(p.api_data, dict):
                rk = p.api_data.get("rakuten") or {}
                if isinstance(rk, dict):
                    cap = strip_html(rk.get("itemCaption", ""))[:1500]
            rows.append({
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "official_url": p.official_url,
                "rakuten_caption": cap,
                "features": strip_html(p.features)[:1500],
                "description_excerpt": strip_html(p.description)[:2500],
                "existing_specs": {k: v for k, v in specs.items() if k != "_internal"},
            })
            if opts["limit"] and len(rows) >= opts["limit"]:
                break
        with open(opts["out"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"{len(rows)}件を書き出し: {opts['out']}"))
