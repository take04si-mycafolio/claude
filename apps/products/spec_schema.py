# -*- coding: utf-8 -*-
"""カテゴリー別 仕様表(スペック表)の単一ソース定義。

- SPEC_SCHEMA[<製品タイプslug>] : 表示する列(項目)の順序付き定義
    key        : Product.specifications に保存する正規化キー(英語snake_case)
    label      : 仕様表に出す日本語ラベル
    unit       : 単位(任意・ラベル横に補足表示)
    group      : 表のグルーピング(基本情報/性能/サイズ/購入情報 等)
    core       : True=全カテゴリ共通のコア項目
    note       : 収集時のガイド(任意)

- LEGACY_ALIASES[<slug>] : 既存の不統一キー → 正規化キー の吸収マップ
    （日本語キー・camelCase・snake_case の混在を normalize で1本化する）

テンプレート・管理画面・収集スクリプトはすべてこの定義を参照する。
他カテゴリーは順次このファイルに追記していく。
"""

# ============================================================
# 美顔器 (slug=bigankiki)
# ============================================================
BIGANKI_FIELDS = [
    # --- 基本情報 ---
    {"key": "brand",          "label": "メーカー／ブランド", "group": "基本情報", "core": True},
    {"key": "model_number",   "label": "型番",               "group": "基本情報", "core": True},
    {"key": "device_type",    "label": "タイプ",             "group": "基本情報", "core": False,
     "note": "スチーマー/EMS/RF/超音波/イオン導入/LED/ウォーターピーリング/温冷/複合 等"},
    {"key": "care_functions", "label": "搭載ケア機能",       "group": "基本情報", "core": False,
     "note": "温スチーム・EMS・RF・イオン導入/導出・LED・超音波 など搭載する美容機構"},
    {"key": "target_area",    "label": "対応部位",           "group": "基本情報", "core": False,
     "note": "顔全体／目元／首・デコルテ など"},
    {"key": "release_date",   "label": "発売日",             "group": "基本情報", "core": True},
    # --- 性能 ---
    {"key": "power_source",   "label": "電源方式",           "group": "性能",   "core": True,
     "note": "AC電源／充電式(リチウムイオン)／乾電池"},
    {"key": "runtime",        "label": "連続使用時間",       "group": "性能",   "core": False, "note": "充電式の場合"},
    {"key": "charge_time",    "label": "充電時間",           "group": "性能",   "core": False, "note": "充電式の場合"},
    {"key": "heatup_time",    "label": "起動・立ち上がり時間", "group": "性能",  "core": False, "note": "スチーマー等"},
    {"key": "steam_temp",     "label": "スチーム温度",       "group": "性能",   "core": False, "unit": "℃", "note": "スチーマーのみ"},
    {"key": "tank_capacity",  "label": "タンク容量",         "group": "性能",   "core": False, "note": "スチーマーのみ"},
    {"key": "power_consumption", "label": "消費電力",        "group": "性能",   "core": False, "unit": "W"},
    {"key": "mode_count",     "label": "モード／レベル数",   "group": "性能",   "core": False},
    {"key": "waterproof",     "label": "防水(お風呂使用)",   "group": "性能",   "core": False, "note": "IPX等級 or 可否"},
    # --- サイズ ---
    {"key": "weight",         "label": "重量",               "group": "サイズ", "core": True},
    {"key": "dimensions",     "label": "本体寸法",           "group": "サイズ", "core": True},
    {"key": "color",          "label": "カラー展開",         "group": "サイズ", "core": False},
    {"key": "accessories",    "label": "付属品",             "group": "サイズ", "core": False},
    # --- 購入情報 ---
    {"key": "msrp",           "label": "希望小売価格(税込)", "group": "購入情報", "core": True},
    {"key": "price_range",    "label": "価格帯",             "group": "購入情報", "core": True},
    {"key": "warranty",       "label": "保証期間",           "group": "購入情報", "core": True},
    {"key": "official_url",   "label": "メーカー公式",       "group": "購入情報", "core": True, "note": "URL"},
]

