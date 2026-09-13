# -*- coding: utf-8 -*-
"""brands.py の BRANDS 定義を Brand テーブルへ初期投入する。"""
from django.db import migrations


def seed(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    from apps.products.brands import BRANDS

    for i, b in enumerate(BRANDS):
        Brand.objects.update_or_create(
            slug=b["slug"],
            defaults={
                "name": b["name"],
                "aka": b.get("aka", ""),
                "match_brands": "\n".join(b.get("match", [])),
                "exclude_name_keywords": "\n".join(b.get("exclude_name", [])),
                # tier を表示順に反映(1→10,20,30…の順、同tier内は定義順)
                "sort_order": b.get("tier", 3) * 100 + i,
                "is_published": True,
            },
        )


def unseed(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    from apps.products.brands import BRANDS
    Brand.objects.filter(slug__in=[b["slug"] for b in BRANDS]).delete()


class Migration(migrations.Migration):
    dependencies = [("products", "0024_brand")]
    operations = [migrations.RunPython(seed, unseed)]
