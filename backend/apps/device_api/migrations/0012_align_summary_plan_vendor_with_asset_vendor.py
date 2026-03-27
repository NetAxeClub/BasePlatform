from django.db import migrations, models


DEVICE_TYPE_NAME_FALLBACKS = {
    "switch": "交换机",
    "firewall": "防火墙",
    "router": "路由器",
    "tap交换机": "TAP交换机",
    "TAP交换机": "TAP交换机",
}


def normalize_summary_plan_base_fields(apps, schema_editor):
    DeviceCollectionPlans = apps.get_model("device_api", "DeviceCollectionPlans")
    Vendor = apps.get_model("asset", "Vendor")
    Category = apps.get_model("asset", "Category")

    vendor_name_map = {}
    vendor_alias_map = {}
    for vendor in Vendor.objects.all().iterator():
        name = str(getattr(vendor, "name", "") or "").strip()
        alias = str(getattr(vendor, "alias", "") or "").strip()
        if name:
            vendor_name_map[name] = name
        if alias:
            vendor_alias_map[alias] = name

    category_name_map = {}
    for category in Category.objects.all().iterator():
        name = str(getattr(category, "name", "") or "").strip()
        if name:
            category_name_map[name] = name

    for plan in DeviceCollectionPlans.objects.all().iterator():
        current_vendor = str(getattr(plan, "vendor", "") or "").strip()
        current_device_type = str(getattr(plan, "device_type", "") or "").strip()
        update_fields = []

        if current_vendor:
            normalized_vendor = (
                vendor_name_map.get(current_vendor)
                or vendor_alias_map.get(current_vendor)
            )
            if normalized_vendor and normalized_vendor != current_vendor:
                plan.vendor = normalized_vendor
                update_fields.append("vendor")

        if current_device_type:
            normalized_device_type = (
                category_name_map.get(current_device_type)
                or category_name_map.get(DEVICE_TYPE_NAME_FALLBACKS.get(current_device_type, ""))
                or DEVICE_TYPE_NAME_FALLBACKS.get(current_device_type)
            )
            if normalized_device_type and normalized_device_type != current_device_type:
                plan.device_type = normalized_device_type
                update_fields.append("device_type")

        if update_fields:
            plan.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("asset", "0001_initial"),
        ("device_api", "0011_alter_netconfxmltemplate_collect_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devicecollectionplans",
            name="vendor",
            field=models.CharField(max_length=30, verbose_name="厂商"),
        ),
        migrations.RunPython(normalize_summary_plan_base_fields, migrations.RunPython.noop),
    ]