BIGANKI_ALIASES = {
    # 既存日本語キー → 正規化キー
    "型番": "model_number",
    "重量": "weight",
    "タイプ": "device_type",
    "搭載機能": "care_functions",
    "対応機能": "care_functions",
    "対応部位": "target_area",
    "発売日": "release_date",
    "ブランド": "brand",
    "メーカー": "brand",
    "メーカー公式": "official_url",
    "本体寸法": "dimensions",
    "消費電力": "power_consumption",
    "消費電力(ミスト時)": "power_consumption",
    "消費電力(スチーム時)": "power_consumption",
    "起動時間": "heatup_time",
    "電源方式": "power_source",
    "スチーム温度": "steam_temp",
    "スチーム温度の目安": "steam_temp",
    "連続使用時間": "runtime",
    "充電時間": "charge_time",
    "プライスレンジ": "price_range",
    "希望小売価格(税込)": "msrp",
    "セール価格(税込)": "sale_price",       # 任意項目(表示はしないが温存)
    "鏡": "mirror",
    "ミラー": "mirror",
    "受賞": "award",
    "使える液体": "usable_liquid",
    "ノズル角度": "nozzle_angle",
    "モード数": "mode_count",
    "コード長": "cord_length",
    "付属品": "accessories",
    "タンク容量": "tank_capacity",
    "防水": "waterproof",
    "カラー": "color",
    "保証": "warranty",
    "保証期間": "warranty",
}

# ============================================================
# 脱毛器 (slug=datsumouki)  ※家庭用光美容器/レーザー脱毛器
# ============================================================
DATSUMOUKI_FIELDS = [
    # --- 基本情報 ---
    {"key": "brand",          "label": "メーカー／ブランド", "group": "基本情報", "core": True},
    {"key": "model_number",   "label": "型番",               "group": "基本情報", "core": True},
    {"key": "device_type",    "label": "タイプ",             "group": "基本情報", "core": False,
     "note": "家庭用光美容器／家庭用レーザー脱毛器 など"},
    {"key": "method",         "label": "脱毛方式",           "group": "基本情報", "core": False,
     "note": "IPL／THR（蓄熱式）／レーザー／ローラー併用 等"},
    {"key": "body_areas",     "label": "対応部位",           "group": "基本情報", "core": False,
     "note": "全身／顔／VIO の対応可否"},
    {"key": "release_date",   "label": "発売日",             "group": "基本情報", "core": True},
    # --- 性能 ---
    {"key": "cooling",        "label": "冷却機能",           "group": "性能",   "core": False,
     "note": "冷却方式(サファイア/ペルチェ等)・有無"},
    {"key": "flash_count",    "label": "照射回数(総ショット数)", "group": "性能", "core": False,
     "note": "例 約30万発／カートリッジ交換式は1個あたり"},
    {"key": "power_levels",   "label": "照射レベル段階",     "group": "性能",   "core": False, "note": "例 5段階"},
    {"key": "shot_mode",      "label": "照射モード",         "group": "性能",   "core": False,
     "note": "自動連射(オート)／単発／部位別モード 等"},
    {"key": "irradiation_interval", "label": "照射間隔(連射速度)", "group": "性能", "core": False,
     "note": "例 約0.7秒/発"},
    {"key": "lamp_life",      "label": "ランプ寿命／カートリッジ", "group": "性能", "core": False,
     "note": "カートリッジ交換式か本体一体か・総照射可能数"},
    {"key": "power_source",   "label": "電源方式",           "group": "性能",   "core": True,
     "note": "AC電源／充電式"},
    {"key": "voltage",        "label": "電圧(海外対応)",     "group": "性能",   "core": False,
     "note": "例 AC100-240V(海外対応)"},
    # --- サイズ ---
    {"key": "weight",         "label": "重量",               "group": "サイズ", "core": True},
    {"key": "dimensions",     "label": "本体寸法",           "group": "サイズ", "core": True},
    {"key": "color",          "label": "カラー展開",         "group": "サイズ", "core": False},
    {"key": "accessories",    "label": "付属品",             "group": "サイズ", "core": False},
    # --- 購入情報 ---
    {"key": "msrp",           "label": "希望小売価格(税込)", "group": "購入情報", "core": True},
    {"key": "price_range",    "label": "価格帯",             "group": "購入情報", "core": True},
    {"key": "warranty",       "label": "保証期間",           "group": "購入情報", "core": True},
    {"key": "official_url",   "label": "メーカー公式",       "group": "購入情報", "core": True, "note": "URL"},
]

