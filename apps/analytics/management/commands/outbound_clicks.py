"""購入リンクのクリック記録を集計する（2026-09-14新設）。

  manage.py outbound_clicks                 # 直近7日（運営・ボット除外）
  manage.py outbound_clicks --days 28 --network rakuten
  manage.py outbound_clicks --rakuten-clicks 2026-09-15=60 2026-09-16=58
      # 楽天管理画面の日別クリック数を渡すと、記録件数との差（=JS非実行のクリック＝ボット等の目安）を並べる

記録は JavaScript が動いた「人のブラウザ」からのクリックだけ。楽天のクリック数より少なければ、
差分は JS を実行しないクローラー等が楽天リンクを直接踏んだものと考えられる。
"""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import OutboundClick


class Command(BaseCommand):
    help = "購入リンクのクリック記録を日別・ページ別・商品別・置き場所別に集計する"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--network", choices=["rakuten", "amazon", "other", "all"], default="all")
        parser.add_argument("--include-staff", action="store_true", help="運営自身のクリックも含める")
        parser.add_argument("--rakuten-clicks", nargs="*", default=[],
                            help="楽天管理画面の日別クリック数 YYYY-MM-DD=N")
        parser.add_argument("--top", type=int, default=15)

    def handle(self, *a, **o):
        since = timezone.now() - timedelta(days=o["days"])
        qs = OutboundClick.objects.filter(created_at__gte=since)
        if o["network"] != "all":
            qs = qs.filter(network=o["network"])
        staff = qs.filter(is_staff=True).count()
        bots = qs.filter(is_bot=True).count()
        if not o["include_staff"]:
            qs = qs.filter(is_staff=False)
        qs = qs.filter(is_bot=False)
        rows = list(qs.values_list("created_at", "network", "page", "product_slug",
                                   "section", "container", "link_text", "device", "ip_hash"))
        w = self.stdout.write
        w(f"# 購入リンクのクリック（直近{o['days']}日・{o['network']}）")
        w(f"対象 {len(rows)}件（除外: 運営{0 if o['include_staff'] else staff}件・ボットUA{bots}件）"
          f" / 押した人(IP) {len({r[8] for r in rows})}")
        if not rows:
            w("記録なし")
            return

        daily = Counter(timezone.localtime(r[0]).date().isoformat() for r in rows if r[1] == "rakuten")
        given = dict(s.split("=", 1) for s in o["rakuten_clicks"] if "=" in s)
        w("\n## 日別（楽天）")
        w("| 日付 | 記録(人のブラウザ) | 楽天管理画面 | 差(ボット等の目安) |")
        w("|---|---|---|---|")
        days = sorted(set(daily) | set(given))
        for d in days:
            g = given.get(d)
            diff = (int(g) - daily.get(d, 0)) if g and g.isdigit() else ""
            w(f"| {d} | {daily.get(d, 0)} | {g or '-'} | {diff} |")

        def table(title, key, label):
            c = Counter(key(r) for r in rows)
            w(f"\n## {title}")
            w(f"| {label} | クリック |")
            w("|---|---|")
            for k, n in c.most_common(o["top"]):
                w(f"| {k or '(不明)'} | {n} |")

        table("リンク先", lambda r: r[1], "リンク先")
        table("ページ別", lambda r: r[2], "ページ")
        table("商品別", lambda r: r[3], "商品slug")
        table("置き場所別", lambda r: r[5], "周囲のclass")
        table("見出し別", lambda r: f"{r[2]} › {r[4]}", "ページ › 直前の見出し")
        table("ボタン文言", lambda r: r[6], "文言")
        table("端末", lambda r: r[7], "端末")
