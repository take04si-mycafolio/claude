"""商品ページへ統合した記事の旧URL → 商品slug の対応表。

2026-09-01: 単一SKUの記事は商品ページと内容が重複するため、記事を非公開にし
本文を Product.description へ移した（記事26本 / 商品34件）。旧記事URLは
IndexNow で送信済みのため、404 にせず対応する商品ページへ 301 で送る。

複数機種を1記事で扱っていたものは、代表機（記事で主役だった型番）へ送る。
"""

ARTICLE_REDIRECTS = {
    "beaum-tiny-flow-atd-b09-kuchikomi": "akibamac-12691292",
    "braun-nevo-silk-shaver-kuchikomi": "braun-10001166",  # 2機種を1記事にしていたもの。代表機へ送る
    "doctorair-3d-neck-massager-mn-10-kuchikomi": "bodyplus-10001941",
    "doctorair-buoru-dryer-bdr-02-kuchikomi": "bodyplus-10001946",
    "dyson-supersonic-travel-hd19-kuchikomi": "dyson-10002070",
    "lourdes-futomomogyu-ax-hj363-kuchikomi": "atex-net-10001818",
    "mirable-ex-kuchikomi": "miraiblue-10000056",
    "niplux-meguris-kuchikomi": "nissoplus-10000312",
    "panasonic-body-trimmer-er-gk9a-gk8a-kuchikomi": "panasonic-store-10001993",  # 2機種を1記事にしていたもの。代表機へ送る
    "panasonic-ionity-eh-ne9p-kuchikomi": "biccamera-15333473",
    "panasonic-kurukuru-eh-ke1n-kuchikomi": "yamada-denki-10681278",
    "panasonic-lamdash-palm-in-es-p550u-p530u": "panasonic-store-10000489",  # 2機種を1記事にしていたもの。代表機へ送る
    "panasonic-lamdash-palm-in-pro-6blade": "denkichiweb-10040047",  # 3機種を1記事にしていたもの。代表機へ送る
    "panasonic-skinact-steamer-eh-sb50-kuchikomi": "panasonic-store-10001790",
    "panasonic-smooth-epi-es-wh8c-kuchikomi": "panasonic-store-10001980",
    "philips-compact-shaver-800-500-kuchikomi": "compmoto-r-12654906",  # 2機種を1記事にしていたもの。代表機へ送る
    "quads-bisara-pro-2-kuchikomi": "akibamac-12693266",
    "salonia-cordless-12mm-sal25119-kuchikomi": "actonlineshop-10055538",
    "sharp-fe-ep600-kuchikomi": "biccamera-15483476",
    "sharp-ib-s510b-kuchikomi": "dtc-13169149",
    "shopjapan-airtec-dryer-shine": "shopjapan-10006087",
    "sixpad-recovery-massager-seat": "mtgec-beauty-10002657",  # 2機種を1記事にしていたもの。代表機へ送る
    "sonicare-3100-2100-kuchikomi": "ksdenki-10523936",  # 2機種を1記事にしていたもの。代表機へ送る
    "theraface-depuffing-wand-kuchikomi": "fitnessclub-10043177",
    "theraface-mask-glo-kuchikomi": "usbonline-10001349",
    "ulike-me-kuchikomi": "ulike-store-10000061",
}


# 記事どうしを統合した旧記事slug → 統合先の記事slug の対応表。
#
# 2026-09-07: 狙いが重複してGoogleに重複扱いされていた(両方 crawled_not_indexed)ペアを
# ユーザー指示で統合。統合元は is_published=False にし、旧URLは統合先へ 301 で送る。
# 統合先の記事には統合元の内容をペルソナから再構築して取り込んである。
ARTICLE_MERGES = {
    "biganrola": "rora",                        # 美顔ローラーの使い方 → 美顔ローラー(選び方+使い方)
    "hair-iron-2way": "hair-iron-osusume-hikaku",  # 2WAY単独 → ヘアアイロン総合比較(2WAYの柱を統合)
    # 2026-09-14 判断#5: 冷却機能で選ぶ → 痛くない脱毛器(冷却は1節に収めて統合)。
    # 予約エントリ: itami のリライト案を承認センターで反映した時点で cool が自動で非公開になり、301が有効になる。
    "datsumouki-cool": "datsumouki-itami",
}

# ARTICLE_MERGES の運用(2026-09-14〜):
# - 統合元が公開のままのエントリは「予約」。301もリンク付け替えも動かない
# - 承認センターで統合先のリライト案を反映すると、公開中の統合元を自動で非公開にする
#   (approval_center._execute_pending_merges)。以後 301 と本文内参照の付け替えが有効になる
