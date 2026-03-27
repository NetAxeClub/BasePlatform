from django.db import migrations, models


TRUNCATED_COLLECTION_TYPE = "cli_output_capabilit"
FULL_COLLECTION_TYPE = "cli_output_capability"
MERGEABLE_FIELDS = (
    "description",
    "netmiko_enabled",
    "netmiko_method",
    "netmiko_path",
    "netmiko_field_mappings",
    "netmiko_processor_enabled",
    "netmiko_processor",
    "netconf_enabled",
    "netconf_path",
    "netconf_field_mappings",
    "netconf_processor_enabled",
    "netconf_processor",
    "snmp_enabled",
    "snmp_version",
    "snmp_oids",
    "snmp_path",
    "snmp_field_mappings",
    "snmp_processor_enabled",
    "snmp_processor",
    "restconf_enabled",
    "restconf_endpoint",
    "restconf_method",
    "restconf_path",
    "restconf_field_mappings",
    "restconf_processor_enabled",
    "restconf_processor",
    "telemetry_enabled",
    "telemetry_subscription_path",
    "telemetry_sampling_interval",
    "telemetry_data_format",
    "telemetry_path",
    "telemetry_field_mappings",
    "telemetry_processor_enabled",
    "telemetry_processor",
    "textfsm_template",
)


def _has_meaningful_value(value):
    if value in (None, "", [], {}):
        return False
    if isinstance(value, bool):
        return value
    return True


def _meaningful_score(instance):
    return sum(1 for field_name in MERGEABLE_FIELDS if _has_meaningful_value(getattr(instance, field_name, None)))


def normalize_cli_output_collection_type(apps, schema_editor):
    DeviceSubCollectionPlan = apps.get_model("device_api", "DeviceSubCollectionPlan")
    NetconfXMLTemplate = apps.get_model("device_api", "NetconfXMLTemplate")

    DeviceSubCollectionPlan.objects.filter(
        collection_type=TRUNCATED_COLLECTION_TYPE
    ).update(collection_type=FULL_COLLECTION_TYPE)

    summary_plan_ids = list(
        DeviceSubCollectionPlan.objects.filter(collection_type=FULL_COLLECTION_TYPE)
        .values_list("summary_plan_id", flat=True)
        .distinct()
    )
    for summary_plan_id in summary_plan_ids:
        sub_plans = list(
            DeviceSubCollectionPlan.objects.filter(
                summary_plan_id=summary_plan_id,
                collection_type=FULL_COLLECTION_TYPE,
            ).order_by("id")
        )
        if len(sub_plans) < 2:
            continue

        sub_plans.sort(key=lambda item: (-_meaningful_score(item), item.id))
        keeper = sub_plans[0]
        update_fields = []
        for duplicate in sub_plans[1:]:
            for field_name in MERGEABLE_FIELDS:
                current_value = getattr(keeper, field_name, None)
                duplicate_value = getattr(duplicate, field_name, None)
                if _has_meaningful_value(current_value) or not _has_meaningful_value(duplicate_value):
                    continue
                setattr(keeper, field_name, duplicate_value)
                if field_name not in update_fields:
                    update_fields.append(field_name)

            duplicate_templates = NetconfXMLTemplate.objects.filter(collection_plan_id=duplicate.id).order_by("id")
            for template in duplicate_templates:
                exists = NetconfXMLTemplate.objects.filter(
                    collection_plan_id=keeper.id,
                    collect_method=template.collect_method,
                ).exists()
                if exists:
                    template.delete()
                    continue
                template.collection_plan_id = keeper.id
                template.save(update_fields=["collection_plan"])

            duplicate.delete()

        if update_fields:
            keeper.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("device_api", "0012_align_summary_plan_vendor_with_asset_vendor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devicesubcollectionplan",
            name="collection_type",
            field=models.CharField(default="arp", max_length=32, verbose_name="采集类型"),
        ),
        migrations.RunPython(
            normalize_cli_output_collection_type,
            migrations.RunPython.noop,
        ),
    ]
