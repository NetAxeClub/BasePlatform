from django.db import migrations, models
from django.utils import timezone


def backfill_plan_binding_serial_num(apps, schema_editor):
    NetworkDevice = apps.get_model("asset", "NetworkDevice")
    PlansToDevice = apps.get_model("device_api", "PlansToDevice")

    device_map = {
        item["manage_ip"]: item
        for item in NetworkDevice.objects.values("manage_ip", "serial_num")
    }

    for relation in PlansToDevice.objects.all().iterator():
        mapped = device_map.get(relation.manage_ip, {})
        serial_num = mapped.get("serial_num") or relation.manage_ip or f"binding-{relation.id}"
        update_fields = []
        if relation.device_serial_num != serial_num:
            relation.device_serial_num = serial_num
            update_fields.append("device_serial_num")
        if relation.last_bound_at is None:
            relation.last_bound_at = timezone.now()
            update_fields.append("last_bound_at")
        if update_fields:
            relation.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('device_api', '0005_planstodevice_use_local_execute_node'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64, unique=True, verbose_name='画像编码')),
                ('vendor_alias', models.CharField(max_length=30, verbose_name='厂商别名')),
                ('category', models.CharField(blank=True, default='', max_length=30, verbose_name='设备类型')),
                ('series_patterns', models.JSONField(blank=True, default=list, verbose_name='型号匹配规则')),
                ('os_family', models.CharField(blank=True, default='', max_length=64, verbose_name='操作系统族')),
                ('version_patterns', models.JSONField(blank=True, default=list, verbose_name='版本匹配规则')),
                ('preferred_methods', models.JSONField(blank=True, default=dict, verbose_name='优先采集协议')),
                ('fallback_methods', models.JSONField(blank=True, default=dict, verbose_name='回退采集协议')),
                ('supported_collection_types', models.JSONField(blank=True, default=list, verbose_name='支持的采集类型')),
                ('default_plan_name', models.CharField(blank=True, default='', max_length=100, verbose_name='默认方案名')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '平台画像',
                'verbose_name_plural': '平台画像',
                'db_table': 'device_api_platform_profile',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='DeviceDiscoveryState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_serial_num', models.CharField(max_length=200, unique=True, verbose_name='设备序列号')),
                ('manage_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='管理IP')),
                ('profile_code', models.CharField(blank=True, default='', max_length=64, verbose_name='画像编码')),
                ('last_discovered_at', models.DateTimeField(blank=True, null=True, verbose_name='最近发现时间')),
                ('last_discovery_status', models.CharField(blank=True, default='pending', max_length=20, verbose_name='最近发现状态')),
                ('last_discovery_error', models.TextField(blank=True, default='', verbose_name='最近发现错误')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '设备发现状态',
                'verbose_name_plural': '设备发现状态',
                'db_table': 'device_api_device_discovery_state',
            },
        ),
        migrations.AddField(
            model_name='devicecollectionplans',
            name='generated_by_system',
            field=models.BooleanField(default=False, verbose_name='是否系统生成'),
        ),
        migrations.AddField(
            model_name='devicecollectionplans',
            name='is_default',
            field=models.BooleanField(default=False, verbose_name='是否默认方案'),
        ),
        migrations.AddField(
            model_name='devicecollectionplans',
            name='plan_kind',
            field=models.CharField(choices=[('template', '模板方案'), ('runtime', '运行时方案')], default='runtime', max_length=16, verbose_name='方案类型'),
        ),
        migrations.AddField(
            model_name='devicecollectionplans',
            name='profile_code',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='画像编码'),
        ),
        migrations.AddField(
            model_name='devicecollectionplans',
            name='version',
            field=models.PositiveIntegerField(default=1, verbose_name='方案版本'),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='binding_source',
            field=models.CharField(choices=[('auto', '自动绑定'), ('manual', '手工绑定'), ('legacy_bridge', '旧链路桥接')], default='manual', max_length=20, verbose_name='绑定来源'),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='device_serial_num',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='设备序列号'),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否启用'),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='last_bound_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='最近绑定时间'),
        ),
        migrations.AddField(
            model_name='planstodevice',
            name='profile_code',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='画像编码'),
        ),
        migrations.RunPython(backfill_plan_binding_serial_num, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='devicecollectionplans',
            index=models.Index(fields=['profile_code', 'device_type'], name='device_api__profile_a0710c_idx'),
        ),
        migrations.AddIndex(
            model_name='devicecollectionplans',
            index=models.Index(fields=['vendor', 'is_default'], name='device_api__vendor_7d5188_idx'),
        ),
        migrations.AddIndex(
            model_name='planstodevice',
            index=models.Index(fields=['device_serial_num', 'is_active'], name='device_api__device__e49f52_idx'),
        ),
        migrations.AddIndex(
            model_name='planstodevice',
            index=models.Index(fields=['manage_ip', 'profile_code'], name='device_api__manage__8c645e_idx'),
        ),
        migrations.AddConstraint(
            model_name='planstodevice',
            constraint=models.UniqueConstraint(fields=('device_serial_num', 'plan'), name='uniq_device_api_plan_binding'),
        ),
        migrations.AddIndex(
            model_name='platformprofile',
            index=models.Index(fields=['vendor_alias', 'category'], name='device_api__vendor__6b4cfb_idx'),
        ),
        migrations.AddIndex(
            model_name='platformprofile',
            index=models.Index(fields=['is_active'], name='device_api__is_acti_adbd99_idx'),
        ),
        migrations.AddIndex(
            model_name='devicediscoverystate',
            index=models.Index(fields=['manage_ip'], name='device_api__manage__2562f3_idx'),
        ),
        migrations.AddIndex(
            model_name='devicediscoverystate',
            index=models.Index(fields=['profile_code', 'last_discovery_status'], name='device_api__profile_4b1d8e_idx'),
        ),
    ]
