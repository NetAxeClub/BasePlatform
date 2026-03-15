from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.device_api.models import DeviceCollectionMatchRule, DeviceCollectionRule


class Command(BaseCommand):
    help = "从 legacy collection_rule / collection_match_rule 物理表导入数据到 device_api 新规则表。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据")
        parser.add_argument("--limit", type=int, default=0, help="限制导入数量")
        parser.add_argument("--rule-table", default="collection_rule")
        parser.add_argument("--match-rule-table", default="collection_match_rule")
        parser.add_argument("--sample-limit", type=int, default=20, help="输出样例数量上限")

    @staticmethod
    def _fetch_all(cursor, sql):
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _import_rows(rules, match_rules):
        stats = {
            "rules": {"created": 0, "updated": 0, "samples": []},
            "match_rules": {"created": 0, "updated": 0, "samples": []},
        }
        rule_id_map = {}

        for row in rules:
            rule, created = DeviceCollectionRule.objects.update_or_create(
                legacy_rule_id=row["id"],
                defaults={
                    "name": row.get("name"),
                    "operation": row.get("operation"),
                    "module": row.get("module"),
                    "method": row.get("method"),
                    "execute": row.get("execute") or "",
                    "plugin": row.get("plugin") or "",
                },
            )
            rule_id_map[row["id"]] = rule.id
            bucket = "created" if created else "updated"
            stats["rules"][bucket] += 1
            stats["rules"]["samples"].append(
                {"legacy_id": row["id"], "id": getattr(rule, "id", None), "name": row.get("name"), "status": bucket}
            )

        for row in match_rules:
            match_rule, created = DeviceCollectionMatchRule.objects.update_or_create(
                legacy_match_rule_id=row["id"],
                defaults={
                    "name": row.get("name"),
                    "fields": row.get("fields"),
                    "operator": row.get("operator"),
                    "value": row.get("value"),
                    "rule_id": rule_id_map.get(row.get("rule_id")),
                },
            )
            bucket = "created" if created else "updated"
            stats["match_rules"][bucket] += 1
            stats["match_rules"]["samples"].append(
                {"legacy_id": row["id"], "id": getattr(match_rule, "id", None), "name": row.get("name"), "status": bucket}
            )

        return stats

    def _emit_stats(self, stats, sample_limit):
        self.stdout.write(self.style.SUCCESS("device_api legacy 采集规则导入完成"))
        self.stdout.write(
            f"rules: created={stats['rules']['created']} updated={stats['rules']['updated']}"
        )
        self.stdout.write(
            f"match_rules: created={stats['match_rules']['created']} updated={stats['match_rules']['updated']}"
        )
        for label in ("rules", "match_rules"):
            samples = stats[label]["samples"][:sample_limit]
            if not samples:
                continue
            self.stdout.write(f"{label} samples:")
            for item in samples:
                self.stdout.write(str(item))

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        sample_limit = options["sample_limit"]
        rule_table = options["rule_table"]
        match_rule_table = options["match_rule_table"]

        rule_sql = f"SELECT * FROM {rule_table} ORDER BY id"
        match_rule_sql = f"SELECT * FROM {match_rule_table} ORDER BY id"
        if limit > 0:
            rule_sql += f" LIMIT {limit}"
            match_rule_sql += f" LIMIT {limit}"

        with connection.cursor() as cursor:
            rules = self._fetch_all(cursor, rule_sql)
            match_rules = self._fetch_all(cursor, match_rule_sql)

        stats = self._import_rows(rules, match_rules)

        if dry_run:
            transaction.set_rollback(True)

        self._emit_stats(stats, sample_limit)
