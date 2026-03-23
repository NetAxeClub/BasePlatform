from django.db import migrations


SPEED_FIELD_MAP = {
    "int_used_1g": "1G",
    "int_used_10m": "10M",
    "int_used_100m": "100M",
    "int_used_10g": "10G",
    "int_used_20g": "20G",
    "int_used_25g": "25G",
    "int_used_40g": "40G",
    "int_used_100g": "100G",
    "int_used_200g": "200G",
    "int_used_400g": "400G",
    "int_unused_1g": "1G",
    "int_unused_10m": "10M",
    "int_unused_100m": "100M",
    "int_unused_10g": "10G",
    "int_unused_20g": "20G",
    "int_unused_25g": "25G",
    "int_unused_40g": "40G",
    "int_unused_100g": "100G",
    "int_unused_200g": "200G",
    "int_unused_400g": "400G",
}


def _speed_counts(record, prefix):
    counts = {}
    for field_name, speed_name in SPEED_FIELD_MAP.items():
        if not field_name.startswith(prefix):
            continue
        value = getattr(record, field_name, 0) or 0
        if value:
            counts[speed_name] = value
    return counts


def backfill_legacy_interface_used(apps, schema_editor):
    connection = schema_editor.connection
    table_names = connection.introspection.table_names()

    LegacyInterfaceUsed = apps.get_model("int_utilization", "InterfaceUsed")
    Snapshot = apps.get_model("network_analysis", "InterfaceUtilizationSnapshot")
    NetworkDevice = apps.get_model("asset", "NetworkDevice")

    if LegacyInterfaceUsed._meta.db_table not in table_names:
        return

    using = connection.alias
    device_by_ip = {
        row["manage_ip"]: row
        for row in NetworkDevice.objects.using(using).all().values("manage_ip", "name", "serial_num")
    }

    for record in LegacyInterfaceUsed.objects.using(using).all().iterator():
        device = device_by_ip.get(str(record.host_ip))
        device_serial_num = ""
        if device and device.get("serial_num"):
            device_serial_num = device["serial_num"]
        elif record.host_id:
            device_serial_num = str(record.host_id)
        elif record.host_ip:
            device_serial_num = str(record.host_ip)
        else:
            continue

        Snapshot.objects.using(using).update_or_create(
            device_serial_num=device_serial_num,
            component_scope="device",
            component_key="",
            defaults={
                "manage_ip": str(record.host_ip or "0.0.0.0"),
                "device_name": (device or {}).get("name") or record.host or "",
                "component_name": (device or {}).get("name") or record.host or "",
                "dominant_speed": record.host_type or "",
                "total_ports": record.int_total or 0,
                "used_ports": record.int_used or 0,
                "unused_ports": record.int_unused or 0,
                "utilization_percent": record.utilization or 0,
                "used_speed_counts": _speed_counts(record, "int_used_"),
                "unused_speed_counts": _speed_counts(record, "int_unused_"),
                "source_execute_time": record.log_time.strftime("%Y-%m-%d %H:%M:%S") if record.log_time else "",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("int_utilization", "0001_initial"),
        ("network_analysis", "0003_auto_20260319_2335"),
        ("asset", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_interface_used, migrations.RunPython.noop),
    ]
