import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection

from apps.asset.models import NetworkDevice
from apps.device_api.platform_profiles import PlatformProfileService


class Command(BaseCommand):
    help = "审计 device_api 的画像/默认方案/绑定覆盖，并输出阻塞切换的设备清单。"
    REQUIRED_SCHEMA = {
        "device_api_platform_profile": [],
        "device_api_device_discovery_state": [],
        "device_api_collection_plans": [
            "profile_code",
            "plan_kind",
            "generated_by_system",
            "version",
            "is_default",
            "enabled_collection_types",
            "collection_method",
        ],
        "device_api_plan2device": [
            "device_serial_num",
            "profile_code",
            "binding_source",
            "is_active",
            "last_bound_at",
        ],
    }

    def add_arguments(self, parser):
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅审计指定管理 IP")
        parser.add_argument("--serial-num", dest="serial_num", help="仅审计指定序列号")
        parser.add_argument("--vendor-alias", dest="vendor_alias", help="仅审计指定厂商别名")
        parser.add_argument("--sync-default-plans", action="store_true", help="先同步内置画像和默认方案")
        parser.add_argument("--auto-bind", action="store_true", help="先对筛选后的设备执行自动绑定")
        parser.add_argument("--sample-limit", type=int, default=20, help="输出阻塞样例数量上限")
        parser.add_argument("--output", dest="output", help="将完整审计结果写入 JSON 文件")

    @classmethod
    def collect_schema_blockers(cls):
        cursor = connection.cursor()
        blockers = []
        for table_name, required_columns in cls.REQUIRED_SCHEMA.items():
            cursor.execute("SHOW TABLES LIKE %s", [table_name])
            exists = cursor.fetchone()
            if not exists:
                blockers.append(
                    {
                        "code": "missing_table",
                        "table": table_name,
                        "message": f"缺少数据表: {table_name}",
                    }
                )
                continue

            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            existing_columns = {row[0] for row in cursor.fetchall()}
            for column_name in required_columns:
                if column_name not in existing_columns:
                    blockers.append(
                        {
                            "code": "missing_column",
                            "table": table_name,
                            "column": column_name,
                            "message": f"缺少字段: {table_name}.{column_name}",
                        }
                    )
        return blockers

    def handle(self, *args, **options):
        queryset = NetworkDevice.objects.filter(status=0, auto_enable=True).select_related(
            "vendor", "category", "model"
        )
        manage_ip = options.get("manage_ip")
        serial_num = options.get("serial_num")
        vendor_alias = options.get("vendor_alias")
        sample_limit = options.get("sample_limit") or 20

        if manage_ip:
            queryset = queryset.filter(manage_ip=manage_ip)
        if serial_num:
            queryset = queryset.filter(serial_num=serial_num)
        if vendor_alias:
            queryset = queryset.filter(vendor__alias=vendor_alias)

        devices = list(queryset)
        schema_blockers = self.collect_schema_blockers()
        schema_ready = not schema_blockers

        if schema_blockers:
            self.stdout.write("schema blockers:")
            for item in schema_blockers:
                self.stdout.write(f"- {item['message']}")

        if options.get("sync_default_plans") and schema_ready:
            profiles = PlatformProfileService.ensure_builtin_profiles()
            synced_count = 0
            for profile in profiles:
                PlatformProfileService.ensure_default_plan_for_profile(profile)
                synced_count += 1
            self.stdout.write(self.style.SUCCESS(f"已同步内置画像和默认方案: {synced_count}"))
        elif options.get("sync_default_plans"):
            self.stdout.write("skip sync_default_plans: schema blockers detected")

        if options.get("auto_bind") and schema_ready:
            bind_result = PlatformProfileService.auto_bind_devices(devices)
            self.stdout.write(self.style.SUCCESS("自动绑定完成"))
            self.stdout.write(
                f"created={bind_result['created']} updated={bind_result['updated']} skipped={bind_result['skipped']}"
            )
        elif options.get("auto_bind"):
            self.stdout.write("skip auto_bind: schema blockers detected")

        if schema_ready:
            audit_result = PlatformProfileService.audit_device_coverage(devices)
        else:
            audit_result = {
                "summary": {
                    "total": len(devices),
                    "ready": 0,
                    "blocked": len(devices),
                    "profile_not_matched": 0,
                    "missing_default_plan": 0,
                    "missing_binding": 0,
                    "schema_blockers": len(schema_blockers),
                },
                "results": [],
                "schema_blockers": schema_blockers,
            }
        summary = audit_result["summary"]
        self.stdout.write(self.style.SUCCESS("device_api 覆盖审计完成"))
        self.stdout.write(
            "summary: "
            f"total={summary['total']} ready={summary['ready']} blocked={summary['blocked']} "
            f"profile_not_matched={summary['profile_not_matched']} "
            f"missing_default_plan={summary['missing_default_plan']} "
            f"missing_binding={summary['missing_binding']}"
        )

        blocked_items = [item for item in audit_result["results"] if item["blockers"]]
        if not blocked_items:
            self.stdout.write("blocked samples: none")
        else:
            self.stdout.write("blocked samples:")
            for item in blocked_items[:sample_limit]:
                blocker_codes = ",".join(blocker["code"] for blocker in item["blockers"])
                self.stdout.write(
                    f"- {item['manage_ip']} serial={item['serial_num']} profile={item['profile_code']} "
                    f"plan={item['plan_name'] or '-'} blockers={blocker_codes}"
                )

        output = options.get("output")
        if output:
            output_path = Path(output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(audit_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.stdout.write(f"report written: {output_path}")
