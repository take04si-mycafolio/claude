"""
Google Gemini API を使用した相場分析レポート生成サービス
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

JST = timezone(timedelta(hours=9))

import google.generativeai as genai

from app.config import Config

logger = logging.getLogger(__name__)


def _build_prompt(signals_summary: dict, backtest_summary: list, current_prices: dict) -> str:
    """Geminiへのプロンプトを構築する"""
    now_jst = datetime.now(JST).strftime("%Y年%m月%d日 %H:%M JST")

    lines = [
        f"あなたはプロのFXトレーダー兼アナリストです。",
        f"以下のデータをもとに、日本語で相場分析レポートを作成してください。",
        f"レポート作成日時: {now_jst}",
        "",
        "## 分析対象通貨ペア",
        "USD/JPY（ドル円）、GBP/JPY（ポンド円）、EUR/JPY（ユーロ円）",
        "",
        "## 現在値",
    ]

    for pair, price_data in current_prices.items():
        if price_data:
            display = f"{pair[:3]}/{pair[3:]}"
            lines.append(f"- {display}: {price_data.get('close', 'N/A')}")

    lines += [
        "",
        "## テクニカルシグナル分析",
    ]

    for pair, summary in signals_summary.items():
        display = f"{pair[:3]}/{pair[3:]}"
        lines.append(f"\n### {display}")
        lines.append(f"- 総合シグナル: {summary['overall_signal']}")
        lines.append(f"- シグナル強度: {summary['signal_strength']:.1f}%")
        lines.append(f"- 買いシグナル数: {summary['buy_count']}")
        lines.append(f"- 売りシグナル数: {summary['sell_count']}")

        if summary["top_signals"]:
            lines.append("- 主要シグナル:")
            for sig in summary["top_signals"][:3]:
                lines.append(
                    f"  * {sig['indicator_name']} [{sig['timeframe']}]: "
                    f"{sig['signal_type']} (勝率: {sig['win_rate']:.1f}%, "
                    f"信頼度: {sig['confidence_score']:.1f})"
                )

    if backtest_summary:
        lines += [
            "",
            "## バックテスト上位指標（勝率ランキング）",
        ]
        for r in backtest_summary[:10]:
            lines.append(
                f"- {r['pair']} {r['tf']} {r['indicator']}: "
                f"勝率{r['win_rate']:.1f}% ({r['trades']}トレード, "
                f"損益: ¥{r['profit']:,.0f})"
            )

    lines += [
        "",
        "## レポートの要件",
        "1. 各通貨ペアの現在の相場環境を分析してください（トレンド・レンジ・ボラティリティ）",
        "2. テクニカルシグナルを総合的に評価し、買い・売りの根拠を述べてください",
        "3. 注意すべきリスク要因があれば記載してください",
        "4. 今後の値動きの見通し（短期: 本日中、中期: 数日間）を提示してください",
        "5. トレード推奨がある場合は、エントリー根拠、利確目標、損切り水準を明示してください",
        "6. 投資は自己責任である旨の注意書きを末尾に必ず記載してください",
        "",
        "読みやすいようにMarkdown形式で出力してください。",
    ]

    return "\n".join(lines)


def generate_report(signals_summary: dict, backtest_top: list, current_prices: dict) -> Optional[dict]:
    """
    Gemini APIを使って相場分析レポートを生成する。

    Returns
    -------
    dict: {"content": str, "model": str, "tokens": int} or None
    """
    if not Config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set")
        return None

    genai.configure(api_key=Config.GEMINI_API_KEY)
    model = genai.GenerativeModel(Config.GEMINI_MODEL)

    prompt = _build_prompt(signals_summary, backtest_top, current_prices)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        content = response.text
        tokens = response.usage_metadata.total_token_count if hasattr(response, "usage_metadata") else 0

        return {
            "content": content,
            "model": Config.GEMINI_MODEL,
            "tokens": tokens,
        }
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        return None


def save_report(content: str, model: str, tokens: int) -> int:
    """レポートをDBに保存してIDを返す"""
    from app import db
    from app.models.report import AiReport

    record = AiReport(
        report_type="scheduled",
        content=content,
        model_used=model,
        tokens_used=tokens,
        email_sent=False,
    )
    db.session.add(record)
    db.session.commit()
    return record.id


def create_and_save_report() -> Optional[int]:
    """
    現在のシグナル・バックテストデータからレポートを生成してDBに保存する。

    Returns
    -------
    int: 保存されたレポートのID、失敗時はNone
    """
    from app.services.signal_engine import get_summary_signals
    from app.services.data_fetcher import get_latest_price
    from app.models.backtest import BacktestResult

    signals_summary = get_summary_signals()

    current_prices = {}
    for pair in Config.CURRENCY_PAIRS:
        current_prices[pair] = get_latest_price(pair)

    # バックテスト上位結果
    top_results = (
        BacktestResult.query
        .filter(BacktestResult.win_rate >= Config.MIN_WIN_RATE)
        .order_by(BacktestResult.win_rate.desc())
        .limit(20)
        .all()
    )

    backtest_top = [
        {
            "pair": r.currency_pair,
            "tf": r.timeframe,
            "indicator": r.indicator_name,
            "win_rate": float(r.win_rate),
            "trades": r.total_trades,
            "profit": float(r.total_profit),
        }
        for r in top_results
    ]

    result = generate_report(signals_summary, backtest_top, current_prices)
    if result is None:
        return None

    report_id = save_report(result["content"], result["model"], result["tokens"])
    logger.info("Report #%d generated (%d tokens)", report_id, result["tokens"])
    return report_id
