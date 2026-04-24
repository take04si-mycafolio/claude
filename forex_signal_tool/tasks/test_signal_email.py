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
    import traceback
    from app import create_app, mail
    from app.models.settings import Setting
    from app.config import Config
    from flask_mail import Message

    app = create_app()
    with app.app_context():
        recipients_raw = Setting.get("quantflow_signal_recipients", "")
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

        # SMTP 設定の診断
        diag = {
            "MAIL_SERVER":         Config.MAIL_SERVER or "(未設定)",
            "MAIL_PORT":           Config.MAIL_PORT,
            "MAIL_USE_TLS":        Config.MAIL_USE_TLS,
            "MAIL_USERNAME":       Config.MAIL_USERNAME or "(未設定)",
            "MAIL_PASSWORD":       ("(設定済み)" if Config.MAIL_PASSWORD and not Config.MAIL_PASSWORD.startswith("your_")
                                    else "(未設定 or プレースホルダ)"),
            "MAIL_DEFAULT_SENDER": Config.MAIL_DEFAULT_SENDER or "(未設定)",
        }
        print("=== SMTP 設定 ===")
        for k, v in diag.items():
            print(f"  {k}: {v}")

        if not recipients:
            print("ERROR: quantflow_signal_recipients が未設定です。設定ページでメールアドレスを登録してください。")
            return
        print(f"  受信者: {recipients}")

        # プレースホルダ未設定なら即エラー
        if not Config.MAIL_PASSWORD or Config.MAIL_PASSWORD.startswith("your_"):
            print("ERROR: MAIL_PASSWORD が未設定です。設定ページから SMTP パスワードを入力してください。")
            return
        if not Config.MAIL_USERNAME or "@" not in Config.MAIL_USERNAME:
            print("ERROR: MAIL_USERNAME（メールアドレス）が未設定 or 無効です。")
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
  <tr><th>SMTPサーバー</th><td>{Config.MAIL_SERVER}:{Config.MAIL_PORT}</td></tr>
</table>
</body>
</html>"""

        # 生 SMTP で接続テスト（flask_mail より詳細なエラーが取れる）
        import smtplib, ssl
        print("\n=== SMTP 接続テスト ===")
        try:
            server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=15)
            server.set_debuglevel(1)
            server.ehlo()
            if Config.MAIL_USE_TLS:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            print("  ✓ SMTP 認証成功")
            server.quit()
        except smtplib.SMTPAuthenticationError as e:
            print(f"ERROR: 認証失敗 - {e.smtp_code} {e.smtp_error.decode('utf-8', errors='replace') if isinstance(e.smtp_error, bytes) else e.smtp_error}")
            print("  → パスワードが間違っている可能性があります。Xserverのメール管理でパスワードを再確認してください。")
            return
        except smtplib.SMTPConnectError as e:
            print(f"ERROR: 接続失敗 - {e}")
            print(f"  → MAIL_SERVER ({Config.MAIL_SERVER}) / MAIL_PORT ({Config.MAIL_PORT}) が正しいか確認してください。")
            return
        except smtplib.SMTPServerDisconnected as e:
            print(f"ERROR: サーバー切断 - {e}")
            return
        except TimeoutError as e:
            print(f"ERROR: タイムアウト - {e}")
            print(f"  → サーバーからの応答がありません。SMTP 送信がファイアウォールで遮断されている可能性があります。")
            return
        except Exception as e:
            print(f"ERROR: SMTP 接続エラー - {type(e).__name__}: {e}")
            traceback.print_exc()
            return

        # 認証OK → Flask-Mail で本送信
        print("\n=== Flask-Mail でテストメール送信中 ===")
        try:
            msg = Message(
                subject  = f"[QuantFlow] テスト送信 - {now_jst}",
                recipients = recipients,
                html     = html,
            )
            mail.send(msg)
            print(f"OK: テストメールを送信しました → {recipients}")
        except Exception as e:
            print(f"ERROR: 送信時エラー - {type(e).__name__}: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