DATSUMOUKI_ALIASES = {
    # 既存キー(主にsnake_case)→ 正規化キー
    "main_method": "method",
    "device_type": "device_type",
    "model_number": "model_number",
    "cooling": "cooling",
    "flash_count": "flash_count",
    "power_levels": "power_levels",
    "body_areas": "body_areas",
    "weight": "weight",
    "voltage": "voltage",
    "warranty": "warranty",
    "price_range": "price_range",
    "release_date": "release_date",
    # 日本語キーが来た場合の保険
    "メーカー": "brand",
    "ブランド": "brand",
    "型番": "model_number",
    "脱毛方式": "method",
    "方式": "method",
    "対応部位": "body_areas",
    "冷却機能": "cooling",
    "照射回数": "flash_count",
    "照射レベル": "power_levels",
    "重量": "weight",
    "本体寸法": "dimensions",
    "電源方式": "power_source",
    "電圧": "voltage",
    "保証": "warranty",
    "保証期間": "warranty",
    "発売日": "release_date",
    "メーカー公式": "official_url",
}

# ============================================================
# ドライヤー (slug=dryer)
# ============================================================
DRYER_FIELDS = [
    # --- 基本情報 ---
    {"key": "brand",          "label": "メーカー／ブランド", "group": "基本情報", "core": True},
    {"key": "model_number",   "label": "型番",               "group": "基本情報", "core": True},
    {"key": "device_type",    "label": "タイプ",             "group": "基本情報", "core": False,
     "note": "ヘアドライヤー／カールドライヤー(くるくる)／スタイリングドライヤー 等"},
    {"key": "ion_function",   "label": "搭載機能（イオン等）", "group": "基本情報", "core": False,
     "note": "ナノケア/高浸透ナノイー/マイナスイオン/プラズマクラスター 等＋速乾ノズル等の機構"},
    {"key": "release_date",   "label": "発売日",             "group": "基本情報", "core": True},
    # --- 性能 ---
    {"key": "air_volume",     "label": "風量",               "group": "性能",   "core": True, "unit": "㎥/分",
     "note": "最重要。TURBO/MAX時の値。単位 m³/分"},
    {"key": "wattage",        "label": "消費電力",           "group": "性能",   "core": False, "unit": "W"},
    {"key": "air_temp",       "label": "温風温度",           "group": "性能",   "core": False,
     "note": "例 約100℃(ターボ)/約80℃。モード別に併記可"},
    {"key": "temp_modes",     "label": "温度・モード切替",   "group": "性能",   "core": False,
     "note": "スカルプ(低温)/冷風/温冷リズム 等の搭載モード"},
    {"key": "noise_level",    "label": "運転音",             "group": "性能",   "core": False, "unit": "dB"},
    {"key": "voltage",        "label": "電源・海外対応",     "group": "性能",   "core": False,
     "note": "AC100V専用 か AC100-240V(海外対応) か"},
    # --- サイズ ---
    {"key": "weight",         "label": "重量",               "group": "サイズ", "core": True,
     "note": "本体のみ(コード除く)を基本に。例 約485g"},
    {"key": "dimensions",     "label": "本体寸法",           "group": "サイズ", "core": True,
     "note": "高さ×幅×奥行 等。単位mm/cm統一"},
    {"key": "cord_length",    "label": "コード長",           "group": "サイズ", "core": False, "note": "例 約1.7m"},
    {"key": "foldable",       "label": "折りたたみ",         "group": "サイズ", "core": False, "note": "可/不可"},
    {"key": "color",          "label": "カラー展開",         "group": "サイズ", "core": False},
    {"key": "accessories",    "label": "付属ノズル・アタッチメント", "group": "サイズ", "core": False},
    # --- 購入情報 ---
    {"key": "msrp",           "label": "希望小売価格(税込)", "group": "購入情報", "core": True,
     "note": "オープン価格なら省略しprice_rangeのみ"},
    {"key": "price_range",    "label": "価格帯",             "group": "購入情報", "core": True},
    {"key": "warranty",       "label": "保証期間",           "group": "購入情報", "core": True},
    {"key": "official_url",   "label": "メーカー公式",       "group": "購入情報", "core": True, "note": "URL"},
]

