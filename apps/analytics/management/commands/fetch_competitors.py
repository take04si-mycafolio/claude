"""検索上位のライバル記事を自動取得して ContentGap に投入する。

メディアサイト方針・自動運用化(2026-09-06)に伴い、従来「人が管理画面にコピペ」
だった競合URL・競合本文を、ヘッドレスブラウザ(/opt/claude-ops/tools/browse.py)で
自動取得する。SERP は Yahoo!検索(Google のインデックス・順位を採用)を使う
(Google 本体はデータセンターIPを CAPTCHA でブロックするため)。

役割分担(更新後):
  - 競合URLの取得 = このコマンド(検索上位の実順位どおり)
  - 差分分析 = Claude Code (set_gap_analysis)
  - 採否 = Claude Code / 人 (増量の歯止め原則は維持)

使い方:
    python manage.py fetch_competitors --draft 189
    python manage.py fetch_competitors --all-in-review          # in_review全件
    python manage.py fetch_competitors --draft 189 --query "くるくるドライヤー おすすめ"
    python manage.py fetch_competitors --draft 189 --limit 4 --dry-run

注意: root で実行する(browse.py のブラウザが root 配下にあるため)。
"""
import re
import subprocess
import time
from urllib.parse import quote, urlparse

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models import ContentGap, RewriteDraft

BROWSE = "/opt/claude-ops/tools/browse.py"
SERP_URL = "https://search.yahoo.co.jp/search?p={q}"

# 競合「記事」として扱わないドメイン(EC本体・SNS・動画・自社)。
# 量販店のメディア記事(〜/media/等)は記事型競合なので除外しない。
EXCLUDE_DOMAINS = (
    "sc-tsusho.jp",
    "rakuten.co.jp", "amazon.co.jp", "amzn.", "yahoo.co.jp", "yimg.jp",
    "google.", "youtube.com", "x.com", "twitter.com", "instagram.com",
    "facebook.com", "tiktok.com", "pinterest.", "wikipedia.org",
    "apps.apple.com", "play.google.com", "chrome.google.com", "line.me",
)
BODY_MAX_CHARS = 12000   # 1競合あたり保存する本文の上限
FETCH_INTERVAL_SEC = 2   # 連続アクセスの間隔(節度)


def _run_browse(args, timeout=60):
    p = subprocess.run([BROWSE] + args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout


def _serp_urls(query, limit):
    """Yahoo!検索の上位URL(実順位どおり・除外ドメイン抜き)を返す。"""
    code, html = _run_browse(
        [SERP_URL.format(q=quote(query)), "--html", "--max-chars", "800000"])
    if code != 0:
        raise CommandError(f"SERP取得に失敗しました(query={query!r})")
    urls, seen = [], set()
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        # 強調スニペット由来の #:~:text= 等のフラグメントは取得失敗の原因になるため除去
        url = m.group(1).split("&amp;")[0].split("#")[0]
        host = urlparse(url).netloc.lower()
        if not host or any(d in host for d in EXCLUDE_DOMAINS):
            continue
        # 同一ドメインは1本まで(多様な競合を取る)
        key = host.removeprefix("www.")
        if key in seen:
            continue
        seen.add(key)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _fetch_body(url):
    """競合ページ本文をテキストで取得。article/main優先→body全体フォールバック。"""
    code, out = _run_browse([url, "--selector", "article, main",
                             "--max-chars", str(BODY_MAX_CHARS)], timeout=90)
    if code != 0 or len(out.strip()) < 500:
        code, out = _run_browse([url, "--max-chars", str(BODY_MAX_CHARS)], timeout=90)
    if code != 0:
        return ""
    out = out.strip()
    # 403ページ・実質空ページ(ヘッダのみ等)を「取得成功」として保存しない
    if len(out) < 400:
        return ""
    # browse.py のヘッダ2行(タイトル/status)は本文に含めたまま保存する(出典が分かる)
    return out


class Command(BaseCommand):
    help = "検索上位のライバル記事を自動取得して ContentGap に投入する"

    def add_arguments(self, parser):
        parser.add_argument("--draft", type=int, default=None, help="RewriteDraft id")
        parser.add_argument("--all-in-review", action="store_true",
                            help="status=in_review の全ドラフトに実行")
        parser.add_argument("--query", type=str, default=None, help="検索クエリの上書き")
        parser.add_argument("--limit", type=int, default=3, help="取得する競合数(既定3)")
        parser.add_argument("--force", action="store_true",
                            help="既に競合本文があるギャップも上書き")
        parser.add_argument("--dry-run", action="store_true",
                            help="SERPのURL一覧のみ表示(本文取得・保存なし)")

    def handle(self, *args, **opts):
        if opts["draft"]:
            drafts = list(RewriteDraft.objects.filter(id=opts["draft"]))
            if not drafts:
                raise CommandError(f"RewriteDraft(id={opts['draft']}) が見つかりません")
        elif opts["all_in_review"]:
            drafts = list(RewriteDraft.objects.filter(status="in_review")
                          .select_related("article").order_by("id"))
        else:
            raise CommandError("--draft か --all-in-review を指定してください")

        for d in drafts:
            gap, _ = ContentGap.objects.get_or_create(rewrite_draft=d)
            filled = {u: v for u, v in (gap.competitor_bodies or {}).items()
                      if (v or "").strip()}
            if filled and not opts["force"]:
                self.stdout.write(f"#{d.id} /{d.article.slug}/ 競合本文あり({len(filled)}件)→スキップ")
                continue

            query = (opts["query"] or gap.target_query or d.target_query
                     or (d.target_grow[0].get("query") if d.target_grow else ""))
            # growクエリが商品文脈を含まない汎用語(例:「どのボタンかわからない」)だと
            # 無関係なSERPを拾う(#196で実発生)。カテゴリ名が無ければ付与する。
            if not opts["query"] and query:
                cat = getattr(getattr(d.article, "product_type", None), "name", "")
                if cat and cat not in query:
                    query = f"{query} {cat}"
            if not query:
                self.stdout.write(self.style.WARNING(
                    f"#{d.id} /{d.article.slug}/ クエリ不明→スキップ"))
                continue

            urls = _serp_urls(query, opts["limit"])
            self.stdout.write(f"#{d.id} /{d.article.slug}/ query={query!r}")
            for u in urls:
                self.stdout.write(f"   - {u}")
            if opts["dry_run"]:
                continue

            bodies = {}
            for u in urls:
                time.sleep(FETCH_INTERVAL_SEC)
                text = _fetch_body(u)
                if text:
                    bodies[u] = text
                else:
                    self.stdout.write(self.style.WARNING(f"   取得失敗: {u}"))

            if not bodies:
                self.stdout.write(self.style.WARNING(f"#{d.id} 本文を1件も取得できず"))
                continue

            gap.target_query = query
            gap.competitor_urls = list(bodies.keys())
            gap.competitor_bodies = bodies
            if gap.status == "pending":
                gap.status = "urls_set"
            gap.save()
            total = sum(len(v) for v in bodies.values())
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ 競合{len(bodies)}本・計{total}字を保存(status={gap.status})"))
