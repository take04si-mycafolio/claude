"""
WordPress XML(WXR) から口コミを Review モデルに取り込む。

使い方:
  python manage.py import_wp_reviews /path/to/wpdata.xml
  python manage.py import_wp_reviews /path/to/wpdata.xml --dry-run
"""
from collections import defaultdict
from datetime import datetime, timezone as dt_tz
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import AgeRange, Gender, SkinType, User
from apps.products.models import Product
from apps.reviews.models import Review

WP = "{http://wordpress.org/export/1.2/}"

SKIN_MAP = {
    "乾燥肌": SkinType.DRY,
    "脂性肌": SkinType.OILY,
    "混合肌": SkinType.COMBINATION,
    "敏感肌": SkinType.SENSITIVE,
    "普通肌": SkinType.NORMAL,
}
AGE_MAP = {
    "10代": AgeRange.TEENS,
    "20代": AgeRange.TWENTIES,
    "30代": AgeRange.THIRTIES,
    "40代": AgeRange.FORTIES,
    "50代": AgeRange.FIFTIES,
    "60代以上": AgeRange.SIXTIES_PLUS,
}
SEX_MAP = {
    "女性": Gender.FEMALE,
    "男性": Gender.MALE,
}
SKIN_SHORT = {
    SkinType.DRY: "dry", SkinType.OILY: "oily",
    SkinType.COMBINATION: "comb", SkinType.SENSITIVE: "sens",
    SkinType.NORMAL: "norm",
}
AGE_SHORT = {
    AgeRange.TEENS: "10", AgeRange.TWENTIES: "20", AgeRange.THIRTIES: "30",
    AgeRange.FORTIES: "40", AgeRange.FIFTIES: "50", AgeRange.SIXTIES_PLUS: "60",
}
SEX_SHORT = {Gender.FEMALE: "F", Gender.MALE: "M", Gender.OTHER: "O"}


