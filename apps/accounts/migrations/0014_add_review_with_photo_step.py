"""既存ミッションに「写真付きで口コミを投稿」の達成ステップを追加する。

現在公開中の（＝先頭の）ミッションに紐づける。get_or_create で冪等。
"""
from django.db import migrations

ACTION = "review_with_photo"
LABEL = "写真付きで口コミを投稿しよう"
ORDER = 5


def add_step(apps, schema_editor):
    Mission = apps.get_model("accounts", "Mission")
    MissionStep = apps.get_model("accounts", "MissionStep")
    mission = Mission.objects.order_by("order", "id").first()
    if mission is None:
        return
    MissionStep.objects.get_or_create(
        mission=mission,
        action_type=ACTION,
        defaults={"label": LABEL, "target_count": 1, "order": ORDER},
    )


def remove_step(apps, schema_editor):
    MissionStep = apps.get_model("accounts", "MissionStep")
    MissionStep.objects.filter(action_type=ACTION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_alter_missionstep_action_type"),
    ]

    operations = [
        migrations.RunPython(add_step, remove_step),
    ]
