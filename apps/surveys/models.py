from django.db import models


class SurveyResponse(models.Model):
    """記事アンケートの1回答。survey_slug は apps.surveys.config.SURVEYS のキー。

    設問はアンケートごとに異なるため、選択式の回答は answers(JSON) に
    {question_key: choice_value} で保存する。集計はこの JSON を対象に行う。
    reason(自由記述) の公開表示は is_approved=True のものだけに限定する。
    """

    survey_slug = models.SlugField("アンケート", max_length=64, db_index=True)
    answers = models.JSONField("回答", default=dict, blank=True)
    reason = models.TextField("理由・感想", max_length=300, blank=True)

    is_approved = models.BooleanField(
        "コメント公開可", default=False,
        help_text="自由記述コメントを結果として公開してよい場合にチェック",
    )
    is_deleted = models.BooleanField("削除(集計から除外)", default=False)

    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField("投稿日時", auto_now_add=True)

    class Meta:
        verbose_name = "アンケート回答"
        verbose_name_plural = "アンケート回答"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["survey_slug", "is_deleted"]),
        ]

    def __str__(self):
        return f"{self.survey_slug} ({self.created_at:%Y-%m-%d})"
