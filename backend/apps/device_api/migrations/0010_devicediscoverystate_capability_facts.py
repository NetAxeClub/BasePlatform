from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("device_api", "0009_summary_plan_sync_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicediscoverystate",
            name="capability_facts",
            field=models.JSONField(blank=True, default=dict, verbose_name="能力画像事实"),
        ),
    ]
