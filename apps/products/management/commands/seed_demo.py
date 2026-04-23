"""開発用のサンプル商品・口コミを投入します"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.products.models import Category, Product
from apps.reviews.models import Review

User = get_user_model()

SAMPLE_CATEGORIES = ["EMS美顔器", "RF美顔器", "イオン導入美顔器", "LED美顔器"]

SAMPLE_PRODUCTS = [
    {
        "name": "リフトアップEMS美顔器 PRO",
        "brand": "BeautyTech",
        "price": 38000,
        "description": "EMS刺激でフェイスラインを引き締める高機能美顔器。1日10分の使用で手軽にケアできます。",
        "features": "・EMSで筋肉にアプローチ\n・防水仕様でお風呂でも使える\n・5段階の強度調整",
        "categories": ["EMS美顔器"],
    },
    {
        "name": "RFラジオ波 美顔器 温感ケア",
        "brand": "SkinLab",
        "price": 29800,
        "description": "温感RFで角層深くまでアプローチ。毛穴ケアからハリケアまで幅広く対応。",
        "features": "・ラジオ波(RF)搭載\n・温感40〜45℃\n・コードレス充電式",
        "categories": ["RF美顔器"],
    },
    {
        "name": "イオン導入 美顔器 Mini",
        "brand": "CosmeWave",
        "price": 14800,
        "description": "コンパクトで手軽に使えるイオン導入美顔器。化粧水の浸透をサポート。",
        "features": "・イオン導入/導出\n・軽量95g\n・USB-C充電",
        "categories": ["イオン導入美顔器"],
    },
    {
        "name": "LED光美顔器 マスク型",
        "brand": "GlowMask",
        "price": 45000,
        "description": "赤色・青色・黄色LEDを搭載した全顔ケアマスク。装着するだけの簡単ケア。",
        "features": "・3色LED搭載\n・ハンズフリー\n・タイマー機能",
        "categories": ["LED美顔器"],
    },
]

SAMPLE_USERS = [
    {"email": "hanako@example.com", "nickname": "はなこ", "age_range": "30s", "skin_type": "dry"},
    {"email": "yuki@example.com", "nickname": "ゆき", "age_range": "40s", "skin_type": "sensitive"},
    {"email": "ami@example.com", "nickname": "あみ", "age_range": "20s", "skin_type": "combination"},
]

SAMPLE_REVIEWS = [
    {"rating": 5, "title": "頬のラインがキリッとしました", "body": "使い始めて2週間ほどで、フェイスラインがすっきりした気がします。痛みもなく使いやすいです。",
     "usage_period": "1-3m", "effectiveness": "excellent"},
    {"rating": 4, "title": "コスパ良好、初心者向き", "body": "操作が簡単で、肌荒れもありませんでした。もう少しパワーがあると嬉しいかも。",
     "usage_period": "lt1m", "effectiveness": "good"},
    {"rating": 3, "title": "可もなく不可もなく", "body": "劇的な効果は感じませんでしたが、肌のハリは少し出た気がします。",
     "usage_period": "3-6m", "effectiveness": "neutral"},
]


class Command(BaseCommand):
    help = "デモ用データを投入します"

    def handle(self, *args, **opts):
        # カテゴリ
        cats = {}
        for name in SAMPLE_CATEGORIES:
            c, _ = Category.objects.get_or_create(name=name)
            cats[name] = c

        # 商品
        products = []
        for p in SAMPLE_PRODUCTS:
            obj, _ = Product.objects.get_or_create(
                name=p["name"],
                defaults={
                    "brand": p["brand"],
                    "price": p["price"],
                    "description": p["description"],
                    "features": p["features"],
                },
            )
            obj.categories.set([cats[c] for c in p["categories"]])
            products.append(obj)

        # ユーザー
        users = []
        for u in SAMPLE_USERS:
            user, created = User.objects.get_or_create(
                email=u["email"],
                defaults={
                    "username": u["email"],
                    "nickname": u["nickname"],
                    "age_range": u["age_range"],
                    "skin_type": u["skin_type"],
                    "email_verified": True,
                },
            )
            if created:
                user.set_password("demopass1234")
                user.save()
            users.append(user)

        # レビュー
        for i, product in enumerate(products):
            for j, r in enumerate(SAMPLE_REVIEWS):
                user = users[j % len(users)]
                Review.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={
                        "rating": r["rating"],
                        "title": r["title"],
                        "body": r["body"],
                        "usage_period": r["usage_period"],
                        "effectiveness": r["effectiveness"],
                        "skin_type": user.skin_type,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"デモデータ投入完了: 商品 {len(products)} 件 / ユーザー {len(users)} 人"
        ))
        self.stdout.write("デモログイン: hanako@example.com / demopass1234")
