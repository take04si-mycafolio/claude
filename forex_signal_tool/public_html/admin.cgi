#!/home/xs539690/forex_env/bin/python3
# -*- coding: utf-8 -*-
"""
管理パネル CGI エントリーポイント (Xserver 共有サーバー用)
"""

import sys
import os
import json
import traceback

# ---- プロジェクトパスを設定 ----
HOME = os.path.expanduser("~")
PROJECT_ROOT = os.path.join(HOME, "forex_project", "forex_signal_tool")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def _is_json_request():
    ct = os.environ.get("CONTENT_TYPE", "")
    xrw = os.environ.get("HTTP_X_REQUESTED_WITH", "")
    return "application/json" in ct or xrw == "XMLHttpRequest"


def _json_error(status, message, tb=""):
    body = json.dumps({"status": "error", "message": message,
                       "detail": tb}, ensure_ascii=False)
    sys.stdout.write(
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Status: {status}\r\n"
        f"\r\n"
        f"{body}"
    )
    sys.stdout.flush()


try:
    from wsgiref.handlers import CGIHandler
    from app import create_app

    flask_app = create_app()

    # API / AJAX リクエストで Flask 例外が HTML にならないようにする
    from flask import request as flask_request, jsonify

    @flask_app.errorhandler(Exception)
    def handle_any_exception(e):
        if flask_request.content_type == "application/json" or \
                flask_request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": str(e)}), 500
        raise e

    @flask_app.errorhandler(404)
    def handle_404(e):
        if flask_request.content_type == "application/json" or \
                flask_request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "エンドポイントが見つかりません"}), 404
        return str(e), 404

    def _fix_script_name(app):
        """SCRIPT_NAME を空にして url_for() がクリーンURLを生成するようにする"""
        def _middleware(environ, start_response):
            environ["SCRIPT_NAME"] = ""
            return app(environ, start_response)
        return _middleware

    if __name__ == "__main__":
        CGIHandler().run(_fix_script_name(flask_app))

except Exception as exc:
    # Flask 起動失敗を JSON で返す（HTML エラーページの代わりに）
    tb = traceback.format_exc()
    _json_error("500 Internal Server Error", str(exc), tb)