def to_int_in_range(s, lo=1, hi=5):
    try:
        v = int((s or "").strip())
        return v if lo <= v <= hi else None
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = "Import reviews from a WordPress XML (WXR) export file."

    def add_arguments(self, parser):
        parser.add_argument("xml_path", help="WordPress export XML path")
        parser.add_argument("--dry-run", action="store_true",
                            help="ロールバックして終了する")

    def handle(self, *args, xml_path, dry_run, **opts):
        wp_reviews = self._parse_xml(xml_path)
        self.stdout.write(f"XMLから抽出した承認済みコメント: {len(wp_reviews)} 件")

        with transaction.atomic():
            user_pool = self._ensure_users(wp_reviews)
            self.stdout.write(
                f"用意したインポート用ユーザー: {sum(len(v) for v in user_pool.values())} 件"
            )
            stats = self._import_reviews(wp_reviews, user_pool)
            self._print_stats(stats)
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(
                    "\n*** DRY RUN: 全変更をロールバックしました ***"
                ))

    def _parse_xml(self, path):
        tree = ET.parse(path)
        channel = tree.getroot().find("channel")
        results = []
        for item in channel.findall("item"):
            pt = item.findtext(f"{WP}post_type")
            if pt != "biganki1":
                continue
            try:
                wp_post_id = int(item.findtext(f"{WP}post_id") or "0")
            except ValueError:
                continue
            for cm in item.findall(f"{WP}comment"):
                approved = cm.findtext(f"{WP}comment_approved") or "0"
                if approved != "1":
                    continue
                try:
                    cid = int(cm.findtext(f"{WP}comment_id") or "0")
                except ValueError:
                    continue
                meta = {}
                for cmeta in cm.findall(f"{WP}commentmeta"):
                    k = cmeta.findtext(f"{WP}meta_key") or ""
                    v = cmeta.findtext(f"{WP}meta_value") or ""
                    if k:
                        meta[k] = v
                date_gmt = cm.findtext(f"{WP}comment_date_gmt") or ""
                created = None
                if date_gmt:
                    try:
                        created = datetime.strptime(
                            date_gmt, "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=dt_tz.utc)
                    except ValueError:
                        created = None
                results.append({
                    "wp_post_id": wp_post_id,
                    "comment_id": cid,
                    "body": (cm.findtext(f"{WP}comment_content") or "").strip(),
                    "created": created,
                    "meta": meta,
                })
        return results

    def _ensure_users(self, wp_reviews):
        per_demo_per_pid = defaultdict(lambda: defaultdict(int))
        for r in wp_reviews:
            skin = SKIN_MAP.get(r["meta"].get("skin", ""))
            age = AGE_MAP.get(r["meta"].get("age", ""))
            gender = SEX_MAP.get(r["meta"].get("sex", ""))
            if skin and age and gender:
                per_demo_per_pid[(skin, age, gender)][r["wp_post_id"]] += 1

        pool = {}
        for (skin, age, gender), pidmap in per_demo_per_pid.items():
            n = max(pidmap.values())
            users = []
            for idx in range(1, n + 1):
                username = (
                    f"wp_{SKIN_SHORT[skin]}_{AGE_SHORT[age]}_{SEX_SHORT[gender]}_{idx}"
                )
                email = f"{username}@wp-imported.local"
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "nickname": f"{skin.label}・{age.label}の{gender.label} #{idx}",
                        "age_range": age,
                        "skin_type": skin,
                        "gender": gender,
                        "is_active": False,
                        "email_verified": False,
                    },
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                else:
                    changed = False
                    for f, v in [
                        ("nickname", f"{skin.label}・{age.label}の{gender.label} #{idx}"),
                        ("age_range", age), ("skin_type", skin), ("gender", gender),
                    ]:
                        if getattr(user, f) != v:
                            setattr(user, f, v); changed = True
                    if changed:
                        user.save()
                users.append(user)
            pool[(skin, age, gender)] = users
        return pool

    def _import_reviews(self, wp_reviews, user_pool):
        product_by_wpid = {
            p.wp_post_id: p for p in Product.objects.all() if p.wp_post_id
        }
        next_idx = defaultdict(lambda: defaultdict(int))
        stats = {"created": 0, "updated": 0, "skip_already": 0,
                 "skip_no_product": 0, "skip_missing": 0}
        for r in wp_reviews:
            existing = Review.objects.filter(wp_comment_id=r["comment_id"]).first()
            if existing:
                stats["skip_already"] += 1
                continue
            product = product_by_wpid.get(r["wp_post_id"])
            if not product:
                stats["skip_no_product"] += 1
                continue
            skin = SKIN_MAP.get(r["meta"].get("skin", ""))
            age = AGE_MAP.get(r["meta"].get("age", ""))
            gender = SEX_MAP.get(r["meta"].get("sex", ""))
            rating = to_int_in_range(r["meta"].get("total"), 1, 5)
            title = (r["meta"].get("title") or "").strip()
            body = r["body"]
            if not (skin and age and gender and rating and title and body):
                stats["skip_missing"] += 1
                continue
            users = user_pool.get((skin, age, gender), [])
            if not users:
                stats["skip_missing"] += 1
                continue
            idx = next_idx[(skin, age, gender)][r["wp_post_id"]]
            user = users[idx % len(users)]
            next_idx[(skin, age, gender)][r["wp_post_id"]] += 1

            review = Review.objects.create(
                product=product, user=user,
                rating=rating, title=title[:120], body=body,
                skin_type=skin,
                cospa=to_int_in_range(r["meta"].get("cospa")),
                control=to_int_in_range(r["meta"].get("control")),
                safety=to_int_in_range(r["meta"].get("anzen")),
                expression=to_int_in_range(r["meta"].get("menber")),
                icon=to_int_in_range(r["meta"].get("icon"), 1, 10),
                wp_comment_id=r["comment_id"], is_approved=True,
            )
            if r["created"]:
                Review.objects.filter(pk=review.pk).update(created_at=r["created"])
            stats["created"] += 1
        return stats

    def _print_stats(self, stats):
        self.stdout.write(self.style.SUCCESS("\n=== 取り込み結果 ==="))
        self.stdout.write(f"  新規作成 : {stats['created']} 件")
        self.stdout.write(f"  既存スキップ(冪等): {stats['skip_already']} 件")
        self.stdout.write(f"  対応商品なしスキップ: {stats['skip_no_product']} 件")
        self.stdout.write(f"  必須項目欠如スキップ: {stats['skip_missing']} 件")