DRYER_ALIASES = {
    "型番": "model_number",
    "タイプ": "device_type",
    "機能": "ion_function",
    "重量": "weight",
    "風量": "air_volume",
    "priceTier": "price_range",
    "消費電力": "wattage",
    "温度": "air_temp",
    "温風温度": "air_temp",
    "コード長": "cord_length",
    "電源コード": "cord_length",
    "dB": "noise_level",
    "本体サイズ": "dimensions",
    "電源": "voltage",
    "その他": "accessories",
    "保証": "warranty",
    "保証期間": "warranty",
    # 日本語キーが来た場合の保険
    "メーカー": "brand",
    "ブランド": "brand",
    "発売日": "release_date",
    "カラー": "color",
    "本体寸法": "dimensions",
    "メーカー公式": "official_url",
}

# ============================================================
# ヘアアイロン (slug=hair-iron)
# ============================================================
HAIRIRON_FIELDS = [
    # --- 基本情報 ---
    {"key": "brand",          "label": "メーカー／ブランド", "group": "基本情報", "core": True},
    {"key": "model_number",   "label": "型番",               "group": "基本情報", "core": True},
    {"key": "iron_type",      "label": "タイプ",             "group": "基本情報", "core": False,
     "note": "ストレート／カール／2WAY／ブラシアイロン／コードレス 等"},
    {"key": "release_date",   "label": "発売日",             "group": "基本情報", "core": True},
    # --- 性能 ---
    {"key": "plate_width",    "label": "プレート幅",         "group": "性能",   "core": True,
     "note": "最重要。例 約27mm。カールはバレル径(例 32mm)"},
    {"key": "plate_material",  "label": "プレート素材・コーティング", "group": "性能", "core": False,
     "note": "チタン／セラミック／テフロン／シルク加工 等"},
    {"key": "temp_range",     "label": "温度範囲",           "group": "性能",   "core": False,
     "note": "例 120-200℃。最高温度も分かれば"},
    {"key": "temp_steps",     "label": "温度設定段階",       "group": "性能",   "core": False, "note": "例 5段階/1℃刻み"},
    {"key": "heatup_time",    "label": "立ち上がり時間",     "group": "性能",   "core": False, "note": "例 約25秒"},
    {"key": "power_source",   "label": "電源方式",           "group": "性能",   "core": True,
     "note": "AC電源／コードレス(充電式)／USB充電"},
    {"key": "voltage",        "label": "電圧(海外対応)",     "group": "性能",   "core": False,
     "note": "AC100V専用 か AC100-240V(海外対応)"},
    {"key": "battery",        "label": "バッテリー・連続使用", "group": "性能", "core": False,
     "note": "コードレス機: 容量/連続使用時間/充電時間"},
    {"key": "auto_off",       "label": "自動電源OFF",        "group": "性能",   "core": False, "note": "有/無・時間"},
    {"key": "wattage",        "label": "消費電力",           "group": "性能",   "core": False, "unit": "W"},
    # --- サイズ ---
    {"key": "weight",         "label": "重量",               "group": "サイズ", "core": True},
    {"key": "dimensions",     "label": "本体寸法",           "group": "サイズ", "core": True},
    {"key": "cord_length",    "label": "コード長",           "group": "サイズ", "core": False, "note": "AC機のみ"},
    {"key": "color",          "label": "カラー展開",         "group": "サイズ", "core": False},
    # --- 購入情報 ---
    {"key": "msrp",           "label": "希望小売価格(税込)", "group": "購入情報", "core": True},
    {"key": "price_range",    "label": "価格帯",             "group": "購入情報", "core": True},
    {"key": "warranty",       "label": "保証期間",           "group": "購入情報", "core": True},
    {"key": "official_url",   "label": "メーカー公式",       "group": "購入情報", "core": True, "note": "URL"},
]

HAIRIRON_ALIASES = {
    "modelNumber": "model_number",
    "plateWidth": "plate_width",
    "plateSize": "plate_width",
    "material": "plate_material",
    "plateMaterial": "plate_material",
    "temperatureRange": "temp_range",
    "heatup": "heatup_time",
    "heatUpTime": "heatup_time",
    "voltage": "voltage",
    "battery": "battery",
    "autoOff": "auto_off",
    "wattage": "wattage",
    "power": "wattage",
    "weight": "weight",
    "dimensions": "dimensions",
    "cord": "cord_length",
    "cordLength": "cord_length",
    "priceRange": "price_range",
    "releaseDate": "release_date",
    # 日本語キーが来た場合の保険
    "メーカー": "brand",
    "ブランド": "brand",
    "型番": "model_number",
    "タイプ": "iron_type",
    "プレート幅": "plate_width",
    "プレート素材": "plate_material",
    "温度範囲": "temp_range",
    "重量": "weight",
    "本体寸法": "dimensions",
    "電源方式": "power_source",
    "電圧": "voltage",
    "コード長": "cord_length",
    "保証": "warranty",
    "保証期間": "warranty",
    "発売日": "release_date",
    "メーカー公式": "official_url",
}

