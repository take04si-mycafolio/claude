"""記事エディタ内から直接画像をアップロードするためのAPI（管理画面専用）。

記事編集画面の本文エディタで、ファイル選択・ドラッグ&ドロップ・クリップボード貼り付けから
画像をアップロードし、カーソル位置に <figure> を差し込むために使う。

- 保存先は ArticleImage（記事に紐づく既存モデル）。「記事内画像」インラインにもそのまま並ぶ。
- 実行ユーザーは gunicorn の deploy。media/ 配下の所有者が root にならないようにするため、
  root でこのAPIを叩かない（テストは Django test client か管理画面から行う）。
"""

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .models import Article, ArticleImage

# 受け入れる画像形式（拡張子とContent-Typeの両方で確認する）
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB


def _figure_html(img, alt="", caption=""):
    """本文に差し込む figure HTML（記事CSSの .bk-mc-illust-figure を使う）。"""
    alt = (alt or "").replace('"', "&quot;")
    parts = [
        '<figure class="bk-mc-illust-figure">',
        f'<img src="{img.image.url}" alt="{alt}" loading="lazy">',
    ]
    if caption:
        safe_caption = (caption or "").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f"<figcaption>{safe_caption}</figcaption>")
    parts.append("</figure>")
    return "\n".join(parts)


@staff_member_required
@require_POST
def upload_article_image(request, article_id):
    """画像を1枚アップロードし、ArticleImage に保存して差し込み用HTMLを返す。"""
    article = get_object_or_404(Article, pk=article_id)

    f = request.FILES.get("image")
    if not f:
        return JsonResponse({"error": "画像ファイルがありません。"}, status=400)
    if f.size > MAX_UPLOAD_BYTES:
        return JsonResponse(
            {"error": f"ファイルが大きすぎます（上限 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB）。"},
            status=400)
    if f.content_type not in ALLOWED_CONTENT_TYPES:
        return JsonResponse(
            {"error": f"対応していない形式です（{f.content_type}）。"}, status=400)

    alt = (request.POST.get("alt_text") or "").strip()[:200]
    caption = (request.POST.get("caption") or "").strip()[:200]

    last = (ArticleImage.objects.filter(article=article)
            .order_by("-order").values_list("order", flat=True).first())
    img = ArticleImage.objects.create(
        article=article, image=f, alt_text=alt, caption=caption,
        order=(last or 0) + 1,
    )
    return JsonResponse({
        "id": img.pk,
        "url": img.image.url,
        "alt": img.alt_text,
        "caption": img.caption,
        "html": _figure_html(img, img.alt_text, img.caption),
    })


@staff_member_required
def list_article_images(request, article_id):
    """この記事にアップロード済みの画像一覧（差し込みライブラリ用）。"""
    article = get_object_or_404(Article, pk=article_id)
    items = [{
        "id": im.pk,
        "url": im.image.url,
        "alt": im.alt_text,
        "caption": im.caption,
        "html": _figure_html(im, im.alt_text, im.caption),
    } for im in article.images.all() if im.image]
    return JsonResponse({"images": items})


@staff_member_required
@require_POST
def update_article_image(request, image_id):
    """既存画像の alt / キャプションを更新（エディタのライブラリから編集する）。"""
    im = get_object_or_404(ArticleImage, pk=image_id)
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "不正なリクエストです。"}, status=400)
    im.alt_text = (data.get("alt_text") or "").strip()[:200]
    im.caption = (data.get("caption") or "").strip()[:200]
    im.save(update_fields=["alt_text", "caption"])
    return JsonResponse({
        "id": im.pk, "url": im.image.url, "alt": im.alt_text,
        "caption": im.caption,
        "html": _figure_html(im, im.alt_text, im.caption),
    })
