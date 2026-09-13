"""口コミ・使用記録(UGC)向けの薬機法・景表法コンプライアンスゲート。

検出パターンの単一ソースは記事リンタ
apps/products/management/commands/yakkihou_lint.py の RULES。
本モジュールはそれを「投稿者に返すエラー」として使えるように翻訳する:

  - headline / reason … なぜ掲載できないかの平易な説明(法律名つき)
  - example           … 感想としてどう書き直せばよいかの例文
  - drop_in           … 該当語をそのまま差し替えられる場合の置換語
                         (文法が壊れない語レベルの置換のみ設定する)

すべての findings に drop_in がある場合のみ、全文の自動言い換え案
(suggest_full_text) を生成できる。文の構造ごと直す必要がある表現
(効能の断定・メカニズム言及など)は example を見せて本人に直してもらう。
"""

import re

from apps.products.management.commands.yakkihou_lint import RULES

# カテゴリ別の見出し(投稿者向けの説明)
CATEGORY_HEADLINES = {
    "CRITICAL": "体への効果・変化を断定する表現は、薬機法の関係で掲載できません",
    "HIGH": "効果の断定・保証と受け取られる表現は掲載できません",
    "KEIHYO": "「最強」「No.1」などの最上級・断定表現は掲載できません(景品表示法)",
    "SAFETY": "安全性を保証する表現は掲載できません",
}

# 全体の書き方ヒント(フォーム/アプリで findings と一緒に表示する)
WRITING_HINT = (
    "「私の場合は〜でした」「〜な気がします」のように、"
    "あくまで個人の感想として書いていただくと掲載しやすくなります。"
)

# ルールの label(第2要素) → 投稿者向けガイダンス。
# drop_in は「該当語をそのまま差し替えても文が壊れない」ものだけに設定する。
GUIDANCE = {
    # ----- CRITICAL -----
    "コラーゲン生成・促進": {
        "reason": "コラーゲンの生成・増加など、体の仕組みへの効果は書けません。",
        "example": "使い続けるうちに、肌のハリ感が増した気がします",
    },
    "皮膚深部への作用": {
        "reason": "肌の深い部分(真皮など)への浸透・作用は書けません。",
        "example": "肌がしっとり、もっちりした感じがします",
    },
    "細胞活性化": {
        "reason": "細胞への働きかけは医療的な表現になるため書けません。",
        "example": "肌が元気になったように感じます",
    },
    "線維芽細胞への作用": {
        "reason": "細胞への働きかけは医療的な表現になるため書けません。",
        "example": "肌が元気になったように感じます",
    },
    "症状改善の断定": {
        "reason": "シミ・シワ・たるみが「消える・治る」といった断定は書けません。",
        "example": "肌が明るく見えるようになった気がします / メイクのりが良くなりました",
    },
    "若返り表現": {
        "reason": "「若返る」という表現は書けません。",
        "example": "肌の調子が上向いてきた気がします",
    },
    "血行促進の断定": {
        "reason": "血行への効果を断定する表現は書けません。",
        "example": "使ったあと、肌がぽかぽかと温かく感じます",
    },
    "代謝への作用": {
        "reason": "代謝への効果を断定する表現は書けません。",
        "example": "朝の肌がすっきりして感じられます",
    },
    "アンチエイジング効果": {
        "reason": "「アンチエイジング効果」という表現は書けません。",
        "example": "エイジングケア(年齢に応じたお手入れ)のつもりで使っています",
        "drop_in": "エイジングケア",
    },
    "治癒・治療表現": {
        "reason": "「治る・治す」は医療行為の表現のため書けません。",
        "example": "気にならなくなってきました",
    },
    "リフトアップ効果の断定": {
        "reason": "リフトアップ効果を断定する表現は書けません。",
        "example": "フェイスラインがすっきりした気がします",
    },
    "筋肉作用の断定": {
        "reason": "筋肉を鍛える・引き上げるといった断定は書けません。",
        "example": "頬のあたりにしっかり刺激を感じます",
    },
    # ----- HIGH -----
    "効果がある": {
        "reason": "効果の断定はできません。個人の感想として書いてください。",
        "example": "私は使い始めてから変化を感じました",
    },
    "効きます": {
        "reason": "効果の保証はできません。個人の感想として書いてください。",
        "example": "私には合っていたようです",
    },
    "確実に": {
        "reason": "「確実に」という保証はできません。",
        "example": "「確実に」を削除するか、「私の場合は」に言い換えてください",
        "drop_in": "",
    },
    "必ず〜": {
        "reason": "「必ず」という保証はできません。",
        "example": "私の場合は〜でした",
    },
    "短期間で〜": {
        "reason": "短期間での効果を保証する表現は書けません。",
        "example": "使い続けるうちに、少しずつ変化を感じました",
    },
    "期間限定の効果保証": {
        "reason": "「◯週間で効果」のように期間と効果を結びつける断定は書けません。",
        "example": "1ヶ月ほど使っていますが、肌の調子は良いように感じます",
    },
    "医学的根拠の主張": {
        "reason": "医学的な証明・実証は根拠が確認できないため書けません。",
        "example": "該当の一文を削除してください",
    },
    "臨床試験の主張": {
        "reason": "臨床試験による証明は根拠が確認できないため書けません。",
        "example": "該当の一文を削除してください",
    },
    # ----- KEIHYO -----
    "最強": {
        "reason": "「最強」などの最上級表現は書けません。",
        "example": "私が使った中では一番良かったです",
        "drop_in": "抜群",
    },
    "業界最〜": {
        "reason": "「業界最高」などの最上級表現は根拠が確認できないため書けません。",
        "example": "私が今まで使った中では一番です",
    },
    "日本一": {
        "reason": "「日本一」は根拠が確認できないため書けません。",
        "example": "私が今まで使った中では一番です",
    },
    "No.1": {
        "reason": "「No.1」は根拠が確認できないため書けません。",
        "example": "私が今まで使った中では一番です",
    },
    "ナンバーワン": {
        "reason": "「ナンバーワン」は根拠が確認できないため書けません。",
        "example": "私が今まで使った中では一番です",
    },
    "完全に": {
        "reason": "「完全に」という断定は書けません。",
        "example": "かなり〜だと感じました",
        "drop_in": "かなり",
    },
    "絶対": {
        "reason": "「絶対」という断定は書けません。",
        "example": "とてもおすすめです",
        "drop_in": "とても",
    },
    "唯一無二": {
        "reason": "「唯一無二」は根拠が確認できないため書けません。",
        "example": "私にとっては替えのきかない一台です",
    },
    "圧倒的な効果": {
        "reason": "「圧倒的な効果」のような誇張表現は書けません。",
        "example": "満足度はかなり高いです",
    },
    # ----- SAFETY -----
    "副作用なし": {
        "reason": "「副作用がない」という安全性の保証は書けません。",
        "example": "私は肌トラブルなく使えています",
    },
    "100%安全": {
        "reason": "「100%安全」という保証は書けません。",
        "example": "私は安心して使えました",
    },
    "誰でも安心": {
        "reason": "「誰でも安心・安全」という保証は書けません。",
        "example": "機械が苦手な私でも扱いやすかったです",
    },
    "刺激なし断定": {
        "reason": "「刺激がない」という断定は書けません。",
        "example": "私は刺激をほとんど感じませんでした",
    },
}

