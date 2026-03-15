from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WorkflowExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_id", models.IntegerField(blank=True, db_index=True, null=True, verbose_name="legacy执行ID")),
                ("task_id", models.CharField(default="", max_length=128, verbose_name="任务ID")),
                ("origin", models.CharField(default="运维平台", max_length=128, verbose_name="来源")),
                ("task_result", models.TextField(default=None, editable=False, null=True, verbose_name="任务结果")),
                ("order_code", models.CharField(blank=True, max_length=128, null=True, verbose_name="工单")),
                ("device", models.GenericIPAddressField(blank=True, null=True, verbose_name="设备IP")),
                ("device_id", models.IntegerField(blank=True, null=True, verbose_name="设备ID")),
                ("commit_user", models.CharField(default="", max_length=42, verbose_name="申请用户")),
                ("commit_time", models.DateTimeField(default=django.utils.timezone.localtime, verbose_name="更新时间")),
                ("task", models.CharField(choices=[("DNAT", "DNAT"), ("SNAT", "SNAT"), ("安全策略", "安全策略"), ("QOS", "QOS"), ("SLB负载均衡", "SLB负载均衡"), ("一键封堵", "一键封堵"), ("地址对象", "地址对象"), ("服务对象", "服务对象"), ("一键切换", "一键切换"), ("巡检", "巡检")], default="", max_length=128, verbose_name="任务模块")),
                ("method", models.CharField(choices=[("NETCONF", "NETCONF"), ("SSH", "SSH"), ("RESTAPI", "RESTAPI")], default="", max_length=128, verbose_name="配置模式")),
                ("class_method", models.CharField(default="", max_length=128, verbose_name="类方法")),
                ("remote_ip", models.CharField(blank=True, max_length=128, null=True, verbose_name="调用IP")),
                ("event", models.IntegerField(blank=True, null=True, verbose_name="关联事件ID")),
                ("kwargs", models.TextField(blank=True, default="{}", verbose_name="任务参数")),
                ("ttp", models.TextField(blank=True, default="{}", verbose_name="结果解析")),
                ("commands", models.TextField(blank=True, default="[]", verbose_name="下发命令")),
                ("back_off_commands", models.TextField(blank=True, default="[]", verbose_name="回退命令")),
                ("state", models.CharField(choices=[("Draft", "Draft"), ("Approved", "Approved"), ("Published", "Published"), ("Failed", "Failed"), ("BackOff", "BackOff"), ("Finish", "Finish")], default="Draft", max_length=200, verbose_name="流程状态")),
                ("code", models.IntegerField(blank=True, default=9000, null=True, verbose_name="状态码")),
            ],
            options={
                "verbose_name": "工作流执行",
                "verbose_name_plural": "工作流执行",
                "db_table": "workflow_center_execution",
            },
        ),
        migrations.CreateModel(
            name="WorkflowHostVar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_id", models.IntegerField(blank=True, db_index=True, null=True, verbose_name="legacy主机变量ID")),
                ("name", models.CharField(blank=True, max_length=100, null=True, verbose_name="主机名")),
                ("host", models.GenericIPAddressField(blank=True, max_length=100, null=True, verbose_name="主机IP")),
                ("variables", models.TextField(blank=True, null=True, verbose_name="主机变量")),
                ("object_name", models.CharField(blank=True, max_length=100, null=True, verbose_name="对象名")),
                ("description", models.CharField(blank=True, max_length=128, null=True, verbose_name="描述")),
                ("task", models.CharField(choices=[("DNAT", "DNAT"), ("SNAT", "SNAT"), ("安全策略", "安全策略"), ("QOS", "QOS"), ("SLB负载均衡", "SLB负载均衡"), ("地址对象", "地址对象"), ("服务对象", "服务对象")], default="地址对象", max_length=64, verbose_name="模块")),
            ],
            options={
                "verbose_name": "工作流主机变量",
                "verbose_name_plural": "工作流主机变量",
                "db_table": "workflow_center_host_var",
            },
        ),
        migrations.CreateModel(
            name="WorkflowInventory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_id", models.IntegerField(blank=True, db_index=True, null=True, verbose_name="legacy库存ID")),
                ("name", models.CharField(max_length=32, unique=True, verbose_name="任务名称")),
                ("variables", models.TextField(blank=True, null=True, verbose_name="组变量")),
                ("description", models.TextField(blank=True, null=True, verbose_name="组描述")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="添加时间")),
                ("task", models.CharField(choices=[("一键封堵", "一键封堵"), ("网络打通", "网络打通"), ("巡检", "巡检")], default="一键封堵", max_length=64, verbose_name="任务模块")),
                ("hosts", models.ManyToManyField(related_name="inventories", to="workflow_center.WorkflowHostVar", verbose_name="组内主机")),
            ],
            options={
                "verbose_name": "工作流库存",
                "verbose_name_plural": "工作流库存",
                "db_table": "workflow_center_inventory",
            },
        ),
    ]
