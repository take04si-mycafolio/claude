"""Amazon / 楽天 共通: 重複判定 + Product upsert ロジック (統合版)。"""
import re
from difflib import SequenceMatcher

from django.utils import timezone
from django.utils.text import slugify


_PUNCT = r"[【】\(\)\[\]「」『』・,.:、。/／\\\-_!!??*＊+~〜=＝]"

# 型番パターン
MODEL_PATTERN = re.compile(r"\b([A-Z][A-Z0-9-]*\d[A-Z0-9-]*)\b")


def extract_model_numbers(title):
    if not title:
        return set()
    found = MODEL_PATTERN.findall(title.upper())
    out = set()
    for m in found:
        m = m.strip("-")
        # 3文字以上 + 数字を含む (USB/EMS/RF 等の略語を弾く)
        if len(m) >= 3 and any(ch.isdigit() for ch in m):
            out.add(m)
            out.add(m.replace("-", ""))
    return out


# ブランド別名
_BRAND_ALIASES = {
    "ヤーマン": ["YA-MAN", "YA‐MAN", "YAMAN", "YA MAN"],
    "Panasonic": ["パナソニック", "ナショナル"],
    "パナソニック": ["Panasonic"],
    "美ルル": ["belulu", "BELULU", "Belulu"],
    "MTG": ["mtg"],
    "ReFa": ["リファ"],
}


def _strip_brand(text, brand_hint):
    if not brand_hint:
        return text
    variants = [brand_hint] + _BRAND_ALIASES.get(brand_hint, [])
    for v in variants:
        text = re.sub(re.escape(v), " ", text, flags=re.IGNORECASE)
    return re.sub(r"[\s\u3000]+", " ", text).strip(" 　-_+")


# pykakasi (カタカナ→ローマ字) 用の遅延ロード
_kakasi = None


def _to_romaji(text):
    global _kakasi
    if not text:
        return ""
    if _kakasi is None:
        try:
            import pykakasi
            _kakasi = pykakasi.kakasi()
        except ImportError:
            _kakasi = False
    if not _kakasi:
        return text
    try:
        result = _kakasi.convert(text)
        return "".join([x.get("hepburn", "") for x in result])
    except Exception:
        return text


def normalize_name(s):
    if not s:
        return ""
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(_PUNCT, "", s)
    return s.lower()


def similarity(a, b):
    if not a or not b:
        return 0.0
    a_n, b_n = normalize_name(a), normalize_name(b)
    a_r, b_r = normalize_name(_to_romaji(a)), normalize_name(_to_romaji(b))
    scores = [
        SequenceMatcher(None, a_n, b_n).ratio(),
        SequenceMatcher(None, a_r, b_r).ratio(),
        SequenceMatcher(None, a_n, b_r).ratio(),
        SequenceMatcher(None, a_r, b_n).ratio(),
    ]
    try:
        from rapidfuzz import fuzz
        for x, y in [(a_n, b_n), (a_r, b_r), (a_n, b_r), (a_r, b_n)]:
            if not x or not y:
                continue
            scores.append(fuzz.partial_ratio(x, y) / 100.0)
            scores.append(fuzz.token_set_ratio(x, y) / 100.0)
    except ImportError:
        pass
    return max(scores)


