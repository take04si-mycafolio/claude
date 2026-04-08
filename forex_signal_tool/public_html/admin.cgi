#!/home/xs539690/forex_env/bin/python3
# -*- coding: utf-8 -*-
"""
管理パネル CGI エントリーポイント (Xserver 共有サーバー用)

Xserver は CGI の 4xx/5xx を HTML エラーページに差し替えるため、
エラー時も HTTP 200 で JSON を返す。
"""

import sys
import os
import json
import traceback

HOME = os.path.expanduser("~")
PROJECT_ROOT = os.path.join(HOME, "forex_project", "forex_signal_tool")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def _json200(payload):
    """常に HTTP 200 で JSON を出力する (Xserver エラーページ回避)"""
    body = json.dumps(payload, ensure_ascii=False)
    sys.stdout.write("Content-Type: application/json; charset=utf-8\n")
    sys.stdout.write("Status: 200 OK\n")
    sys.stdout.write("\n")
    sys.stdout.write(body)
    sys.stdout.flush()


try:
    from wsgiref.handlers import CGIHandler
    from app import create_app

    flask_app = create_app()

    # 未補足の例外はすべて HTTP 200 JSON で返す（Xserver が 500 HTML に差し替えないように）
    from flask import request as _req, jsonify as _jsonify

    @flask_app.errorhandler(Exception)
    def _handle_exc(e):
        logger.exception("unhandled flask error")
        return _jsonify({"status": "error", "message": "予期せぬエラー: " + str(e)})

    @flask_app.errorhandler(404)
    def _handle_404(e):
        return _jsonify({"status": "error", "message": "エンドポイントが見つかりません: " + str(e)})

    def _fix_script_name(app):
        def _mw(environ, start_response):
            environ["SCRIPT_NAME"] = ""
            return app(environ, start_response)
        return _mw

    if __name__ == "__main__":
        CGIHandler().run(_fix_script_name(flask_app))

except Exception as exc:
    _json200({
        "status": "error",
        "message": "サーバー起動エラー: " + str(exc),
        "detail": traceback.format_exc(),
    })
