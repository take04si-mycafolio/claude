"""
下書きファイルから記事本文・meta_descriptionを本番DBに反映する管理コマンド。
反映前に自動でJSONバックアップを取り、復旧はrollback_draft.pyで可能。

使い方:
    python manage.py apply_draft --slug=kousyuha              # 単一記事を本番反映
    python manage.py apply_draft --all                        # drafts配下の全記事を一括反映
    python manage.py apply_draft --all --dry-run              # 一括対象の確認のみ
    python manage.py apply_draft --slug=kousyuha --dry-run    # 差分プレビューのみ
    python manage.py apply_draft --slug=kousyuha --content-only  # 本文のみ反映
    python manage.py apply_draft --slug=kousyuha --meta-only     # metaのみ反映
    python manage.py apply_draft --all --no-notify            # 一括反映・検索エンジン通知なし
    python manage.py apply_draft --slug=foo --publish         # 反映と同時に is_published=True（Phase 6）
    python manage.py apply_draft --all --publish              # 一括反映＋一括公開（Phase 6）

下書きファイル配置:
    /opt/claude-ops/drafts/{slug}_revised.html        # 本文
    /opt/claude-ops/drafts/{slug}_meta_revised.txt    # meta_description

バックアップ:
    /opt/claude-ops/backups/{slug}_{YYYYmmdd_HHMMSS}.json
"""

import json
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Article


DRAFTS_DIR = Path("/opt/claude-ops/drafts")
BACKUPS_DIR = Path("/opt/claude-ops/backups")


