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
    """常に HTTP 200 で JSON を標準出力に書く"""
    body = json.dumps(payload, ensure_ascii=False)
    sys.stdout.write("Content-Type: application/json; charset=utf-8\n\n")
    sys.stdout.write(body)
    sys.stdout.flush()


def _make_safe_wsgi(app):
    """
    WSGI ミドルウェア層で例外を捕捉し JSON 200 を返す。
    Flask のエラーハンドラより手前でも確実に動作する。
    """
    def _mw(environ, start_response):
        try:
            environ["SCRIPT_NAME"] = ""
            return app(environ, start_response)
        except Exception as exc:
            tb = traceback.format_exc()
            body = json.dumps(
                {"status": "error", "message": str(exc), "detail": tb},
                ensure_ascii=False
            ).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ])
            return [body]
    return _mw


try:
    from wsgiref.handlers import CGIHandler
    from flask import jsonify as _jsonify
    from app import create_app

    flask_app = create_app()

    # Flask レベルのエラーハンドラ (念のため)
    @flask_app.errorhandler(Exception)
    def _handle_exc(e):
        return _jsonify({"status": "error", "message": "Flaskエラー: " + str(e)})

    @flask_app.errorhandler(500)
    def _handle_500(e):
        return _jsonify({"status": "error", "message": "Internal error: " + str(e)})

    @flask_app.errorhandler(404)
    def _handle_404(e):
        return _jsonify({"status": "error", "message": "Not found: " + str(e)})

    if __name__ == "__main__":
        CGIHandler().run(_make_safe_wsgi(flask_app))

except Exception as exc:
    _json200({
        "status": "error",
        "message": "CGI起動エラー: " + str(exc),
        "detail": traceback.format_exc(),
    })
