"""
メール配信サービス
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import Config

logger = logging.getLogger(__name__)


def send_report_email(report_id: int) -> bool:
    """
    指定レポートIDのレポートをメールで送信する。

    Returns
    -------
    bool: 送信成功かどうか
    """
    from app import db, mail
    from app.models.report import AiReport
    from flask_mail import Message

    report = AiReport.query.get(report_id)
    if not report:
        logger.error("Report #%d not found", report_id)
        return False

    recipients = Config.REPORT_RECIPIENTS
    if not recipients:
        logger.warning("No REPORT_RECIPIENTS configured")
        return False

    now_str = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")
    subject = f"【FXシグナルツール】相場分析レポート {now_str}"

    # Markdown をプレーンテキストに変換（簡易）
    plain_text = report.content

    # HTMLメール用に簡易変換
    html_body = _markdown_to_html(report.content)

    try:
        msg = Message(
            subject=subject,
            recipients=recipients,
            body=plain_text,
            html=html_body,
        )
        mail.send(msg)
        report.email_sent = True
        report.email_sent_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info("Report #%d sent to %s", report_id, recipients)
        return True
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        return False


def _markdown_to_html(text: str) -> str:
    """シンプルなMarkdown → HTML変換"""
    import re

    lines = text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        # 見出し
        if line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{line[2:]}</h1>")
        # リスト
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = line[2:]
            # ボールド
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item)
            html_lines.append(f"<li>{item}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if line.strip():
                line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                html_lines.append(f"<p>{line}</p>")
            else:
                html_lines.append("<br>")

    if in_list:
        html_lines.append("</ul>")

    body = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
  h1, h2, h3 {{ color: #1a56db; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 4px 0; }}
  p {{ line-height: 1.6; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
