import hashlib

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .config import get_survey
from .forms import SurveyResponseForm
from .models import SurveyResponse


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_hash(request):
    ip = _client_ip(request)
    raw = f"{ip}:{settings.SECRET_KEY}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@require_POST
def submit(request, slug):
    """アンケート回答を受け付ける（AJAX / 通常POST両対応、JSONを返す）。

    - honeypot と選択肢バリデーションで最低限の spam を弾く
    - 同一 ip_hash + slug の12時間以内の重複はカウントしない（二重送信対策）
    """
    survey = get_survey(slug)
    if not survey:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    form = SurveyResponseForm(request.POST, survey_slug=slug)
    if not form.is_valid():
        # honeypot 命中時も含めて、攻撃者に成否を悟らせないため ok を返すが保存しない。
        if "website" in form.errors:
            return JsonResponse({"ok": True, "counted": False})
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    ip_hash = _ip_hash(request)
    since = timezone.now() - timezone.timedelta(hours=12)
    dup = SurveyResponse.objects.filter(
        survey_slug=slug, ip_hash=ip_hash, created_at__gte=since
    ).exists()
    if dup:
        return JsonResponse({"ok": True, "counted": False, "duplicate": True})

    SurveyResponse.objects.create(
        survey_slug=slug,
        answers=form.answers,
        reason=form.cleaned_data["reason"],
        ip_hash=ip_hash,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:200],
        # 自由記述があるものは公開前に管理画面で確認するため未承認スタート
        is_approved=False,
    )
    return JsonResponse({"ok": True, "counted": True})
