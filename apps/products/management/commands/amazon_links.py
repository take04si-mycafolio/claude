"""Amazonアソシエイトリンクの整備（PA-API 不使用）。

PA-API を使わず、アソシエイトタグ（ApiCredential.amazon_partner_tag）を付けた
リンクを組み立てて Product.asin / amazon_url を埋める。3モード:

1) --resolve-short
   既存の amzn.to 短縮リンク(SiteStripe由来)をリダイレクト解決して ASIN を抽出し、
   asin フィールドへバックフィルする。amazon_url は書き換えない（動いているリンクに触らない）。

2) --from-csv path.csv
   「slug,asin」または「slug,AmazonのURL」のCSVを読み、
   amazon_url = https://www.amazon.co.jp/dp/{ASIN}?tag={tag} を設定する。
   既に amazon_url がある商品は --overwrite を付けない限りスキップ。

3) --search-links --category <slug>
   amazon_url が空の商品に、商品名でのAmazon検索結果リンク
   https://www.amazon.co.jp/s?k={商品名}&tag={tag} を設定する。
   直リンク(ASIN)が用意でき次第 --from-csv で上書きする前提のつなぎ。
   検索リンクは URL に /s?k= を含むため後から機械的に判別できる。

Amazonページのスクレイピングは規約違反のため行わない（短縮URLのリダイレクト解決のみ）。
"""
import csv
import re
import time
from urllib.parse import quote_plus

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.products.models import ApiCredential, Product

ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
UA = "Mozilla/5.0 (compatible; sc-tsusho-linkcheck/1.0)"


def _get_tag():
    cred = ApiCredential.objects.first()
    tag = (cred.amazon_partner_tag or "").strip() if cred else ""
    if not tag:
        raise CommandError("ApiCredential.amazon_partner_tag が未設定です")
    return tag


def _dp_url(asin, tag):
    return f"https://www.amazon.co.jp/dp/{asin}?tag={tag}"


def _extract_asin(text):
    m = ASIN_RE.search(text or "")
    return m.group(1) if m else None


class Command(BaseCommand):
    help = "AmazonアソシエイトリンクをAPI無しで整備する（asinバックフィル/CSV取込/検索リンク）"

    def add_arguments(self, parser):
        parser.add_argument("--resolve-short", action="store_true",
                            help="amzn.to を解決して asin をバックフィル")
        parser.add_argument("--from-csv", metavar="PATH",
                            help="slug,asin(またはURL) のCSVから直リンクを設定")
        parser.add_argument("--search-links", action="store_true",
                            help="amazon_url 空の商品へ検索結果リンクを設定")
        parser.add_argument("--category", help="search-links の対象カテゴリslug（必須）")
        parser.add_argument("--overwrite", action="store_true",
                            help="from-csv: 既存 amazon_url も上書き（検索リンク→直リンク置換に使う）")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        if o["resolve_short"]:
            self.resolve_short(o)
        elif o["from_csv"]:
            self.from_csv(o)
        elif o["search_links"]:
            self.search_links(o)
        else:
            raise CommandError("--resolve-short / --from-csv / --search-links のいずれかを指定")

    # ── 1) amzn.to → asin バックフィル ──
    def resolve_short(self, o):
        qs = (Product.objects.filter(amazon_url__contains="amzn.to")
              .filter(asin__isnull=True) | Product.objects.filter(
                  amazon_url__contains="amzn.to", asin=""))
        qs = qs.distinct().order_by("id")
        if o["limit"]:
            qs = qs[:o["limit"]]
        ok = ng = 0
        for p in qs:
            asin = None
            try:
                # 短縮URLのLocationヘッダだけ読む（Amazon本体は取得しない）
                r = requests.head(p.amazon_url, allow_redirects=False,
                                  timeout=10, headers={"User-Agent": UA})
                loc = r.headers.get("Location", "")
                asin = _extract_asin(loc)
            except requests.RequestException as e:
                self.stdout.write(f"  NG {p.slug}: {e.__class__.__name__}")
            if asin:
                ok += 1
                if not o["dry_run"]:
                    p.asin = asin
                    p.save(update_fields=["asin"])
                self.stdout.write(f"  OK {p.slug}: {asin}")
            else:
                ng += 1
            time.sleep(0.3)
        self.stdout.write(self.style.SUCCESS(
            f"resolve-short 完了: asin取得 {ok} / 失敗 {ng}{'（dry-run）' if o['dry_run'] else ''}"))

    # ── 2) CSV から直リンク設定 ──
    def from_csv(self, o):
        tag = _get_tag()
        done = skip = bad = 0
        with open(o["from_csv"], newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row or row[0].startswith("#"):
                    continue
                slug, val = row[0].strip(), (row[1].strip() if len(row) > 1 else "")
                asin = val if re.fullmatch(r"[A-Z0-9]{10}", val) else _extract_asin(val)
                p = Product.objects.filter(slug=slug).first()
                if not p or not asin:
                    bad += 1
                    self.stdout.write(f"  不正行: {row}")
                    continue
                is_search = "/s?k=" in (p.amazon_url or "")
                if p.amazon_url and not o["overwrite"] and not is_search:
                    skip += 1
                    continue
                done += 1
                if not o["dry_run"]:
                    p.asin = asin
                    p.amazon_url = _dp_url(asin, tag)
                    p.save(update_fields=["asin", "amazon_url"])
                self.stdout.write(f"  SET {slug}: {_dp_url(asin, tag)}")
        self.stdout.write(self.style.SUCCESS(
            f"from-csv 完了: 設定 {done} / スキップ {skip} / 不正 {bad}"
            f"{'（dry-run）' if o['dry_run'] else ''}"))

    # ── 3) 検索結果リンク（つなぎ） ──
    def search_links(self, o):
        if not o["category"]:
            raise CommandError("--search-links には --category が必要です")
        tag = _get_tag()
        qs = (Product.objects.filter(is_published=True, amazon_url="")
              .filter(categories__slug=o["category"]).distinct().order_by("id"))
        if o["limit"]:
            qs = qs[:o["limit"]]
        n = 0
        for p in qs:
            kw = f"{p.brand} {p.name}" if p.brand and p.brand not in p.name else p.name
            url = f"https://www.amazon.co.jp/s?k={quote_plus(kw)}&tag={tag}"
            n += 1
            if not o["dry_run"]:
                p.amazon_url = url
                p.save(update_fields=["amazon_url"])
            self.stdout.write(f"  SET {p.slug}: {url[:110]}")
        self.stdout.write(self.style.SUCCESS(
            f"search-links 完了: {n}件（category={o['category']}）"
            f"{'（dry-run）' if o['dry_run'] else ''}"))