def clean_product_name(title, brand_hint=None):
    if not title:
        return ""

    # 1. 《...》 内優先
    m2 = re.search(r"《([^》]+)》", title)
    if m2:
        core = m2.group(1).strip()
        return _strip_brand(core, brand_hint)[:80]

    cleaned = title

    # 2. 【】〔〕[] 削除
    cleaned = re.sub(r"【[^】]*】", " ", cleaned)
    cleaned = re.sub(r"〔[^〕]*〕", " ", cleaned)
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)

    # 3. ｜ 分割: 最長セグメント採用
    if "｜" in cleaned or "|" in cleaned:
        parts = [p.strip() for p in re.split(r"[｜|]", cleaned) if p.strip()]
        if parts:
            cleaned = max(parts, key=len)

    # 4. SEO ノイズ削除
    noise_patterns = [
        r"(公式店|公式|正規品|国内正規品|保証付|長期保証|無料延長保証|安心の上場企業)",
        r"楽天\d+位(受賞)?", r"ランキング受賞", r"ランキング\d+位",
        r"レビュー特典", r"レビューで",
        r"送料無料", r"即納", r"新品", r"中古品?", r"あす楽(関東(_対応)?)?",
        r"\d{1,3}(,\d{3})*\s*→\s*\d{1,3}(,\d{3})*\s*円?",
        r"\d{1,3}(,\d{3})*\s*円(オフ|OFF)?",
        r"\d+\s*%\s*(OFF|オフ)?",
        r"クーポン\S*",
        r"(ふるさと納税|お買い物マラソン|スーパーDEAL|お得|セール)",
        r"(母の日|父の日|敬老の日|GW|お正月|新春|ホワイトデー|限定価格?|特典|プレゼント|割引?)",
        r"P\d+倍", r"ポイント\d+倍?",
        r"5年保証付",
        r"期間限定", r"最安値(に挑戦)?",
        r"\bNEW\b", r"\bnew\b",
        r"無料ラッピング", r"無料", r"ラッピング",
    ]
    for p in noise_patterns:
        cleaned = re.sub(p, " ", cleaned, flags=re.IGNORECASE)

    # 5. カテゴリ語・機能語削除 (長い語から)
    generic_words = [
        "光美容器", "光美顔器", "LED美顔器", "RF美顔器", "EMS美顔器",
        "美顔ローラー", "美容ローラー", "美顔器具", "美容器具",
        "美顔器", "美容器",
        "光エステ", "ホームエステ", "サロン仕様", "サロン級", "サロン",
        "フォトフェイシャル", "フェイシャルケア", "フェイスケア",
        "リフトケア", "エイジングケア", "スキンケア", "毛穴ケア", "ニキビケア", "頭皮ケア", "ボディケア",
        "ハンディタイプ", "ハンディ", "コードレス",
        "多機能", "オールインワン", "ウェアラブル", "ハンズフリー",
        "防水仕様", "防水", "充電式", "USB充電", "USB",
        "レディース", "メンズ", "プレゼント", "ギフト",
        "がご自宅で", "ご自宅で",
        "頭皮", "ブラシ", "シートパッド",
        "イオン導入", "イオン導出", "超音波",
    ]
    for w in generic_words:
        cleaned = re.sub(re.escape(w), " ", cleaned)

    # 5.5 型番後ろをカット
    target_models = extract_model_numbers(cleaned)
    if target_models:
        last_end = 0
        upper = cleaned.upper()
        for model in target_models:
            idx = upper.rfind(model)
            if idx >= 0:
                end = idx + len(model)
                if end > last_end:
                    last_end = end
        if last_end > 0:
            cleaned = cleaned[:last_end]

    # 6. 区切り文字で先頭セグメント
    for sep in ["、", ",", "/", "／", "!", "!", "?", "?", ":", ":", ";", ";", "(", "(", "「"]:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0]

    # 7. 装飾記号
    cleaned = re.sub(r"[★☆✨✓◎◯○●▼▲☑＋＝]", " ", cleaned)
    cleaned = re.sub(r"[*＊~〜=]+", " ", cleaned)

    # 8. ブランド除去 (空なら除去前を保持)
    core_before = cleaned
    cleaned = _strip_brand(cleaned, brand_hint)
    if not cleaned.strip():
        cleaned = core_before

    # 9. スペース整理
    cleaned = re.sub(r"[\s\u3000]+", " ", cleaned).strip(" 　-_.")

    # 10. 重複ワード除去
    seen = set()
    deduped = []
    for t in cleaned.split():
        if t not in seen:
            deduped.append(t)
            seen.add(t)
    cleaned = " ".join(deduped)

    # 11. 40文字以内
    if len(cleaned) > 40:
        cleaned = cleaned[:40].rstrip(" 　-_.")

    return cleaned or title[:40]


_ACCESSORY_KEYWORDS = [
    "コットン", "電源", "ケーブル", "コード", "ジェル", "ローション",
    "シート", "シートマスク", "パッド", "アタッチメント", "替え", "交換",
    "予備", "詰め替え", "サンプル", "ボトル",
]


def is_accessory(title):
    if not title:
        return False
    return any(kw in title for kw in _ACCESSORY_KEYWORDS)


def find_existing_product(parsed, ptype, fuzzy_threshold=0.80):
    from apps.products.models import Product

    asin = parsed.get("asin")
    rakuten_code = parsed.get("rakuten_item_code")
    title = parsed.get("title", "")

    if asin:
        p = Product.objects.filter(asin=asin).first()
        if p:
            return (p, "asin")

    if rakuten_code:
        p = Product.objects.filter(rakuten_item_code=rakuten_code).first()
        if p:
            return (p, "rakuten_item_code")

    qs = list(Product.objects.filter(product_type=ptype).only("id", "name", "slug"))
    norm_target = normalize_name(title)

    for p in qs:
        if normalize_name(p.name) == norm_target:
            return (p, "name_exact")

    target_models = extract_model_numbers(title)
    if target_models:
        for p in qs:
            existing_models = extract_model_numbers(p.name)
            if existing_models & target_models:
                return (p, "model_number")

    best, best_score = None, 0.0
    for p in qs:
        s = similarity(p.name, title)
        if s > best_score:
            best, best_score = p, s
    if not best:
        return (None, None)

    if target_models:
        existing_models = extract_model_numbers(best.name)
        if not existing_models:
            if best_score >= 0.97:
                return (best, "fuzzy_confident")
            return (None, None)
        if not (existing_models & target_models):
            return (None, None)

    if best_score >= 0.95:
        return (best, "fuzzy_confident")
    if best_score >= fuzzy_threshold:
        return (best, "fuzzy")
    return (None, None)


