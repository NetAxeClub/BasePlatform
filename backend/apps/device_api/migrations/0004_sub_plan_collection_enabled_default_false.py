# 子采集方案新建时采集方式默认关闭，由用户在前端按需开启

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_api', '0003_auto_20260109_2317'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicesubcollectionplan',
            name='netmiko_enabled',
            field=models.BooleanField(default=False, verbose_name='启用Netmiko'),
        ),
    ]
