from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("device_api", "0013_expand_sub_plan_collection_type_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicecollectionplans",
            name="recent_failed_device_count",
            field=models.PositiveIntegerField(default=0, verbose_name="最近失败设备数"),
        ),
        migrations.AddField(
            model_name="devicecollectionplans",
            name="recent_validation_status",
            field=models.CharField(
                blank=True,
                default="pending",
                max_length=32,
                verbose_name="最近验证状态",
            ),
        ),
        migrations.AddField(
            model_name="devicesubcollectionplan",
            name="latest_sample_result",
            field=models.TextField(blank=True, default="", verbose_name="最近样例结果"),
        ),
        migrations.AddField(
            model_name="devicesubcollectionplan",
            name="recent_failed_count",
            field=models.PositiveIntegerField(default=0, verbose_name="最近失败数"),
        ),
    ]