_FALLBACK_REASON = "法律(薬機法・景品表示法)の関係で掲載できない表現です。"
_FALLBACK_EXAMPLE = "個人の感想として「〜な気がします」のように書き換えてください"


def find_violations(text):
    """テキストを検査し、投稿者に返せる findings のリストを返す(出現順)。

    finding: {severity, headline, label, match, start, end,
              reason, example, drop_in(None可)}
    """
    if not text:
        return []
    findings = []
    for severity, rule_set in RULES.items():
        for pattern, label in rule_set["patterns"]:
            for m in re.finditer(pattern, text):
                g = GUIDANCE.get(label, {})
                findings.append({
                    "severity": severity,
                    "headline": CATEGORY_HEADLINES[severity],
                    "label": label,
                    "match": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                    "reason": g.get("reason", _FALLBACK_REASON),
                    "example": g.get("example", _FALLBACK_EXAMPLE),
                    "drop_in": g.get("drop_in"),
                })
    findings.sort(key=lambda f: f["start"])
    return findings


def check_fields(**fields):
    """複数フィールドをまとめて検査する。finding に field キーを足して返す。

    使い方: check_fields(title=..., body=...)
    """
    all_findings = []
    for field, text in fields.items():
        for f in find_violations(text):
            f["field"] = field
            all_findings.append(f)
    return all_findings


def api_error_payload(title, body, findings):
    """API(DRF)の ValidationError に載せる構造化ペイロードを作る。

    アプリ側はこの compliance オブジェクトをそのまま指摘UIに使える。
    """
    title_findings = [f for f in findings if f["field"] == "title"]
    body_findings = [f for f in findings if f["field"] == "body"]
    return {
        "detail": "掲載できない表現が含まれています。指摘箇所を修正して再投稿してください。",
        "compliance": {
            "hint": WRITING_HINT,
            "findings": [
                {
                    "field": f["field"],
                    "severity": f["severity"],
                    "headline": f["headline"],
                    "match": f["match"],
                    "start": f["start"],
                    "end": f["end"],
                    "reason": f["reason"],
                    "example": f["example"],
                }
                for f in findings
            ],
            "suggested_title": suggest_full_text(title, title_findings)
            if title_findings else None,
            "suggested_body": suggest_full_text(body, body_findings)
            if body_findings else None,
        },
    }


def suggest_full_text(text, findings=None):
    """全文の自動言い換え案を返す。作れない場合は None。

    すべての findings に drop_in があるときだけ生成する(文の構造ごと
    直す必要がある表現が混ざっていると、機械置換では文が壊れるため)。
    置換後に再検査し、まだ違反が残る場合も None を返す。
    """
    if findings is None:
        findings = find_violations(text)
    if not findings:
        return None
    if any(f["drop_in"] is None for f in findings):
        return None
    out = text
    for f in sorted(findings, key=lambda f: -f["start"]):
        out = out[: f["start"]] + f["drop_in"] + out[f["end"]:]
    if find_violations(out):
        return None
    return out
