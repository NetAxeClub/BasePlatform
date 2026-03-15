from django.db import migrations, models


def copy_legacy_collection_rules(apps, schema_editor):
    LegacyCollectionRule = apps.get_model("automation", "CollectionRule")
    LegacyCollectionMatchRule = apps.get_model("automation", "CollectionMatchRule")
    DeviceCollectionRule = apps.get_model("device_api", "DeviceCollectionRule")
    DeviceCollectionMatchRule = apps.get_model("device_api", "DeviceCollectionMatchRule")

    rule_id_map = {}
    for legacy_rule in LegacyCollectionRule.objects.all().iterator():
        new_rule, _ = DeviceCollectionRule.objects.update_or_create(
            id=legacy_rule.id,
            defaults={
                "name": legacy_rule.name,
                "operation": legacy_rule.operation,
                "module": legacy_rule.module,
                "method": legacy_rule.method,
                "execute": legacy_rule.execute,
                "plugin": legacy_rule.plugin,
            },
        )
        rule_id_map[legacy_rule.id] = new_rule.id

    for legacy_match_rule in LegacyCollectionMatchRule.objects.all().iterator():
        DeviceCollectionMatchRule.objects.update_or_create(
            id=legacy_match_rule.id,
            defaults={
                "name": legacy_match_rule.name,
                "fields": legacy_match_rule.fields,
                "operator": legacy_match_rule.operator,
                "value": legacy_match_rule.value,
                "rule_id": rule_id_map.get(legacy_match_rule.rule_id),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0005_alter_autoflow_commit_time"),
        ("device_api", "0006_auto_20260315_0324"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceCollectionRule",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, default="", max_length=100, null=True, verbose_name="规则名")),
                ("operation", models.CharField(blank=True, default="", max_length=50, null=True, verbose_name="运算符")),
                ("module", models.CharField(choices=[("BASE", "基础平台"), ("SouthDriver", "南向驱动")], default="BASE", max_length=50, verbose_name="执行模块")),
                ("method", models.CharField(choices=[("NETCONF", "NETCONF"), ("CLI", "CLI"), ("REST_API", "REST_API")], default="CLI", max_length=50, verbose_name="执行方法")),
                ("execute", models.TextField(blank=True, default="", verbose_name="执行内容")),
                ("plugin", models.CharField(default="", max_length=50, verbose_name="解析插件标识")),
            ],
            options={
                "verbose_name": "采集规则",
                "verbose_name_plural": "采集规则",
                "db_table": "device_api_collection_rule",
            },
        ),
        migrations.CreateModel(
            name="DeviceCollectionMatchRule",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=10, verbose_name="规则名")),
                ("fields", models.CharField(blank=True, default="", max_length=50, null=True, verbose_name="匹配字段")),
                ("operator", models.CharField(blank=True, choices=[("__exact", "精确匹配"), ("__iexact", "不区分大小写的精确匹配"), ("__contains", "包含指定值"), ("__icontains", "不区分大小写包含指定值"), ("__startswith", "以指定值开头"), ("__endswith", "以指定值结尾"), ("__istartswith", "不区分大小写以指定值开头"), ("__iendswith", "不区分大小写以指定值结尾")], default="__exact", max_length=50, null=True, verbose_name="操作符")),
                ("value", models.CharField(blank=True, default="", max_length=50, null=True, verbose_name="匹配值")),
                ("rule", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="match_rule", to="device_api.devicecollectionrule")),
            ],
            options={
                "verbose_name": "采集规则匹配项",
                "verbose_name_plural": "采集规则匹配项",
                "db_table": "device_api_collection_match_rule",
                "unique_together": {("rule", "name")},
            },
        ),
        migrations.AddIndex(
            model_name="devicecollectionrule",
            index=models.Index(fields=["id"], name="device_api__id_4eec09_idx"),
        ),
        migrations.AddIndex(
            model_name="devicecollectionmatchrule",
            index=models.Index(fields=["id"], name="device_api__id_cc0808_idx"),
        ),
        migrations.RunPython(copy_legacy_collection_rules, migrations.RunPython.noop),
    ]
