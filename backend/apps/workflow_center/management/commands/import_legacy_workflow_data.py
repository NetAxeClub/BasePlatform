import json

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.workflow_center.models import WorkflowExecution, WorkflowHostVar, WorkflowInventory


class Command(BaseCommand):
    help = "从 legacy automation 物理表导入工作流数据到 workflow_center 新表。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据")
        parser.add_argument("--limit", type=int, default=0, help="限制导入数量")
        parser.add_argument("--execution-table", default="auto_work_flow")
        parser.add_argument("--hostvar-table", default="automation_autovars")
        parser.add_argument("--inventory-table", default="automation_automationinventory")
        parser.add_argument(
            "--inventory-host-table",
            default="automation_automationinventory_ans_group_hosts",
        )
        parser.add_argument("--sample-limit", type=int, default=20, help="输出样例数量上限")

    @staticmethod
    def _fetch_all(cursor, sql):
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _import_rows(execution_rows, hostvar_rows, inventory_rows, inventory_host_rows):
        stats = {
            "executions": {"created": 0, "updated": 0, "samples": []},
            "host_vars": {"created": 0, "updated": 0, "samples": []},
            "inventories": {"created": 0, "updated": 0, "samples": []},
            "inventory_host_links": {"linked": 0, "skipped": 0, "samples": []},
        }

        host_var_map = {}
        inventory_map = {}

        for row in hostvar_rows:
            obj, created = WorkflowHostVar.objects.update_or_create(
                legacy_id=row["id"],
                defaults={
                    "name": row.get("ans_name"),
                    "host": row.get("ans_host"),
                    "variables": row.get("ans_vars"),
                    "object_name": row.get("ans_obj"),
                    "description": row.get("ans_memo"),
                    "task": row.get("task") or WorkflowHostVar._meta.get_field("task").default,
                },
            )
            host_var_map[row["id"]] = obj
            bucket = "created" if created else "updated"
            stats["host_vars"][bucket] += 1
            stats["host_vars"]["samples"].append(
                {"legacy_id": row["id"], "id": getattr(obj, "id", None), "name": row.get("ans_name"), "status": bucket}
            )

        for row in inventory_rows:
            obj, created = WorkflowInventory.objects.update_or_create(
                legacy_id=row["id"],
                defaults={
                    "name": row.get("ans_group_name"),
                    "variables": row.get("ans_group_vars"),
                    "description": row.get("ans_group_memo"),
                    "created_at": row.get("ans_group_datetime"),
                    "task": row.get("task") or WorkflowInventory._meta.get_field("task").default,
                },
            )
            inventory_map[row["id"]] = obj
            bucket = "created" if created else "updated"
            stats["inventories"][bucket] += 1
            stats["inventories"]["samples"].append(
                {"legacy_id": row["id"], "id": getattr(obj, "id", None), "name": row.get("ans_group_name"), "status": bucket}
            )

        for row in inventory_host_rows:
            inventory_obj = inventory_map.get(row.get("automationinventory_id"))
            host_obj = host_var_map.get(row.get("autovars_id"))
            if inventory_obj and host_obj:
                inventory_obj.hosts.add(host_obj)
                stats["inventory_host_links"]["linked"] += 1
                stats["inventory_host_links"]["samples"].append(
                    {
                        "inventory_legacy_id": row.get("automationinventory_id"),
                        "host_legacy_id": row.get("autovars_id"),
                        "status": "linked",
                    }
                )
            else:
                stats["inventory_host_links"]["skipped"] += 1
                stats["inventory_host_links"]["samples"].append(
                    {
                        "inventory_legacy_id": row.get("automationinventory_id"),
                        "host_legacy_id": row.get("autovars_id"),
                        "status": "skipped",
                    }
                )

        for row in execution_rows:
            obj, created = WorkflowExecution.objects.update_or_create(
                legacy_id=row["id"],
                defaults={
                    "task_id": row.get("task_id") or "",
                    "origin": row.get("origin") or "",
                    "task_result": row.get("task_result"),
                    "order_code": row.get("order_code"),
                    "device": row.get("device"),
                    "device_id": row.get("device_id"),
                    "commit_user": row.get("commit_user") or "",
                    "commit_time": row.get("commit_time"),
                    "task": row.get("task") or "",
                    "method": row.get("method") or "",
                    "class_method": row.get("class_method") or "",
                    "remote_ip": row.get("remote_ip"),
                    "event": row.get("event_id"),
                    "kwargs": row.get("kwargs") or "{}",
                    "ttp": row.get("ttp") or "{}",
                    "commands": row.get("commands") or "[]",
                    "back_off_commands": row.get("back_off_commands") or "[]",
                    "state": row.get("state") or WorkflowExecution._meta.get_field("state").default,
                    "code": row.get("code"),
                },
            )
            bucket = "created" if created else "updated"
            stats["executions"][bucket] += 1
            stats["executions"]["samples"].append(
                {"legacy_id": row["id"], "id": getattr(obj, "id", None), "task_id": row.get("task_id"), "status": bucket}
            )

        return stats

    def _emit_stats(self, stats, sample_limit):
        self.stdout.write(self.style.SUCCESS("workflow_center legacy 数据导入完成"))
        self.stdout.write(
            f"executions: created={stats['executions']['created']} updated={stats['executions']['updated']}"
        )
        self.stdout.write(
            f"host_vars: created={stats['host_vars']['created']} updated={stats['host_vars']['updated']}"
        )
        self.stdout.write(
            f"inventories: created={stats['inventories']['created']} updated={stats['inventories']['updated']}"
        )
        self.stdout.write(
            f"inventory_host_links: linked={stats['inventory_host_links']['linked']} skipped={stats['inventory_host_links']['skipped']}"
        )

        for label in ("executions", "host_vars", "inventories", "inventory_host_links"):
            samples = stats[label]["samples"][:sample_limit]
            if not samples:
                continue
            self.stdout.write(f"{label} samples:")
            for item in samples:
                self.stdout.write(json.dumps(item, ensure_ascii=False))

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        sample_limit = options["sample_limit"]
        execution_table = options["execution_table"]
        hostvar_table = options["hostvar_table"]
        inventory_table = options["inventory_table"]
        inventory_host_table = options["inventory_host_table"]

        execution_sql = f"SELECT * FROM {execution_table} ORDER BY id"
        hostvar_sql = f"SELECT * FROM {hostvar_table} ORDER BY id"
        inventory_sql = f"SELECT * FROM {inventory_table} ORDER BY id"
        inventory_host_sql = f"SELECT * FROM {inventory_host_table} ORDER BY id"

        if limit > 0:
            execution_sql += f" LIMIT {limit}"
            hostvar_sql += f" LIMIT {limit}"
            inventory_sql += f" LIMIT {limit}"

        with connection.cursor() as cursor:
            execution_rows = self._fetch_all(cursor, execution_sql)
            hostvar_rows = self._fetch_all(cursor, hostvar_sql)
            inventory_rows = self._fetch_all(cursor, inventory_sql)
            inventory_host_rows = self._fetch_all(cursor, inventory_host_sql)

        stats = self._import_rows(
            execution_rows,
            hostvar_rows,
            inventory_rows,
            inventory_host_rows,
        )

        if dry_run:
            transaction.set_rollback(True)

        self._emit_stats(stats, sample_limit)
