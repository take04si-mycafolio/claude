"""製品タイプの初期データ投入と既存データの移行"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.products.models import Category, Product

PRODUCT_TYPES = [
    ("美顔器", "bigankiki", 10, "EMS・RF・LEDなどで肌やフェイスラインをケアする美顔器のレビュー"),
    ("ドライヤー", "dryer", 20, "マイナスイオンや速乾、ヘアケア機能付きドライヤーのレビュー"),
    ("ヘアアイロン", "hair-iron", 30, "ストレート・カール・ヘアアイロンのレビュー"),
    ("脱毛器", "datsumouki", 40, "家庭用脱毛器・光脱毛・レーザー脱毛器のレビュー"),
    ("マッサージ機", "massage", 50, "フェイス・ボディ用マッサージ機のレビュー"),
    ("電動歯ブラシ", "toothbrush", 60, "音波・振動タイプの電動歯ブラシのレビュー"),
    ("シェーバー", "shaver", 70, "女性・男性用シェーバー・ムダ毛処理家電のレビュー"),
]

# 美顔器カテゴリとして既に存在する機能カテゴリ（これを親=美顔器の子にする）
FACIAL_FUNCTION_SLUGS = [
    "ems", "rf", "led", "tyouonpa", "イオン導入", "イオン導出",
    "マイクロカレント", "マッサージ機能", "美顔ローラー", "超音波",
    "ピーリング", "スチーマー", "温冷機能", "エレクトロポーション",
    "洗顔ブラシ", "レーザー", "光美容", "鼻用", "角栓ケア"
]


class Command(BaseCommand):
    help = "製品タイプを登録し、既存カテゴリ/商品を美顔器に紐付けます"

    def handle(self, *args, **opts):
        # 1. 製品タイプ作成
        type_map = {}
        for name, slug, order, desc in PRODUCT_TYPES:
            obj, created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "sort_order": order,
                    "description": desc,
                    "parent": None,
                },
            )
            if not created:
                obj.name = name
                obj.sort_order = order
                obj.description = desc
                obj.parent = None
                obj.save()
            type_map[slug] = obj
            self.stdout.write(f"  製品タイプ: {name} ({'created' if created else 'updated'})")

        bigankiki = type_map["bigankiki"]

        # 2. 既存のフラットカテゴリ（機能カテゴリ）を美顔器の子にする
        moved = 0
        for cat in Category.objects.filter(parent__isnull=True).exclude(slug__in=[t[1] for t in PRODUCT_TYPES]):
            cat.parent = bigankiki
            cat.save(update_fields=["parent"])
            moved += 1
        self.stdout.write(f"  既存機能カテゴリを美顔器の下に移動: {moved} 件")

        # 3. 既存商品すべてに product_type = 美顔器 を設定
        updated = Product.objects.filter(product_type__isnull=True).update(
            product_type=bigankiki
        )
        self.stdout.write(f"  既存商品に製品タイプ「美顔器」を設定: {updated} 件")

        self.stdout.write(self.style.SUCCESS("製品タイプ初期化完了"))
