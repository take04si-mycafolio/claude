"""SEOキーワード戦略の初期データ投入

使い方:
  python manage.py seed_seo_keywords
"""
from django.core.management.base import BaseCommand
from apps.aiarticles.models import SeoKeywordStrategy


INITIAL_KEYWORDS = [
    # ===== 美顔器 =====
    {
        "category": "美顔器", "keyword": "美顔器 効果", "article_type": "effect",
        "search_volume": 8100, "commercial_intent_score": 4, "competition_score": 4,
        "search_intent": "美顔器に効果があるか知りたい・購入を迷っている層。比較データを求める。",
    },
    {
        "category": "美顔器", "keyword": "美顔器 口コミ", "article_type": "review",
        "search_volume": 6600, "commercial_intent_score": 5, "competition_score": 4,
        "search_intent": "実際の使用者のリアルな評価を知りたい層。CV直前に近い検索意図。",
    },
    {
        "category": "美顔器", "keyword": "美顔器 おすすめ", "article_type": "ranking",
        "search_volume": 14800, "commercial_intent_score": 5, "competition_score": 5,
        "search_intent": "どの美顔器を買うべきか比較・ランキング情報を求める層。最重要キーワード。",
    },
    {
        "category": "美顔器", "keyword": "RF美顔器 EMS 違い", "article_type": "comparison",
        "search_volume": 1300, "commercial_intent_score": 4, "competition_score": 2,
        "search_intent": "RFとEMSの技術的な違いを知りたい・自分に合う方を選びたい層。CV高め。",
    },
    {
        "category": "美顔器", "keyword": "スチーマー 美顔器 効果", "article_type": "effect",
        "search_volume": 2900, "commercial_intent_score": 3, "competition_score": 3,
        "search_intent": "スチーマー型美顔器の効果を知りたい・購入を検討している層。",
    },

    # ===== 脱毛器 =====
    {
        "category": "脱毛器", "keyword": "家庭用脱毛器 効果", "article_type": "effect",
        "search_volume": 4400, "commercial_intent_score": 4, "competition_score": 4,
        "search_intent": "家庭用脱毛器に本当に効果があるか不安・調べている層。",
    },
    {
        "category": "脱毛器", "keyword": "家庭用脱毛器 口コミ", "article_type": "review",
        "search_volume": 3600, "commercial_intent_score": 5, "competition_score": 4,
        "search_intent": "脱毛器の実際の使用感・効果を口コミで判断したい層。",
    },

    # ===== ドライヤー =====
    {
        "category": "ドライヤー", "keyword": "ドライヤー 速乾 比較", "article_type": "comparison",
        "search_volume": 2400, "commercial_intent_score": 4, "competition_score": 3,
        "search_intent": "速乾ドライヤーを複数比較したい・最速のものを選びたい層。",
    },
    {
        "category": "ドライヤー", "keyword": "ドライヤー 美髪 おすすめ", "article_type": "ranking",
        "search_volume": 5400, "commercial_intent_score": 5, "competition_score": 4,
        "search_intent": "美髪ケアに特化したドライヤーのランキング・おすすめを求める層。",
    },

    # ===== ギフト =====
    {
        "category": "美容家電", "keyword": "美容家電 プレゼント おすすめ", "article_type": "ranking",
        "search_volume": 2900, "commercial_intent_score": 5, "competition_score": 3,
        "search_intent": "プレゼント用の美容家電を選びたい層。母の日・誕生日需要が大きい。",
    },
]


class Command(BaseCommand):
    help = "Initial SEO keyword strategy seed (initial 10 keywords)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="既存の同一keywordレコードを上書き")

    def handle(self, *args, **opts):
        n_created, n_existing, n_updated = 0, 0, 0
        for kw_data in INITIAL_KEYWORDS:
            obj, created = SeoKeywordStrategy.objects.get_or_create(
                keyword=kw_data["keyword"],
                defaults=kw_data,
            )
            if created:
                n_created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ 作成: {obj.keyword} (priority={obj.priority_score:.1f})"
                ))
            elif opts.get("reset"):
                for k, v in kw_data.items():
                    setattr(obj, k, v)
                obj.save()
                n_updated += 1
                self.stdout.write(self.style.WARNING(
                    f"  ↻ 更新: {obj.keyword} (priority={obj.priority_score:.1f})"
                ))
            else:
                n_existing += 1
                self.stdout.write(f"  - 既存: {obj.keyword} (priority={obj.priority_score:.1f})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"完了: 作成 {n_created}件 / 更新 {n_updated}件 / 既存 {n_existing}件"
        ))
        self.stdout.write(f"全レコード数: {SeoKeywordStrategy.objects.count()}件")
