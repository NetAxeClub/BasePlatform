# 方案与设备关联：增加 use_local（默认本地采集）与 execute_node（南向驱动节点）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('device_api', '0004_sub_plan_collection_enabled_default_false'),
    ]

    operations = [
        migrations.AddField(
            model_name='planstodevice',
            name='use_local',
            field=models.BooleanField(
                default=True,
                help_text='默认True表示本地采集；设为False时使用南向驱动，由 execute_node 指定执行节点',
                verbose_name='使用本地采集',
            ),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='execute_node',
            field=models.CharField(
                blank=True,
                default='',
                help_text='仅当 use_local=False 时生效，指定南向驱动节点地址或标识',
                max_length=200,
                verbose_name='南向驱动执行节点',
            ),
        ),
    ]
