from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="InterfaceUtilizationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_serial_num", models.CharField(max_length=200, verbose_name="设备序列号")),
                ("manage_ip", models.GenericIPAddressField(verbose_name="管理IP")),
                ("device_name", models.CharField(blank=True, default="", max_length=200, verbose_name="设备名称")),
                ("component_scope", models.CharField(choices=[("device", "设备级"), ("slot", "槽位级"), ("chassis", "机框级")], default="device", max_length=20, verbose_name="分析粒度")),
                ("component_key", models.CharField(blank=True, default="", max_length=50, verbose_name="组件标识")),
                ("component_name", models.CharField(blank=True, default="", max_length=200, verbose_name="组件名称")),
                ("dominant_speed", models.CharField(blank=True, default="", max_length=20, verbose_name="主端口速率")),
                ("total_ports", models.IntegerField(default=0, verbose_name="总端口数")),
                ("used_ports", models.IntegerField(default=0, verbose_name="已使用端口数")),
                ("unused_ports", models.IntegerField(default=0, verbose_name="未使用端口数")),
                ("utilization_percent", models.FloatField(default=0.0, verbose_name="利用率")),
                ("used_speed_counts", models.JSONField(blank=True, default=dict, verbose_name="已使用速率分布")),
                ("unused_speed_counts", models.JSONField(blank=True, default=dict, verbose_name="未使用速率分布")),
                ("source_execute_time", models.CharField(blank=True, default="", max_length=64, verbose_name="源采集批次")),
                ("snapshot_time", models.DateTimeField(auto_now=True, verbose_name="快照时间")),
            ],
            options={"db_table": "network_analysis_interface_utilization", "verbose_name": "接口利用率快照", "verbose_name_plural": "接口利用率快照"},
        ),
        migrations.CreateModel(
            name="AddressTraceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ip_address", models.GenericIPAddressField(verbose_name="目标IP")),
                ("mac_address", models.CharField(blank=True, default="", max_length=64, verbose_name="MAC地址")),
                ("device_serial_num", models.CharField(blank=True, default="", max_length=200, verbose_name="设备序列号")),
                ("manage_ip", models.GenericIPAddressField(verbose_name="接入设备管理IP")),
                ("device_name", models.CharField(blank=True, default="", max_length=200, verbose_name="接入设备名称")),
                ("idc_name", models.CharField(blank=True, default="", max_length=100, verbose_name="机房")),
                ("category_name", models.CharField(blank=True, default="", max_length=100, verbose_name="设备类型")),
                ("node_location", models.CharField(blank=True, default="", max_length=255, verbose_name="设备位置")),
                ("interface_name", models.CharField(blank=True, default="", max_length=255, verbose_name="接入口")),
                ("member_ports", models.JSONField(blank=True, default=list, verbose_name="聚合成员端口")),
                ("trace_status", models.CharField(choices=[("located", "已定位"), ("partial", "部分定位"), ("unresolved", "未定位")], default="unresolved", max_length=20, verbose_name="定位状态")),
                ("trace_method", models.CharField(blank=True, default="", max_length=50, verbose_name="定位方式")),
                ("trace_details", models.JSONField(blank=True, default=dict, verbose_name="定位详情")),
                ("source_execute_time", models.CharField(blank=True, default="", max_length=64, verbose_name="源采集批次")),
                ("observed_at", models.DateTimeField(auto_now=True, verbose_name="观测时间")),
            ],
            options={"db_table": "network_analysis_address_trace", "verbose_name": "地址定位快照", "verbose_name_plural": "地址定位快照"},
        ),
        migrations.AddConstraint(
            model_name="interfaceutilizationsnapshot",
            constraint=models.UniqueConstraint(fields=("device_serial_num", "component_scope", "component_key"), name="uniq_network_analysis_interface_utilization"),
        ),
        migrations.AddConstraint(
            model_name="addresstracesnapshot",
            constraint=models.UniqueConstraint(fields=("ip_address", "manage_ip", "interface_name"), name="uniq_network_analysis_address_trace"),
        ),
        migrations.AddIndex(
            model_name="interfaceutilizationsnapshot",
            index=models.Index(fields=["manage_ip", "snapshot_time"], name="network_ana_manage__239a79_idx"),
        ),
        migrations.AddIndex(
            model_name="interfaceutilizationsnapshot",
            index=models.Index(fields=["component_scope", "utilization_percent"], name="network_ana_compone_2124a5_idx"),
        ),
        migrations.AddIndex(
            model_name="addresstracesnapshot",
            index=models.Index(fields=["ip_address", "trace_status"], name="network_ana_ip_addr_4bf934_idx"),
        ),
        migrations.AddIndex(
            model_name="addresstracesnapshot",
            index=models.Index(fields=["manage_ip", "observed_at"], name="network_ana_manage__7276dd_idx"),
        ),
    ]
