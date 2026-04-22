"""
メール配信サービス
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

JST = timezone(timedelta(hours=9))

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

    now_str = datetime.now(JST).strftime("%Y年%m月%d日 %H:%M JST")
    subject = f"【AI×FXツール】相場分析レポート {now_str}"

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


def send_quantflow_signal_email(signal, event_type: str) -> bool:
    """
    QuantFlow ライブシグナルのメール通知を送信する。

    Parameters
    ----------
    signal : QuantFlowLiveSignal
    event_type : str
        "ENTRY" / "EXIT_TP" / "EXIT_SL" / "EXIT_SIGNAL_END"

    受信先: Settings テーブルの quantflow_signal_recipients（カンマ区切り）
    """
    from app import mail
    from app.models.settings import Setting
    from flask_mail import Message

    recipients_raw = Setting.get("quantflow_signal_recipients", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        logger.warning("quantflow_signal_recipients が未設定のためメール送信をスキップ")
        return False

    dir_ja    = "買い（BUY）" if signal.direction == "BUY" else "売り（SELL）"
    ep_str    = f"{float(signal.entry_price):.3f}"
    sl_str    = f"{float(signal.sl_price):.3f}"
    tp_str    = f"{float(signal.tp_price):.3f}"
    entry_jst = (signal.entry_ts + timedelta(hours=9)).strftime("%Y/%m/%d %H:%M JST")

    subjects = {
        "ENTRY":           f"[QuantFlow] {dir_ja}シグナル発生 - USDJPY",
        "EXIT_TP":         f"[QuantFlow] TP達成（利確）- USDJPY {signal.direction}",
        "EXIT_SL":         f"[QuantFlow] SL到達（損切）- USDJPY {signal.direction}",
        "EXIT_SIGNAL_END": f"[QuantFlow] シグナル変更で決済 - USDJPY {signal.direction}",
    }

    if event_type == "ENTRY":
        body = f"""
<h2>QuantFlow シグナル発生</h2>
<table>
  <tr><th>方向</th><td>{dir_ja}</td></tr>
  <tr><th>スコア</th><td>{signal.score_at_entry}</td></tr>
  <tr><th>エントリー日時</th><td>{entry_jst}</td></tr>
  <tr><th>エントリー価格</th><td>{ep_str}</td></tr>
  <tr><th>SL</th><td>{sl_str}（{float(signal.sl_pips):.1f} pips）</td></tr>
  <tr><th>TP</th><td>{tp_str}（{float(signal.tp_pips):.1f} pips）</td></tr>
</table>"""
    else:
        exit_jst = (
            (signal.exit_ts + timedelta(hours=9)).strftime("%Y/%m/%d %H:%M JST")
            if signal.exit_ts else "-"
        )
        exit_str = f"{float(signal.exit_price):.3f}" if signal.exit_price else "-"
        pp_str   = f"{float(signal.profit_pips):+.2f}" if signal.profit_pips is not None else "-"
        reason_ja = {
            "EXIT_TP":         "TP達成（利確）",
            "EXIT_SL":         "SL到達（損切）",
            "EXIT_SIGNAL_END": "シグナル変更",
        }.get(event_type, event_type)
        body = f"""
<h2>QuantFlow ポジション決済</h2>
<table>
  <tr><th>決済理由</th><td>{reason_ja}</td></tr>
  <tr><th>方向</th><td>{dir_ja}</td></tr>
  <tr><th>エントリー日時</th><td>{entry_jst}</td></tr>
  <tr><th>エントリー価格</th><td>{ep_str}</td></tr>
  <tr><th>決済日時</th><td>{exit_jst}</td></tr>
  <tr><th>決済価格</th><td>{exit_str}</td></tr>
  <tr><th>損益</th><td>{pp_str} pips</td></tr>
</table>"""

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
<body>{body}</body>
</html>"""

    try:
        msg = Message(
            subject    = subjects.get(event_type, "[QuantFlow] 通知"),
            recipients = recipients,
            html       = html,
        )
        mail.send(msg)
        logger.info("QuantFlow email sent: %s → %s", event_type, recipients)
        return True
    except Exception as exc:
        logger.error("QuantFlow email failed: %s", exc)
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
