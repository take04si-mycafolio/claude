# -*- coding: utf-8 -*-
"""メーカー(ブランド)ページの単一ソース定義。

Product.brand は自由入力で表記ゆれ・親会社/ブランド名の混在があるため、
ここで「認知ブランド名」に正規化してページ化する。

各ブランド def:
  slug    : URL (例 /brands/refa/)
  name    : ページ表示名(認知ブランド名)
  aka     : 別名・読み(説明文/keywordsに使用。表記ゆれ吸収の補助)
  match   : Product.brand がこれらの値のものを集約(表記ゆれ・親会社名を含む)
  exclude_name : 商品名にこれを含むものは除外(別ブランドOEMの切り分け用)
  tier    : 1=中核 / 2=準主力 / 3=ボーダー(表示順とバッジ用)

ピックアップ基準: 登録商品3点以上で一覧として成立するメーカー(2026-06-23時点)。
"""

BRANDS = [
    # ---- Tier 1: 中核(8点以上 or 高口コミ) ----
    {"slug": "yaman",        "name": "ヤーマン",        "aka": "YA-MAN", "tier": 1,
     "match": ["ヤーマン", "YA-MAN"]},
    {"slug": "panasonic",    "name": "パナソニック",    "aka": "Panasonic", "tier": 1,
     "match": ["パナソニック"]},
    {"slug": "refa",         "name": "ReFa",            "aka": "リファ／MTG", "tier": 1,
     "match": ["ReFa", "MTG"], "exclude_name": ["PAO"]},
    {"slug": "belulu",       "name": "美ルル",          "aka": "belulu／ベルル", "tier": 1,
     "match": ["美ルル"]},
    {"slug": "koizumi",      "name": "コイズミ",        "aka": "KOIZUMI", "tier": 1,
     "match": ["コイズミ"]},
    {"slug": "salonia",      "name": "SALONIA",         "aka": "サロニア", "tier": 1,
     "match": ["SALONIA"]},
    {"slug": "create-ion",   "name": "クレイツ",        "aka": "CREATE ION／クレイツイオン", "tier": 1,
     "match": ["クレイツ"]},
    {"slug": "kinujo",       "name": "KINUJO",          "aka": "絹女／きぬじょ", "tier": 1,
     "match": ["KINUJO"]},
    {"slug": "lumielina",    "name": "リュミエリーナ",  "aka": "ヘアビューロン／レプロナイザー／Bioprogramming", "tier": 1,
     "match": ["リュミエリーナ", "ヘアビューロン"]},
    {"slug": "areti",        "name": "Areti",           "aka": "アレティ", "tier": 1,
     "match": ["Areti", "アレティ"]},
    {"slug": "geske",        "name": "GESKE",           "aka": "ゲスケ", "tier": 1,
     "match": ["GESKE"]},
    # ---- Tier 2: 準主力(5〜7点) ----
    {"slug": "tescom",       "name": "テスコム",        "aka": "TESCOM", "tier": 2,
     "match": ["テスコム"]},
    {"slug": "exideal",      "name": "Exideal",         "aka": "エクスイディアル／ハスラック", "tier": 2,
     "match": ["ハスラック"]},
    {"slug": "vidal-sassoon", "name": "ヴィダルサスーン", "aka": "Vidal Sassoon", "tier": 2,
     "match": ["ヴィダルサスーン"]},
    # ---- Tier 3: ボーダー(3〜4点) ----
    {"slug": "hitachi",      "name": "日立",            "aka": "HITACHI", "tier": 3,
     "match": ["日立"]},
    {"slug": "philips",      "name": "フィリップス",    "aka": "PHILIPS", "tier": 3,
     "match": ["フィリップス"]},
    {"slug": "cosbeauty",    "name": "コスビューティー", "aka": "CosBeauty", "tier": 3,
     "match": ["コスビューティー"]},
    {"slug": "iris-ohyama",  "name": "アイリスオーヤマ", "aka": "IRIS OHYAMA", "tier": 3,
     "match": ["アイリスオーヤマ"]},
    {"slug": "brighte",      "name": "Brighte",         "aka": "ブライト", "tier": 3,
     "match": ["Brighte"]},
    {"slug": "mytrex",       "name": "MYTREX",          "aka": "マイトレックス／創通メディカル", "tier": 3,
     "match": ["MYTREX", "創通メディカル"]},
    {"slug": "ulike",        "name": "Ulike",           "aka": "ユーライク", "tier": 3,
     "match": ["Ulike"]},
]

_BY_SLUG = {b["slug"]: b for b in BRANDS}


def get_brand(slug):
    return _BY_SLUG.get(slug)


def all_brands():
    return BRANDS


def filter_products(qs, bdef):
    """ブランド def に該当する商品に qs を絞り込む。"""
    qs = qs.filter(brand__in=bdef["match"])
    for kw in bdef.get("exclude_name", []):
        qs = qs.exclude(name__icontains=kw)
    return qs
