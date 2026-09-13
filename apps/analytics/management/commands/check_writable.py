"""管理画面（gunicorn=deploy:www-data）が書き込む場所の権限を点検する。

root 実行の cron が作ったファイル/ディレクトリが root 所有のままだと、
管理画面からの差し戻し・承認反映が「書き込めません」で止まる（実際に2回発生）。
os.access は実行ユーザー基準で当てにならないので、gunicorn の uid/gid で判定する。

使い方:
    manage.py check_writable          # 点検（NGがあれば終了コード1）
    manage.py check_writable --fix-hint  # 直すコマンドも表示
"""
import grp
import os
import pwd
import stat
from pathlib import Path

from django.core.management.base import BaseCommand

# 管理画面が書き込む場所（増えたらここに足す）
PATHS = [
    ("/opt/claude-ops/backups", "商品記事v2の反映前バックアップ"),
    ("/home/deploy/app/backups", "記事リライトの反映前バックアップ"),
    ("/opt/claude-ops/agents/product_v2_queue", "商品記事v2の承認キュー(差し戻しで書き換え)"),
    ("/opt/claude-ops/agents/triggers", "差し戻し・リサーチ依頼のトリガー"),
    ("/opt/claude-ops/agents/research_requests", "リサーチ依頼キュー"),
    ("/home/deploy/app/media/agents", "AI社員アバターのアップロード先"),
    ("/home/deploy/app/media/article-images", "記事画像のアップロード先"),
]
RUN_USER, RUN_GROUP = "deploy", "www-data"


def can_write(path, uid, gids):
    st = os.stat(path)
    if st.st_uid == uid:
        return bool(st.st_mode & stat.S_IWUSR)
    if st.st_gid in gids:
        return bool(st.st_mode & stat.S_IWGRP)
    return bool(st.st_mode & stat.S_IWOTH)


class Command(BaseCommand):
    help = "管理画面が書き込む場所の権限を点検する"

    def add_arguments(self, parser):
        parser.add_argument("--fix-hint", action="store_true")

    def handle(self, *a, **o):
        uid = pwd.getpwnam(RUN_USER).pw_uid
        gids = {g.gr_gid for g in grp.getgrall() if RUN_USER in g.gr_mem}
        gids.add(grp.getgrnam(RUN_GROUP).gr_gid)
        gids.add(pwd.getpwnam(RUN_USER).pw_gid)

        ng = []
        for path, note in PATHS:
            p = Path(path)
            if not p.exists():
                self.stdout.write(f"—  {path}（未作成・{note}）")
                continue
            st = os.stat(path)
            owner = f"{pwd.getpwuid(st.st_uid).pw_name}:{grp.getgrgid(st.st_gid).gr_name}"
            ok = can_write(path, uid, gids)
            mark = self.style.SUCCESS("OK") if ok else self.style.ERROR("NG")
            self.stdout.write(f"{mark} {path}  {owner} {oct(st.st_mode)[-4:]}  … {note}")
            if not ok:
                ng.append(path)
                # 中のファイルも見る（ディレクトリが書けてもファイル上書きは所有者依存）
                for f in list(p.glob("*"))[:50]:
                    if f.is_file() and not can_write(f, uid, gids):
                        self.stdout.write(f"     └ 書けないファイル: {f.name}")
        if ng:
            self.stdout.write(self.style.ERROR(f"\n書き込めない場所が {len(ng)}件 あります"))
            if o["fix_hint"]:
                for path in ng:
                    self.stdout.write(f"  chgrp -R {RUN_GROUP} {path} && chmod -R g+w {path} "
                                      f"&& chmod g+s {path}")
            return
        self.stdout.write(self.style.SUCCESS("\n管理画面が書き込む場所はすべて書き込み可能です"))
