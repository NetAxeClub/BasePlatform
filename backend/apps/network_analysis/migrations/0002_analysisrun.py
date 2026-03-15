from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("network_analysis", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_kind", models.CharField(choices=[("interface_utilization", "接口利用率分析"), ("address_tracking", "地址定位分析"), ("full_refresh", "全量分析")], max_length=32, verbose_name="分析类型")),
                ("target_manage_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="目标设备IP")),
                ("target_ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="目标业务IP")),
                ("triggered_by", models.CharField(blank=True, default="", max_length=100, verbose_name="触发来源")),
                ("status", models.CharField(choices=[("pending", "待执行"), ("running", "执行中"), ("success", "成功"), ("failed", "失败")], default="pending", max_length=20, verbose_name="执行状态")),
                ("summary", models.JSONField(blank=True, default=dict, verbose_name="执行摘要")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="错误信息")),
                ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="开始时间")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="结束时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "db_table": "network_analysis_run",
                "verbose_name": "分析运行记录",
                "verbose_name_plural": "分析运行记录",
            },
        ),
        migrations.AddIndex(
            model_name="analysisrun",
            index=models.Index(fields=["run_kind", "status"], name="network_ana_run_kin_574355_idx"),
        ),
        migrations.AddIndex(
            model_name="analysisrun",
            index=models.Index(fields=["created_at"], name="network_ana_created_5d5ac3_idx"),
        ),
    ]
