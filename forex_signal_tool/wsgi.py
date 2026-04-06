"""
Xサーバー用 WSGI エントリーポイント

Xサーバーでの設定例 (.htaccess):
  Options +ExecCGI
  AddHandler wsgi-script .py
  RewriteEngine On
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteRule ^(.*)$ /wsgi.py/$1 [QSA,PT,L]
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run(debug=False)
