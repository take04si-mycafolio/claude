"""WorkReport(作業報告)を読み手向けに整形するための補助(2026-09-07)。

管理画面の報告ページ(change_form)とリスト(change_list)から使う。
- 報告者(AI社員キャラクター)の推定: タイトル接頭辞 → approval_center._AGENTS / characters.json
- 本文Markdown → HTML(見出し目次つき・表は横スクロール枠で包む)
- 概要(summary)の「・」区切りを箇条書きに分解(括弧内の「・」は分割しない)
"""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

def agent_for_title(title):
    """タイトルから報告者を推定して {key,name,nick,avatar,color,duty} を返す。
    AI社員の報告は指示書で固定接頭辞(週次ダイジェスト/リサーチ/新規執筆/検品/商品記事v2/リライト後続処理/
    リライト効果 定期観測)が決まっているので接頭辞一致のみで判定する。
    (語の含有で判定すると「編集長の運用変更」のような開発報告が社員扱いになるため、緩い判定はしない)
    該当なしは開発(Claude Code)。"""
    from .approval_center import _AGENTS, _characters, _MEDIA_ROOT
    chars = _characters()
    key = None
    for a in _AGENTS:
        if title.startswith(a["prefix"]):
            key = a["key"]
            break
    if key is None:
        return {"key": "dev", "name": "Claude Code(開発・保守)", "nick": "開発",
                "avatar": "", "color": "#555", "duty": "コード修正・基盤整備・運用変更"}
    meta = next((a for a in _AGENTS if a["key"] == key), {})
    ch = chars.get(key) or {}
    avatar = ch.get("avatar", "")
    if avatar and not (_MEDIA_ROOT / avatar.lstrip("/")).exists():
        avatar = ""
    return {"key": key, "name": ch.get("name") or meta.get("name", key),
            "nick": ch.get("nick") or meta.get("name", key),
            "avatar": avatar, "color": ch.get("color", "#555"),
            "duty": meta.get("duty", "")}


def summary_items(summary):
    """概要を「・」で分解して箇条書き用のリストにする。括弧内の「・」は区切りとみなさない。
    短い(60字未満)か区切りが1つ以下ならそのまま1要素で返す。"""
    s = (summary or "").strip()
    if not s:
        return []
    parts, buf, depth = [], [], 0
    for ch in s:
        if ch in "（(【[":
            depth += 1
        elif ch in "）)】]":
            depth = max(0, depth - 1)
        if ch == "・" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf).strip())
    parts = [p for p in parts if p]
    if len(s) < 60 or len(parts) < 2:
        return [s]
    # 「※」以降の注記は独立させる
    out = []
    for p in parts:
        if "※" in p and not p.startswith("※"):
            head, note = p.split("※", 1)
            out.append(head.strip())
            out.append("※" + note.strip())
        else:
            out.append(p)
    return out


_TABLE_RE = re.compile(r"<table>(.*?)</table>", re.S)


def render_body(body):
    """Markdown本文を HTML化。戻り値 (html, toc_tokens)。表は横スクロール枠で包む。"""
    if not (body or "").strip():
        return "", []
    import markdown
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "nl2br", "sane_lists", "toc"],
        extension_configs={"toc": {"toc_depth": "2-3", "anchorlink": False}},
    )
    html = md.convert(body)
    html = _TABLE_RE.sub(lambda m: '<div class="wr-tbl"><table>' + m.group(1) + "</table></div>", html)
    toc = []
    for t in getattr(md, "toc_tokens", []) or []:
        if t.get("level") == 2:
            toc.append({"id": t["id"], "name": t["name"]})
    return mark_safe(html), toc


def files_list(files_changed):
    return [f.strip() for f in (files_changed or "").splitlines() if f.strip()]


def summary_html_for_list(summary, limit=160):
    """一覧用: 折り返し可能な小さめテキスト。長い場合は省略しツールチップに全文。"""
    s = (summary or "").strip()
    if not s:
        return "-"
    short = s if len(s) <= limit else s[:limit].rstrip() + "…"
    return mark_safe(
        '<div class="wr-sum" title="{}">{}</div>'.format(escape(s), escape(short)))