# ============================================================
# レジストリ
# ============================================================
SPEC_SCHEMA = {
    "bigankiki": BIGANKI_FIELDS,
    "datsumouki": DATSUMOUKI_FIELDS,
    "dryer": DRYER_FIELDS,
    "hair-iron": HAIRIRON_FIELDS,
}

LEGACY_ALIASES = {
    "bigankiki": BIGANKI_ALIASES,
    "datsumouki": DATSUMOUKI_ALIASES,
    "dryer": DRYER_ALIASES,
    "hair-iron": HAIRIRON_ALIASES,
}

# 仕様表には出さないが温存する内部メタ(接頭辞 _ で名前空間分離)
INTERNAL_META_KEYS = {
    "status", "priority", "featureMemo", "memo", "specVerified", "spec_verified",
    "releaseDatePrecision", "release_date_precision",
    "modelName", "priority_memo", "note", "operation",
}


def get_schema(slug):
    """製品タイプslugの仕様表フィールド定義を返す(未定義なら空list)。"""
    return SPEC_SCHEMA.get(slug, [])


def get_field_keys(slug):
    return [f["key"] for f in get_schema(slug)]


def spec_table_data(slug, specs):
    """製品タイプslugのスキーマに沿って、値のある項目だけをグループ単位で
    並べた仕様表データを返す。Web(テンプレートタグ)とAPI(シリアライザ)の共通ソース。

    返り値: [{"group": str, "rows": [
                {"key","label","value","unit","is_url"}, ...]}, ...]
    値が1つも無ければ空list。
    """
    schema = get_schema(slug)
    if not schema or not isinstance(specs, dict) or not specs:
        return []
    groups = []
    index = {}  # group_name -> rows list
    for f in schema:
        val = specs.get(f["key"])
        sval = ("" if val is None else str(val)).strip()
        if not sval:
            continue
        g = f.get("group", "仕様")
        if g not in index:
            index[g] = []
            groups.append({"group": g, "rows": index[g]})
        # 単位は値に未包含のときだけ補足表示(収集値は単位を内包しがちで二重表示を防ぐ)
        unit = f.get("unit", "")
        if unit and unit in sval:
            unit = ""
        index[g].append({
            "key": f["key"],
            "label": f["label"],
            "value": sval,
            "unit": unit,
            "is_url": f["key"] == "official_url",
        })
    return groups


def public_specifications(specs):
    """内部メタ(_internal)を除いた表示用 specifications を返す(APIの生スペック用)。"""
    if not isinstance(specs, dict):
        return {}
    return {k: v for k, v in specs.items() if k != "_internal"}


def normalize_specifications(slug, specs):
    """既存 specifications を正規化キーに寄せる。

    - LEGACY_ALIASES でキーをリネーム
    - 内部メタは _internal にまとめて温存
    - 値が空/プレースホルダ('要確認'等)は除外
    返り値: (normalized_dict, internal_dict)
    """
    if not isinstance(specs, dict):
        return {}, {}
    aliases = LEGACY_ALIASES.get(slug, {})
    out, internal = {}, {}
    placeholders = {"", "要確認", "不明", "-", "—", "未確認", "なし(要確認)"}
    junk_lower = {"unknown", "n/a", "na", "none", "null", "tbd"}
    for k, v in specs.items():
        if k in INTERNAL_META_KEYS:
            internal[k] = v
            continue
        canon = aliases.get(k, k)
        sval = ("" if v is None else str(v)).strip()
        if sval in placeholders or sval.lower() in junk_lower:
            continue
        # 既存の正規化値を優先(同一canonへ複数legacyが来た場合)
        if canon not in out or not str(out.get(canon, "")).strip():
            out[canon] = v
    return out, internal
