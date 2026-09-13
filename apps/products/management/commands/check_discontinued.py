"""楽天Open APIで流通状況を調べ、公式確認にかける候補を絞り込む(2026-09-07ユーザー指示)。

  1. 商品の rakuten_item_code を itemCode 検索
  2. 見つからなければ 型番(specifications.model_number) と 商品名 で在庫あり検索
  3. どちらでも在庫が確認できないものを「要確認」として出す

★ 重要(2026-09-07の実測で判明): **楽天の在庫有無は生産終了の判定に使えない**。
  - 終売品でも在庫処分・並行輸入で売られている(例: ナノケア EH-NA0J は公式で後継機に
    切り替わっているのに「新品箱訳あり」で流通)
  - 逆に現行品でも楽天に扱いが無い/itemCodeが空で名前検索が効かないことがある
    (実測: 在庫が見つからなかった7件は**全て公式で現行**だった)
  したがってこのコマンドは **候補の絞り込み専用**。生産終了かどうかは必ず
  メーカー公式サイト(製品ページの「生産終了」表記・現行ラインアップからの消滅・
  後継機の告知)で確認してから is_discontinued を変えること。
  誤って終売にすると商品ページ・一覧・カードに「生産終了」バッジが出て、
  現行品が売れなくなる(実際に21件中8件が誤フラグだった)。

使い方:
    python manage.py check_discontinued --in-articles          # 記事で使われている商品だけ(推奨)
    python manage.py check_discontinued --category dryer --json
    python manage.py check_discontinued --slug foo --slug bar

確認結果は Product.api_data["discontinued_check"] に残す(公式確認した際も必ず記録する)。
"""
import json
import re
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.products.models import Article, Product
from apps.products.services import rakuten_sync

THROTTLE = 1.0   # 楽天APIは1リクエスト/秒を目安にする


def _model_number(p):
    sp = p.specifications or {}
    mn = (sp.get("model_number") or "").strip()
    # 「EH-NA0J」「KHD-9940」等の型番らしい部分だけを取り出す(注記が付いている場合がある)
    m = re.search(r"[A-Za-z]{1,6}[-‐]?[A-Za-z0-9]{2,10}(?:[-‐][A-Za-z0-9]{1,6})?", mn)
    return m.group(0) if m else mn


def _articles_using():
    """公開記事の [product slug="..."] で使われている商品slug → 記事slugのリスト。"""
    use = {}
    for a in Article.objects.filter(is_published=True).only("slug", "content"):
        for s in set(re.findall(r'\[product slug="([^"]+)"\]', a.content or "")):
            use.setdefault(s, []).append(a.slug)
    return use


class Command(BaseCommand):
    help = "楽天APIで在庫を確認し、生産終了(終売)候補を検出する"

    def add_arguments(self, parser):
        parser.add_argument("--in-articles", action="store_true",
                            help="公開記事で紹介されている商品だけを対象にする")
        parser.add_argument("--category", action="append", default=None, help="カテゴリslugで絞る")
        parser.add_argument("--slug", action="append", default=None, help="商品slugを直接指定")
        parser.add_argument("--include-discontinued", action="store_true",
                            help="既に生産終了の商品も再確認する(復活の検出)")
        parser.add_argument("--apply", action="store_true",
                            help="(非推奨)在庫が確認できない商品を is_discontinued=True にする。"
                                 "楽天在庫は終売の証拠にならないため、公式確認を経ずに使わないこと")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **opts):
        if not rakuten_sync.is_enabled():
            self.stderr.write("楽天APIが未設定のため実行できません")
            return

        qs = Product.objects.filter(is_published=True)
        if not opts["include_discontinued"]:
            qs = qs.filter(is_discontinued=False)
        if opts["category"]:
            qs = qs.filter(product_type__slug__in=opts["category"])
        if opts["slug"]:
            qs = qs.filter(slug__in=opts["slug"])
        use = _articles_using()
        if opts["in_articles"]:
            qs = qs.filter(slug__in=list(use.keys()))
        products = list(qs.select_related("product_type").order_by("product_type__slug", "slug"))
        if opts["limit"]:
            products = products[:opts["limit"]]

        rows = []
        for i, p in enumerate(products, 1):
            found_by = None
            hit = None
            if p.rakuten_item_code:
                hit = rakuten_sync.get_by_code(p.rakuten_item_code)
                time.sleep(THROTTLE)
                if hit:
                    found_by = "item_code"
            if not hit:
                mn = _model_number(p)
                for kw in [k for k in (mn, p.name) if k]:
                    res = rakuten_sync.search_items(keyword=kw, hits=3)
                    time.sleep(THROTTLE)
                    if res:
                        hit = res[0]
                        found_by = "model_number" if kw == mn else "name"
                        break
            row = {
                "slug": p.slug, "name": p.name,
                "category": p.product_type.slug if p.product_type else None,
                "price": p.price, "model_number": _model_number(p),
                "already_discontinued": p.is_discontinued,
                "in_stock": bool(hit), "found_by": found_by,
                "hit_title": (hit or {}).get("title", "")[:60],
                "hit_price": (hit or {}).get("price"),
                "articles": use.get(p.slug, []),
            }
            rows.append(row)
            if not opts["json"]:
                mark = "在庫あり" if hit else "★終売候補"
                self.stdout.write(
                    f"[{i}/{len(products)}] {mark} {p.slug} ({row['category']}) "
                    f"{p.name[:30]} | 型番 {row['model_number']} | 判定元 {found_by or '-'} "
                    f"| 記事{len(row['articles'])}本")

        gone = [r for r in rows if not r["in_stock"] and not r["already_discontinued"]]
        back = [r for r in rows if r["in_stock"] and r["already_discontinued"]]

        if opts["apply"] and gone:
            self.stderr.write(
                "⚠ --apply は楽天在庫だけを根拠に生産終了へ変えます。"
                "実測では在庫が無い商品の多くが公式では現行でした。公式確認を済ませた場合のみ続行してください。")
            now = timezone.now()
            for r in gone:
                p = Product.objects.get(slug=r["slug"])
                data = p.api_data if isinstance(p.api_data, dict) else {}
                data["discontinued_check"] = {
                    "checked_at": now.isoformat(), "source": "rakuten_api",
                    "reason": "itemCode・型番・商品名のいずれでも在庫が確認できなかった",
                    "model_number": r["model_number"],
                }
                p.api_data = data
                p.is_discontinued = True
                p.discontinued_at = now
                p.save(update_fields=["is_discontinued", "discontinued_at", "api_data", "updated_at"])
            self.stdout.write(f"\n✅ {len(gone)}件を生産終了に更新しました")

        if opts["json"]:
            self.stdout.write(json.dumps({"rows": rows, "gone": gone, "back_in_stock": back},
                                         ensure_ascii=False))
            return

        self.stdout.write(f"\n==== 結果 ====")
        self.stdout.write(f"確認 {len(rows)}件 / 終売候補 {len(gone)}件 / 在庫復活(終売扱いだが在庫あり) {len(back)}件")
        if gone:
            self.stdout.write("\n## 終売候補(記事掲載数の多い順)")
            for r in sorted(gone, key=lambda r: -len(r["articles"])):
                arts = ", ".join(f"/{a}/" for a in r["articles"]) or "掲載なし"
                self.stdout.write(f"- {r['slug']} ({r['category']}) {r['name'][:36]} ¥{r['price']} → {arts}")
        if back:
            self.stdout.write("\n## 生産終了扱いだが在庫あり(要確認)")
            for r in back:
                self.stdout.write(f"- {r['slug']} {r['name'][:36]} | {r['found_by']} | {r['hit_title']}")
