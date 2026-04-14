#!/usr/bin/env python3
"""
run_ai_bt_analyze.py — Gemini を使って指標バックテストを分析し、改善条件を提案する

PHP admin/api.php の exec() から同期呼び出しされる。
引数: <params_json_file_path>
標準出力: JSON 結果（改行なし）

入力:
  indicator_name: str  — 対象指標名 (例: RSI_14)
  indicator_display: str  — 日本語表示名 (例: RSI（相対力指数）14期間)

出力:
  {
    "ok": true,
    "indicator_name": "RSI_14",
    "analysis": "...(Geminiの分析テキスト)...",
    "model": "gemini-1.5-flash",
    "tokens": 1234
  }
"""

import sys
import os
import json
import warnings
import traceback

warnings.filterwarnings("ignore")

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "使い方: run_ai_bt_analyze.py <params_file>"}))
        return

    try:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            body = json.load(f)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"パラメータ読み込みエラー: {e}"}))
        return

    try:
        from app import create_app, db
        from sqlalchemy import text
        from app.config import Config

        app = create_app()
        with app.app_context():
            indicator_name    = body.get("indicator_name", "").strip()
            indicator_display = body.get("indicator_display", indicator_name)

            if not indicator_name:
                print(json.dumps({"ok": False, "error": "indicator_name が必要です"}))
                return

            if not Config.GEMINI_API_KEY:
                print(json.dumps({"ok": False, "error": "GEMINI_API_KEY が設定されていません"}))
                return

            # ---- バックテストデータを収集 ----
            # 1) テクニカルページ専用バックテストを優先
            bt_rows = db.session.execute(
                text("SELECT currency_pair, timeframe, win_rate, profit_factor, "
                     "total_trades, winning_trades, losing_trades, total_profit, "
                     "sl_pips, tp_pips, start_date, end_date "
                     "FROM indicator_page_bt_results WHERE indicator_name = :ind "
                     "ORDER BY currency_pair, timeframe"),
                {"ind": indicator_name}
            ).fetchall()

            # 2) なければランキング用テーブルにフォールバック
            if not bt_rows:
                bt_rows = db.session.execute(
                    text("SELECT currency_pair, timeframe, win_rate, profit_factor, "
                         "total_trades, winning_trades, losing_trades, total_profit, "
                         "sl_pips, tp_pips, NULL as start_date, NULL as end_date "
                         "FROM backtest_results WHERE indicator_name = :ind "
                         "ORDER BY currency_pair, timeframe"),
                    {"ind": indicator_name}
                ).fetchall()

            if not bt_rows:
                print(json.dumps({"ok": False, "error": "バックテストデータがありません。先にバックテストを実行してください。"}))
                return

            # 直近トレード（最新50件）
            trade_rows = []
            for table in ("indicator_page_sim_trades", "simulation_trades"):
                try:
                    rows = db.session.execute(
                        text(f"SELECT currency_pair, timeframe, direction, outcome, "
                             f"entry_at, exit_at, profit_loss "
                             f"FROM {table} WHERE indicator_name = :ind "
                             f"ORDER BY entry_at DESC LIMIT 50"),
                        {"ind": indicator_name}
                    ).fetchall()
                    if rows:
                        trade_rows = rows
                        break
                except Exception:
                    continue

            # ---- プロンプト構築 ----
            prompt = _build_prompt(indicator_name, indicator_display, bt_rows, trade_rows)

            # ---- Gemini 呼び出し ----
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            model = genai.GenerativeModel(Config.GEMINI_MODEL)

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=3000,
                ),
            )
            analysis = response.text
            tokens   = getattr(response.usage_metadata, "total_token_count", 0)

            print(json.dumps({
                "ok":               True,
                "indicator_name":   indicator_name,
                "indicator_display": indicator_display,
                "analysis":         analysis,
                "model":            Config.GEMINI_MODEL,
                "tokens":           tokens,
            }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({
            "ok":     False,
            "error":  str(e),
            "detail": traceback.format_exc(),
        }, ensure_ascii=False))


# ---------------------------------------------------------------------------

TF_LABELS = {
    "5min": "5分足", "15min": "15分足", "30min": "30分足",
    "1hr": "1時間足", "4hr": "4時間足", "daily": "日足",
}
PAIR_LABELS = {"USDJPY": "USD/JPY", "GBPJPY": "GBP/JPY", "EURJPY": "EUR/JPY"}


def _build_prompt(indicator_name, indicator_display, bt_rows, trade_rows):
    lines = [
        "あなたはFXテクニカル分析の専門家です。",
        "以下のバックテスト結果を分析し、この指標の勝率を改善するための追加条件を提案してください。",
        "",
        f"## 対象指標: {indicator_display}",
        "",
        "## バックテスト結果サマリー",
        "| 通貨ペア | 時間足 | 勝率 | PF | 取引数 | 総損益 | SL | TP |",
        "|---------|--------|------|----|--------|--------|----|----|",
    ]

    for r in bt_rows:
        d = dict(r._mapping)
        pair_lbl = PAIR_LABELS.get(d["currency_pair"], d["currency_pair"])
        tf_lbl   = TF_LABELS.get(d["timeframe"], d["timeframe"])
        wr   = float(d.get("win_rate") or 0)
        pf   = float(d.get("profit_factor") or 0)
        tt   = int(d.get("total_trades") or 0)
        prof = float(d.get("total_profit") or 0)
        sl   = float(d.get("sl_pips") or 20)
        tp   = float(d.get("tp_pips") or 40)
        lines.append(
            f"| {pair_lbl} | {tf_lbl} | {wr:.1f}% | {pf:.2f} | {tt}件 | ¥{prof:,.0f} | {sl}pips | {tp}pips |"
        )

    if trade_rows:
        # 直近20件のトレードパターンを分析
        wins  = [t for t in trade_rows if dict(t._mapping).get("outcome") == "WIN"]
        losses = [t for t in trade_rows if dict(t._mapping).get("outcome") == "LOSS"]
        buy_win  = sum(1 for t in wins   if dict(t._mapping).get("direction") == "BUY")
        sell_win = sum(1 for t in wins   if dict(t._mapping).get("direction") == "SELL")
        buy_loss = sum(1 for t in losses if dict(t._mapping).get("direction") == "BUY")
        sell_loss= sum(1 for t in losses if dict(t._mapping).get("direction") == "SELL")
        lines += [
            "",
            "## 直近トレードパターン（最新50件より集計）",
            f"- 勝ちトレード: {len(wins)}件（BUY: {buy_win} / SELL: {sell_win}）",
            f"- 負けトレード: {len(losses)}件（BUY: {buy_loss} / SELL: {sell_loss}）",
        ]

    lines += [
        "",
        "## 利用可能なバックテスト条件（バックテストツール2）",
        "以下の指標を組み合わせ条件として使えます:",
        "- テクニカル指標: RSI(期間), EMA(期間), SMA(期間), MACD(ヒスト/ライン/シグナル),",
        "  Stoch %K/%D, CCI, Williams %R, ATR, BB上/中/下バンド, CLOSE, HIGH, LOW",
        "- ローソク足パターン（1=検出 / 0=未検出）: ハンマー, 逆ハンマー, 十字線, 強気包み足,",
        "  弱気包み足, 三白兵, 三羽烏, ピンバー（陽線）, ピンバー（陰線）",
        "- 比較演算子: >, <, >=, <=, =, ↑クロスアップ, ↓クロスダウン",
        "- 条件間論理: AND / OR",
        "",
        "## 回答形式",
        "以下の構成で日本語で回答してください:",
        "",
        "### 1. 現状分析（3〜5行）",
        "この指標のバックテスト結果の特徴・強みと弱みを端的に述べてください。",
        "",
        "### 2. 改善戦略の提案（2〜3案）",
        "各案に以下を記載してください:",
        "- 戦略名（例：RSI + EMAフィルター戦略）",
        "- 追加する条件（具体的な指標・パラメータ・閾値を明示）",
        "- 期待される効果と根拠",
        "- 推奨テスト期間と時間足",
        "",
        "### 3. 注意事項",
        "過学習・データスヌーピングのリスクや注意点を簡潔に。",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    main()
