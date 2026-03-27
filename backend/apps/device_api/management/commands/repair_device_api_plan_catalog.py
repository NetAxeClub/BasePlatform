import json
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder

from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan, NetconfXMLTemplate
from apps.device_api.services_new import DeviceCollectionService


MERGEABLE_SUB_PLAN_FIELDS = (
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


class Command(BaseCommand):
    help = "审计并修复 device_api 父方案命名混用、collection_type 截断和重复子方案问题。"

    def add_arguments(self, parser):
        parser.add_argument("--plan-name", dest="plan_name", help="仅处理指定父方案名称")
        parser.add_argument("--vendor", dest="vendor", help="仅处理指定厂商")
        parser.add_argument("--fix", action="store_true", help="执行修复；默认仅审计")
        parser.add_argument("--sample-limit", type=int, default=20, help="输出样例数量上限")
        parser.add_argument("--output", dest="output", help="将完整结果写入 JSON 文件")

    def _get_collection_type_column_length(self):
        table_name = DeviceSubCollectionPlan._meta.db_table
        column_name = "collection_type"
        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SHOW COLUMNS FROM {table_name} LIKE %s",
                    [column_name],
                )
                row = cursor.fetchone()
            if not row:
                return 0
            match = re.search(r"varchar\((\d+)\)", str(row[1]), re.IGNORECASE)
            return int(match.group(1)) if match else 0

        with connection.cursor() as cursor:
            for column in connection.introspection.get_table_description(cursor, table_name):
                if column.name == column_name:
                    return int(getattr(column, "internal_size", 0) or 0)
        return 0

    @staticmethod
    def _migration_0013_applied():
        return MigrationRecorder.Migration.objects.filter(
            app="device_api",
            name="0013_expand_sub_plan_collection_type_length",
        ).exists()

    @staticmethod
    def _sub_plan_score(sub_plan):
        score = 0
        for field_name in MERGEABLE_SUB_PLAN_FIELDS:
            if _has_meaningful_value(getattr(sub_plan, field_name, None)):
                score += 1
        if any(
            bool(getattr(sub_plan, field_name, False))
            for field_name in (
                "netmiko_enabled",
                "netconf_enabled",
                "snmp_enabled",
                "restconf_enabled",
                "telemetry_enabled",
            )
        ):
            score += 4
        score += sub_plan.xml_templates.count()
        return score

    def _pick_keeper(self, sub_plans, normalized_type):
        return sorted(
            sub_plans,
            key=lambda item: (
                0 if item.collection_type == normalized_type else 1,
                -self._sub_plan_score(item),
                item.id,
            ),
        )[0]

    def _merge_duplicate_sub_plans(self, keeper, duplicates):
        merged_fields = []
        deleted_ids = []
        moved_templates = 0

        for duplicate in duplicates:
            for field_name in MERGEABLE_SUB_PLAN_FIELDS:
                current_value = getattr(keeper, field_name, None)
                duplicate_value = getattr(duplicate, field_name, None)
                if _has_meaningful_value(current_value) or not _has_meaningful_value(duplicate_value):
                    continue
                setattr(keeper, field_name, duplicate_value)
                if field_name not in merged_fields:
                    merged_fields.append(field_name)

            duplicate_templates = NetconfXMLTemplate.objects.filter(
                collection_plan_id=duplicate.id
            ).order_by("id")
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
                moved_templates += 1

            deleted_ids.append(duplicate.id)
            duplicate.delete()

        if merged_fields:
            keeper.save(update_fields=merged_fields + ["updated_at"])

        return {
            "deleted_ids": deleted_ids,
            "moved_templates": moved_templates,
            "merged_fields": merged_fields,
        }

    def handle(self, *args, **options):
        plan_name = str(options.get("plan_name") or "").strip()
        vendor = str(options.get("vendor") or "").strip()
        fix = bool(options.get("fix"))
        sample_limit = options.get("sample_limit") or 20

        expected_length = DeviceSubCollectionPlan._meta.get_field("collection_type").max_length or 0
        actual_length = self._get_collection_type_column_length()
        migration_applied = self._migration_0013_applied()
        schema_ready = actual_length >= expected_length

        queryset = DeviceCollectionPlans.objects.all().order_by("id").prefetch_related(
            "collect_plans__xml_templates"
        )
        if plan_name:
            queryset = queryset.filter(name=plan_name)
        if vendor:
            queryset = queryset.filter(vendor__in=DeviceCollectionPlans.resolve_vendor_variants(vendor))

        summary = {
            "plans_scanned": queryset.count(),
            "plan_names_normalized": 0,
            "legacy_collection_type_rows": 0,
            "duplicate_sub_plan_rows": 0,
            "sub_plan_rows_deleted": 0,
            "sub_plan_rows_merged": 0,
            "sub_plan_collection_types_normalized": 0,
            "schema_blocked_collection_type_normalization": 0,
            "schema_ready": schema_ready,
            "schema_actual_length": actual_length,
            "schema_expected_length": expected_length,
            "migration_0013_applied": migration_applied,
        }
        results = []

        for plan in queryset:
            item = {
                "plan_id": plan.id,
                "plan_name": plan.name,
                "vendor_before": plan.vendor,
                "device_type_before": plan.device_type,
                "vendor_after": plan.vendor,
                "device_type_after": plan.device_type,
                "sub_plan_actions": [],
            }

            normalized_vendor = DeviceCollectionPlans.normalize_vendor_value(plan.vendor)
            normalized_device_type = DeviceCollectionPlans.normalize_device_type_value(plan.device_type)
            naming_changed = (
                plan.vendor != normalized_vendor or plan.device_type != normalized_device_type
            )
            if naming_changed and fix:
                with transaction.atomic():
                    if plan.vendor != normalized_vendor:
                        plan.vendor = normalized_vendor
                    if plan.device_type != normalized_device_type:
                        plan.device_type = normalized_device_type
                    plan.save(update_fields=["vendor", "device_type", "updated_at"])
                item["vendor_after"] = plan.vendor
                item["device_type_after"] = plan.device_type
                summary["plan_names_normalized"] += 1
            elif naming_changed:
                item["vendor_after"] = normalized_vendor
                item["device_type_after"] = normalized_device_type

            grouped_sub_plans = defaultdict(list)
            for sub_plan in plan.collect_plans.all():
                normalized_type = DeviceCollectionService.normalize_sub_plan_collection_type(
                    sub_plan.collection_type
                )
                grouped_sub_plans[normalized_type].append(sub_plan)

            for normalized_type, sub_plans in grouped_sub_plans.items():
                legacy_rows = [
                    sub_plan
                    for sub_plan in sub_plans
                    if sub_plan.collection_type != normalized_type
                ]
                duplicates = max(len(sub_plans) - 1, 0)
                if not legacy_rows and not duplicates:
                    continue

                summary["legacy_collection_type_rows"] += len(legacy_rows)
                summary["duplicate_sub_plan_rows"] += duplicates
                keeper = self._pick_keeper(sub_plans, normalized_type)
                action = {
                    "normalized_collection_type": normalized_type,
                    "current_collection_types": [sub_plan.collection_type for sub_plan in sub_plans],
                    "sub_plan_ids": [sub_plan.id for sub_plan in sub_plans],
                    "keeper_id": keeper.id,
                    "duplicates": duplicates,
                    "normalized": False,
                    "schema_blocked": False,
                    "deleted_ids": [],
                    "merged_fields": [],
                }

                if fix:
                    with transaction.atomic():
                        if keeper.collection_type != normalized_type:
                            if schema_ready:
                                keeper.collection_type = normalized_type
                                keeper.save(update_fields=["collection_type", "updated_at"])
                                action["normalized"] = True
                                summary["sub_plan_collection_types_normalized"] += 1
                            else:
                                action["schema_blocked"] = True
                                summary["schema_blocked_collection_type_normalization"] += 1

                        duplicate_rows = [sub_plan for sub_plan in sub_plans if sub_plan.id != keeper.id]
                        if duplicate_rows:
                            merge_result = self._merge_duplicate_sub_plans(keeper, duplicate_rows)
                            action["deleted_ids"] = merge_result["deleted_ids"]
                            action["merged_fields"] = merge_result["merged_fields"]
                            summary["sub_plan_rows_deleted"] += len(merge_result["deleted_ids"])
                            summary["sub_plan_rows_merged"] += len(merge_result["deleted_ids"])

                item["sub_plan_actions"].append(action)

            if naming_changed or item["sub_plan_actions"]:
                results.append(item)

        report = {
            "summary": summary,
            "results": results,
        }

        self.stdout.write(
            self.style.SUCCESS(
                "device_api 方案治理审计完成"
                if not fix
                else "device_api 方案治理修复完成"
            )
        )
        self.stdout.write(
            "summary: "
            f"plans_scanned={summary['plans_scanned']} "
            f"plan_names_normalized={summary['plan_names_normalized']} "
            f"legacy_collection_type_rows={summary['legacy_collection_type_rows']} "
            f"duplicate_sub_plan_rows={summary['duplicate_sub_plan_rows']} "
            f"sub_plan_rows_deleted={summary['sub_plan_rows_deleted']} "
            f"schema_ready={summary['schema_ready']} "
            f"schema_actual_length={summary['schema_actual_length']} "
            f"migration_0013_applied={summary['migration_0013_applied']}"
        )

        if not results:
            self.stdout.write("samples: none")
        else:
            self.stdout.write("samples:")
            for item in results[:sample_limit]:
                self.stdout.write(
                    "- "
                    f"plan={item['plan_name']}#{item['plan_id']} "
                    f"vendor={item['vendor_before']}->{item['vendor_after']} "
                    f"device_type={item['device_type_before']}->{item['device_type_after']} "
                    f"sub_plan_actions={len(item['sub_plan_actions'])}"
                )

        output = options.get("output")
        if output:
            output_path = Path(output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.stdout.write(f"report written: {output_path}")
