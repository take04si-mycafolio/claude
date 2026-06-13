"""既存ミッションに「SNSアカウント連携」の達成ステップを追加する。

プロフィールの SNS 項目（X / Instagram / TikTok / YouTube）を1つずつ
ステップ化し、現在公開中の（＝先頭の）ミッションに紐づける。
get_or_create で冪等にしているため再実行しても重複しない。
"""
from django.db import migrations


# (action_type, 表示ラベル, 表示順)
SNS_STEPS = [
    ("sns_twitter", "X(Twitter)を連携しよう", 10),
    ("sns_instagram", "Instagramを連携しよう", 11),
    ("sns_tiktok", "TikTokを連携しよう", 12),
    ("sns_youtube", "YouTubeを連携しよう", 13),
]


def add_sns_steps(apps, schema_editor):
    Mission = apps.get_model("accounts", "Mission")
    MissionStep = apps.get_model("accounts", "MissionStep")
    mission = Mission.objects.order_by("order", "id").first()
    if mission is None:
        return
    for action_type, label, order in SNS_STEPS:
        MissionStep.objects.get_or_create(
            mission=mission,
            action_type=action_type,
            defaults={"label": label, "target_count": 1, "order": order},
        )


def remove_sns_steps(apps, schema_editor):
    MissionStep = apps.get_model("accounts", "MissionStep")
    MissionStep.objects.filter(
        action_type__in=[s[0] for s in SNS_STEPS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_alter_missionstep_action_type"),
    ]

    operations = [
        migrations.RunPython(add_sns_steps, remove_sns_steps),
    ]
