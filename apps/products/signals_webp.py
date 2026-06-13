"""
ImageField のアップロード時に WebP に自動変換するシグナル。
- 新規アップロード分のみ変換(既存ファイルは触らない)
- quality=80 で圧縮、ファイル名は <ナノ秒タイムスタンプ>.webp に置換
- 変換失敗時はサイレントスキップ(アップロード自体は継続)
"""
import time
from io import BytesIO
from PIL import Image
from django.apps import apps as django_apps
from django.core.files.base import ContentFile
from django.db.models import ImageField
from django.db.models.signals import pre_save

WEBP_QUALITY = 80


def _convert_to_webp(file_obj):
    img = Image.open(file_obj)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        mode = "RGBA"
    else:
        mode = "RGB"
    img = img.convert(mode)
    out = BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    out.seek(0)
    return out


def _process_image_field(instance, field_name):
    field_file = getattr(instance, field_name, None)
    if not field_file:
        return
    # 既存ファイル(新規アップロードでない)はスキップ
    if getattr(field_file, "_committed", True):
        return
    name = field_file.name or ""
    # 既に webp で且つ数字ファイル名ならスキップ
    if name.lower().endswith(".webp") and "/" in name:
        # ファイル名部分だけ抽出して数字判定
        fname_part = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if fname_part.isdigit():
            return
    try:
        f = field_file.file
        f.seek(0)
        webp_io = _convert_to_webp(f)
    except Exception:
        return  # 変換失敗時はサイレントスキップ
    # ファイル名 = ナノ秒タイムスタンプ(衝突しない19桁の数字)
    new_name = f"{time.time_ns()}.webp"
    setattr(instance, field_name, ContentFile(webp_io.getvalue(), name=new_name))


def _make_handler(field_names):
    def handler(sender, instance, **kwargs):
        for fname in field_names:
            _process_image_field(instance, fname)
    return handler


def connect_image_to_webp():
    for model in django_apps.get_models():
        image_fields = [
            f.name for f in model._meta.get_fields()
            if isinstance(f, ImageField)
        ]
        if image_fields:
            handler = _make_handler(image_fields)
            pre_save.connect(
                handler,
                sender=model,
                weak=False,
                dispatch_uid=f"webp_convert_{model._meta.label}",
            )
