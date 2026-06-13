"""SEO品質計測サービス - 全記事タイプ共通"""
import re
from typing import Optional


def clean_ai_output(text: Optional[str]) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^```(?:html|HTML)?\s*\n?", "", t)
    t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def jaccard_similarity(a: str, b: str, n: int = 2) -> float:
    def ngrams(s, k):
        return set(s[i:i+k] for i in range(max(0, len(s) - k + 1)))
    if not a or not b:
        return 0.0 if a != b else 1.0
    A = ngrams(a, n); B = ngrams(b, n)
    if not A and not B:
        return 1.0
    return len(A & B) / max(len(A | B), 1)


def analyze_seo_metrics(content: str, keyword: str) -> dict:
    plain = re.sub(r"<[^>]+>", " ", content or "")
    plain_no_space = re.sub(r"\s+", "", plain)
    char_count = len(plain_no_space)
    keyword_count = plain.count(keyword) if keyword else 0
    keyword_density = (keyword_count / max(char_count, 1)) * 100
    h2 = len(re.findall(r"<h2[\s>]", content or ""))
    h3 = len(re.findall(r"<h3[\s>]", content or ""))
    p = len(re.findall(r"<p[\s>]", content or ""))
    h2_texts = [m.strip() for m in re.findall(r"<h2[^>]*>(.*?)</h2>", content or "", re.DOTALL)]
    return {
        "char_count": char_count, "keyword_count": keyword_count,
        "keyword_density": round(keyword_density, 3),
        "h2_count": h2, "h3_count": h3, "p_count": p, "h2_texts": h2_texts,
    }


def compare_h2_structure(before_h2s: list, after_h2s: list, sim_threshold: float = 0.4) -> dict:
    diff = abs(len(before_h2s) - len(after_h2s))
    issues = []
    if diff > 1:
        issues.append(f"H2数が±1超え({len(before_h2s)} → {len(after_h2s)})")
    similarities, matched_indices = [], []
    for b in before_h2s:
        best_sim, best_idx = 0.0, -1
        for i, a in enumerate(after_h2s):
            sim = jaccard_similarity(b, a, n=2)
            if sim > best_sim:
                best_sim, best_idx = sim, i
        similarities.append({"before": b,
                             "best_after": after_h2s[best_idx] if best_idx >= 0 else "",
                             "similarity": round(best_sim, 3)})
        if best_sim >= sim_threshold:
            matched_indices.append(best_idx)
    is_monotonic = (all(matched_indices[i] <= matched_indices[i+1]
                        for i in range(len(matched_indices)-1))
                    if len(matched_indices) > 1 else True)
    avg_sim = sum(s["similarity"] for s in similarities) / max(len(similarities), 1)
    matched = sum(1 for s in similarities if s["similarity"] >= sim_threshold)
    match_ratio = matched / max(len(before_h2s), 1)
    if match_ratio < 0.7:
        issues.append(f"H2類似度マッチ率が{match_ratio*100:.0f}% (基準70%)")
    if not is_monotonic:
        issues.append("H2の順番が大きく入れ替わっています")
    return {
        "before_h2s": before_h2s, "after_h2s": after_h2s,
        "similarities": similarities,
        "match_ratio": round(match_ratio, 3),
        "avg_similarity": round(avg_sim, 3),
        "is_monotonic": is_monotonic,
        "issues": issues, "acceptable": len(issues) == 0,
    }


def compare_seo_metrics(before, after, min_ratio=0.7, keyword_min=5, keyword_max=10):
    def ratio(a, b):
        return (a / b) if b > 0 else (1.0 if a == 0 else 1.0)
    char_ratio = ratio(after["char_count"], before["char_count"])
    kw_ratio = ratio(after["keyword_count"], before["keyword_count"])
    h2_ratio = ratio(after["h2_count"], before["h2_count"])
    issues = []
    if char_ratio < min_ratio: issues.append(f"文字数が{char_ratio*100:.0f}%に減少")
    if kw_ratio < min_ratio: issues.append(f"キーワード出現が{kw_ratio*100:.0f}%に減少")
    if h2_ratio < min_ratio: issues.append(f"H2見出しが{h2_ratio*100:.0f}%に減少")
    kw_count = after.get("keyword_count", 0)
    if kw_count < keyword_min:
        issues.append(f"キーワード出現{kw_count}回(推奨{keyword_min}〜{keyword_max}回)")
    elif kw_count > keyword_max:
        issues.append(f"キーワード出現{kw_count}回が多すぎ")
    h2_struct = compare_h2_structure(before.get("h2_texts", []), after.get("h2_texts", []), 0.4)
    if not h2_struct["acceptable"]:
        issues.extend([f"H2構造: {i}" for i in h2_struct["issues"]])
    return {
        "before": before, "after": after,
        "char_ratio": round(char_ratio, 3),
        "kw_ratio": round(kw_ratio, 3),
        "h2_ratio": round(h2_ratio, 3),
        "kw_in_range": keyword_min <= kw_count <= keyword_max,
        "h2_structure": h2_struct,
        "issues": issues, "acceptable": len(issues) == 0,
    }
