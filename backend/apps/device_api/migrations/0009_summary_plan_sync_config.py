from django.db import migrations, models


def backfill_summary_plan_sync_config(apps, schema_editor):
    DeviceCollectionPlans = apps.get_model("device_api", "DeviceCollectionPlans")
    DeviceSubCollectionPlan = apps.get_model("device_api", "DeviceSubCollectionPlan")

    for summary_plan in DeviceCollectionPlans.objects.all().iterator():
        sub_plans = list(
            DeviceSubCollectionPlan.objects.filter(summary_plan_id=summary_plan.id).iterator()
        )

        enabled_types = []
        netmiko_enabled = False
        netconf_enabled = False

        for sub_plan in sub_plans:
            if sub_plan.netmiko_enabled:
                netmiko_enabled = True
            if sub_plan.netconf_enabled:
                netconf_enabled = True

            has_any_protocol_enabled = any(
                [
                    sub_plan.netmiko_enabled,
                    sub_plan.netconf_enabled,
                    sub_plan.snmp_enabled,
                    sub_plan.restconf_enabled,
                    sub_plan.telemetry_enabled,
                ]
            )
            if has_any_protocol_enabled and sub_plan.collection_type not in enabled_types:
                enabled_types.append(sub_plan.collection_type)

        if not enabled_types:
            for sub_plan in sub_plans:
                if sub_plan.collection_type and sub_plan.collection_type not in enabled_types:
                    enabled_types.append(sub_plan.collection_type)

        if netmiko_enabled and netconf_enabled:
            collection_method = "both"
        elif netconf_enabled:
            collection_method = "netconf"
        else:
            collection_method = "netmiko"

        summary_plan.enabled_collection_types = enabled_types
        summary_plan.collection_method = collection_method
        summary_plan.save(
            update_fields=["enabled_collection_types", "collection_method"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("device_api", "0008_legacy_rule_mapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicecollectionplans",
            name="collection_method",
            field=models.CharField(
                choices=[
                    ("netmiko", "仅 Netmiko"),
                    ("netconf", "仅 NETCONF"),
                    ("both", "Netmiko + NETCONF"),
                ],
                default="netmiko",
                max_length=16,
                verbose_name="方案级采集方式",
            ),
        ),
        migrations.AddField(
            model_name="devicecollectionplans",
            name="enabled_collection_types",
            field=models.JSONField(blank=True, default=list, verbose_name="启用的采集类型"),
        ),
        migrations.RunPython(
            backfill_summary_plan_sync_config,
            migrations.RunPython.noop,
        ),
    ]
