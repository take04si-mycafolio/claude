#!/home/xs539690/forex_env/bin/python3
# -*- coding: utf-8 -*-
"""
管理パネル CGI エントリーポイント (Xserver 共有サーバー用)

アクセスURL: /admin/login, /admin/, /admin/backtest-tool

.htaccess の設定:
  Options +ExecCGI
  AddHandler cgi-script .cgi
  RewriteEngine On
  RewriteRule ^admin(/.*)?$ /admin.cgi/admin$1 [QSA,PT,L]
"""

import sys
import os

# ---- プロジェクトパスを設定 ----
HOME = os.path.expanduser("~")
PROJECT_ROOT = os.path.join(HOME, "forex_project", "forex_signal_tool")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# ---- Flask を CGI として起動 ----
from wsgiref.handlers import CGIHandler
from app import create_app

flask_app = create_app()


def _fix_script_name(app):
    """SCRIPT_NAME を空にして url_for() がクリーンURLを生成するようにする"""
    def _middleware(environ, start_response):
        environ["SCRIPT_NAME"] = ""
        return app(environ, start_response)
    return _middleware


if __name__ == "__main__":
    CGIHandler().run(_fix_script_name(flask_app))
