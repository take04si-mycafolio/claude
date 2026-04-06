#!/usr/bin/env python3
"""
ローカル開発用サーバー起動スクリプト
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
