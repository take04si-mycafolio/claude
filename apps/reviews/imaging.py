"""アップロード画像の圧縮ユーティリティ。

投稿された画像をそのまま保存せず、長辺をリサイズしたうえで WebP に再エンコード
してデータ量を大幅に削減する。EXIF の回転情報を反映してからメタデータは破棄する。

口コミ画像はここで直接 WebP 化するため、プロジェクト共通の「全 ImageField を
WebP 変換する pre_save シグナル」(apps/products/signals_webp.py) は ReviewImage に
対して無効化している（二重エンコード回避。ReviewsConfig.ready 参照）。
"""
import io
import time

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

# 既定の圧縮パラメータ
MAX_SIDE = 1600   # 長辺の最大ピクセル
QUALITY = 82      # WebP 品質
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 受け付ける元ファイルの上限(15MB)


def compress_image(uploaded, max_side: int = MAX_SIDE, quality: int = QUALITY) -> ContentFile:
    """アップロードファイルを圧縮した WebP の ContentFile にして返す。

    - EXIF の向きを反映
    - 透過画像は透過を維持（それ以外は RGB）
    - 長辺を max_side 以内に縮小（拡大はしない）
    - WebP で再エンコードしメタデータを除去
    画像として開けない場合は PIL が例外を送出する。
    """
    img = Image.open(uploaded)
    img = ImageOps.exif_transpose(img)  # 撮影向きを正規化

    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    img = img.convert("RGBA" if has_alpha else "RGB")

    # 長辺を max_side 以内に（元が小さければそのまま）
    img.thumbnail((max_side, max_side), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=quality, method=6)
    buffer.seek(0)

    # 衝突しないタイムスタンプ名にして元ファイル名は持ち越さない
    return ContentFile(buffer.read(), name=f"{time.time_ns()}.webp")