class Command(BaseCommand):
    help = "下書きファイルからArticleの本文/metaを本番DBへ反映（自動バックアップあり）"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, default=None, help="対象記事のslug（単一反映）")
        parser.add_argument(
            "--all", action="store_true",
            help="drafts配下の全 *_revised.html を一括反映",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="DB書き込みせず差分・対象のみ表示"
        )
        parser.add_argument(
            "--content-only", action="store_true", help="本文(content)のみ反映"
        )
        parser.add_argument(
            "--meta-only", action="store_true", help="meta_descriptionのみ反映"
        )
        parser.add_argument(
            "--no-notify", action="store_true",
            help="反映後の検索エンジン通知(notify_google/notify_indexnow)をスキップ",
        )
        parser.add_argument(
            "--publish", action="store_true",
            help="反映と同時に is_published=True をセット（Phase 6: 非公開記事の公開用）",
        )

    def handle(self, *args, **opts):
        slug = opts["slug"]
        do_all = opts["all"]
        dry = opts["dry_run"]
        content_only = opts["content_only"]
        meta_only = opts["meta_only"]
        publish = opts["publish"]

        if content_only and meta_only:
            raise CommandError("--content-only と --meta-only は同時指定できません")
        if bool(slug) == bool(do_all):
            raise CommandError("--slug と --all はどちらか一方を指定してください")

        apply_content = not meta_only
        apply_meta = not content_only

        # --- 対象slug一覧の決定 ----------------------------------------------
        if do_all:
            slugs = sorted(
                p.name[: -len("_revised.html")]
                for p in DRAFTS_DIR.glob("*_revised.html")
            )
            if not slugs:
                raise CommandError(f"対象がありません: {DRAFTS_DIR}/*_revised.html")
            self.stdout.write(self.style.SUCCESS(f"=== 一括反映対象: {len(slugs)}件 ==="))
            for s in slugs:
                self.stdout.write(f"  - {s}")
            self.stdout.write("")
        else:
            slugs = [slug]

        # 単一slugは厳格（下書き・記事が無ければエラー）。--allは止めずスキップ。
        strict = not do_all

        applied_urls = []      # 実際に反映できた記事URL（通知対象）
        applied = 0            # 反映成功件数（本番）
        previewed = 0          # プレビュー件数（dry-run）
        skipped = []           # (slug, 理由)

        for s in slugs:
            try:
                status, url, reason = self._apply_one(
                    s, apply_content, apply_meta, dry, strict, publish
                )
            except Exception as e:  # noqa: BLE001
                # --all時の想定外エラーは1記事スキップで続行
                if strict:
                    raise
                status, url, reason = "skipped", None, f"{type(e).__name__}: {e}"

            if status == "applied":
                applied += 1
                if url:
                    applied_urls.append(url)
            elif status == "previewed":
                previewed += 1
                if url:
                    applied_urls.append(url)  # dry時は通知しないが対象把握用
            else:
                skipped.append((s, reason))

        # --- 反映後の検索エンジン通知（全記事まとめて1回）--------------------
        # Google: sitemap全体の再送信なので記事数によらず1回でよい。
        # IndexNow: 反映した全URLを1リクエストにまとめて送る。
        # 通知失敗はDB反映を巻き戻さず警告のみ（既存方針を踏襲）。
        notify_result = "（dry-runのため通知なし）" if dry else None
        if not dry:
            if opts.get("no_notify"):
                notify_result = "（--no-notify指定のためスキップ）"
                self.stdout.write("\n（--no-notify指定のため検索エンジン通知はスキップ）")
            elif not applied_urls:
                notify_result = "（反映成功記事が無いため通知なし）"
            else:
                notify_result = self._notify(applied_urls)

        # --- 完了サマリ -------------------------------------------------------
        if do_all:
            self.stdout.write(self.style.SUCCESS("\n=== 一括反映 完了サマリ ==="))
            self.stdout.write(f"対象             : {len(slugs)}件")
            if dry:
                self.stdout.write(f"プレビュー成功   : {previewed}件")
            else:
                self.stdout.write(f"反映成功         : {applied}件")
            self.stdout.write(f"失敗・スキップ   : {len(skipped)}件")
            for s, reason in skipped:
                self.stdout.write(f"    - {s}: {reason}")
            self.stdout.write(f"通知結果         : {notify_result}")

    # -------------------------------------------------------------------------
    # 1記事の反映（プレビュー＋バックアップ＋DB保存）。通知は行わない。
    # 戻り値: (status, url, reason)
    #   status: "applied"（反映済）/ "previewed"（dry）/ "skipped"（対象外）
    # -------------------------------------------------------------------------
    def _apply_one(self, slug, apply_content, apply_meta, dry, strict, publish=False):
        content_path = DRAFTS_DIR / f"{slug}_revised.html"
        meta_path = DRAFTS_DIR / f"{slug}_meta_revised.txt"

        new_content = None
        new_meta = None
        if apply_content:
            if not content_path.exists():
                if strict:
                    raise CommandError(f"下書き本文が見つかりません: {content_path}")
                return "skipped", None, "下書き本文なし"
            new_content = content_path.read_text(encoding="utf-8")
        if apply_meta:
            if not meta_path.exists():
                if strict:
                    raise CommandError(f"下書きmetaが見つかりません: {meta_path}")
                return "skipped", None, "下書きmetaなし"
            new_meta = meta_path.read_text(encoding="utf-8")

        try:
            article = Article.objects.get(slug=slug)
        except Article.DoesNotExist:
            if strict:
                raise CommandError(f"Article(slug={slug!r}) が見つかりません")
            return "skipped", None, "Article未存在"

        url = f"https://sc-tsusho.jp/{slug}/"
        old_content_len = len(article.content or "")
        old_meta_len = len(article.meta_description or "")

        self.stdout.write(self.style.SUCCESS(f"--- 反映プレビュー: {slug} ---"))
        self.stdout.write(f"記事    : {article.title}")
        self.stdout.write(f"id      : {article.id} / published: {article.is_published}")
        if apply_content:
            ratio = len(new_content) / old_content_len * 100 if old_content_len else 0
            self.stdout.write(
                f"content : {old_content_len}字 → {len(new_content)}字 ({ratio:.1f}%)"
            )
        else:
            self.stdout.write("content : (変更なし / --meta-only指定)")
        if apply_meta:
            self.stdout.write(f"meta    : {old_meta_len}字 → {len(new_meta)}字")
        else:
            self.stdout.write("meta    : (変更なし / --content-only指定)")
        if publish:
            if article.is_published:
                self.stdout.write(
                    f"公開状態: {article.is_published} （既に公開済み / --publishは冪等）"
                )
            else:
                self.stdout.write(
                    f"公開状態: {article.is_published} → True に変更予定（--publish指定）"
                )
        else:
            self.stdout.write("公開状態: (変更なし / --publish未指定)")

        if dry:
            self.stdout.write("  → [dry-run] DB書き込みはスキップ")
            return "previewed", url, ""

        # 反映前バックアップ
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUPS_DIR / f"{slug}_{ts}.json"
        backup_data = {
            "slug": article.slug,
            "id": article.id,
            "title": article.title,
            "content": article.content,
            "meta_description": article.meta_description,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
            "backed_up_at": datetime.now().isoformat(),
            "applied_fields": [
                f for f, on in [("content", apply_content), ("meta_description", apply_meta)] if on
            ],
        }
        backup_path.write_text(
            json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.stdout.write(f"💾 バックアップ: {backup_path}")

        # 反映
        update_fields = []
        if apply_content:
            article.content = new_content
            update_fields.append("content")
        if apply_meta:
            article.meta_description = new_meta
            update_fields.append("meta_description")
        if publish:
            article.is_published = True
            update_fields.append("is_published")
        update_fields.append("updated_at")
        article.save(update_fields=update_fields)
        article.refresh_from_db()

        self.stdout.write(self.style.SUCCESS(f"✅ DB反映完了: {slug}（ロールバック: rollback_draft.py --slug={slug}）"))
        return "applied", url, ""

    # -------------------------------------------------------------------------
    # 検索エンジン通知（Google sitemap再送信 + IndexNow一括）。戻り値は結果文字列。
    # -------------------------------------------------------------------------
    def _notify(self, urls):
        google_ok = False
        indexnow_ok = False

        # (1) Google: sitemap再送信（記事数によらず1回）
        self.stdout.write("\nGoogleへsitemap再送信を通知します ...")
        try:
            call_command("notify_google")
            google_ok = True
        except Exception as e:  # noqa: BLE001
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Google通知に失敗（DB反映は完了済み）: {e}\n"
                    "  後で `python manage.py notify_google` を再実行できます。"
                )
            )

        # (2) Bing/Yandex等: IndexNowで全URLをまとめて通知
        self.stdout.write(f"IndexNowへURL通知します（{len(urls)}件）...")
        try:
            call_command("notify_indexnow", url=urls)
            indexnow_ok = True
        except Exception as e:  # noqa: BLE001
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ IndexNow通知に失敗（DB反映は完了済み）: {e}\n"
                    "  後で `python manage.py notify_indexnow --url=...` を再実行できます。"
                )
            )

        g = "成功" if google_ok else "失敗"
        i = "成功" if indexnow_ok else "失敗"
        return f"Google={g} / IndexNow={i}（{len(urls)}URL）"
