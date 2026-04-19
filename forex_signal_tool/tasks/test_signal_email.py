#!/usr/bin/env python3
"""
QuantFlow シグナルメールのテスト送信タスク。
管理画面の「テスト送信」ボタンから呼び出される。
成功時は標準出力に "OK" を含む文字列を出力する。
"""
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JST = timezone(timedelta(hours=9))


def main():
    from app import create_app, mail
    from app.models.settings import Setting
    from flask_mail import Message

    app = create_app()
    with app.app_context():
        recipients_raw = Setting.get("quantflow_signal_recipients", "")
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

        if not recipients:
            print("ERROR: quantflow_signal_recipients が未設定です。設定ページでメールアドレスを登録してください。")
            return

        now_jst = datetime.now(JST).strftime("%Y/%m/%d %H:%M JST")

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body  {{ font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333; }}
  h2   {{ color: #1a56db; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th   {{ background: #f5f5f5; width: 35%; }}
</style>
</head>
<body>
<h2>[QuantFlow] テスト送信</h2>
<p>このメールはテスト送信です。QuantFlow シグナル通知が正常に動作しています。</p>
<table>
  <tr><th>送信日時</th><td>{now_jst}</td></tr>
  <tr><th>通知先</th><td>{', '.join(recipients)}</td></tr>
</table>
</body>
</html>"""

        try:
            msg = Message(
                subject  = f"[QuantFlow] テスト送信 - {now_jst}",
                recipients = recipients,
                html     = html,
            )
            mail.send(msg)
            print(f"OK: テストメールを送信しました → {recipients}")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