def _generate_slug(base, fallback="item"):
    from apps.products.models import Product

    slug = (slugify(base or "", allow_unicode=True) or fallback)[:60]
    if not Product.objects.filter(slug=slug).exists():
        return slug
    i = 2
    while Product.objects.filter(slug=f"{slug}-{i}").exists():
        i += 1
    return f"{slug}-{i}"


def upsert_from_rakuten(parsed, ptype, auto_create=True, allow_fuzzy_update=False, brand_hint=None, publish=True):
    from apps.products.models import Product

    existing, match_type = find_existing_product(parsed, ptype)
    title = parsed.get("title", "")
    rakuten_code = parsed.get("rakuten_item_code", "")
    aff_url = parsed.get("affiliate_url") or parsed.get("rakuten_url", "")
    image_url = parsed.get("image_url", "")
    price = parsed.get("price")

    if existing:
        if match_type == "fuzzy" and not allow_fuzzy_update:
            return (existing, "fuzzy_review")
        existing.rakuten_item_code = rakuten_code
        existing.rakuten_url = aff_url
        if not existing.image_url and image_url:
            existing.image_url = image_url
        if not existing.price and price:
            existing.price = price
        existing.rakuten_synced_at = timezone.now()
        if not isinstance(existing.api_data, dict):
            existing.api_data = {}
        existing.api_data["rakuten"] = parsed.get("raw", {})
        existing.save()
        return (existing, "updated")

    if not auto_create:
        return (None, "skipped")

    cleaned_name = clean_product_name(title, brand_hint=brand_hint)
    slug = _generate_slug(rakuten_code.replace(":", "-") if rakuten_code else cleaned_name, "r-item")
    p = Product.objects.create(
        name=cleaned_name[:200],
        slug=slug,
        product_type=ptype,
        brand=(brand_hint or "")[:100],
        rakuten_item_code=rakuten_code,
        rakuten_url=aff_url,
        image_url=image_url,
        price=price,
        description=(parsed.get("caption", "") or "")[:500],
        is_published=publish,
        source="rakuten",
        rakuten_synced_at=timezone.now(),
        api_data={"rakuten": parsed.get("raw", {})},
    )
    return (p, "created")


def upsert_from_amazon(parsed, ptype, auto_create=True, allow_fuzzy_update=False, brand_hint=None, publish=True):
    from apps.products.models import Product

    existing, match_type = find_existing_product(parsed, ptype)
    title = parsed.get("title", "")
    asin = parsed.get("asin", "")
    amazon_url = parsed.get("amazon_url", "")
    image_url = parsed.get("image_url", "")
    price = parsed.get("price")
    brand = parsed.get("brand", "")

    if existing:
        if match_type == "fuzzy" and not allow_fuzzy_update:
            return (existing, "fuzzy_review")
        existing.asin = asin
        existing.amazon_url = amazon_url
        if not existing.image_url and image_url:
            existing.image_url = image_url
        if not existing.price and price:
            existing.price = price
        if not existing.brand and brand:
            existing.brand = brand
        existing.amazon_synced_at = timezone.now()
        if not isinstance(existing.api_data, dict):
            existing.api_data = {}
        existing.api_data["amazon"] = parsed.get("raw", {})
        existing.save()
        return (existing, "updated")

    if not auto_create:
        return (None, "skipped")

    cleaned_name = clean_product_name(title, brand_hint=brand_hint)
    slug = _generate_slug(asin or cleaned_name, "a-item")
    p = Product.objects.create(
        name=cleaned_name[:200],
        slug=slug,
        product_type=ptype,
        brand=(brand_hint or brand or "")[:100],
        asin=asin,
        amazon_url=amazon_url,
        image_url=image_url,
        price=price,
        is_published=publish,
        source="amazon",
        amazon_synced_at=timezone.now(),
        api_data={"amazon": parsed.get("raw", {})},
    )
    return (p, "created")
