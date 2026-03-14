import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.config_center.models import ConfigCompliance, ConfigComplianceRule


BASELINE_FILE = Path(__file__).with_name("security_baselines.json")


def load_baseline_data():
    with open(BASELINE_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_rule_tree(rule_tree, reset=False):
    root_name = rule_tree["root"]
    root_rule, _ = ConfigComplianceRule.objects.get_or_create(name=root_name, parent=None)

    child_rules = {}
    for child_name in rule_tree.get("children", []):
        child_rule, _ = ConfigComplianceRule.objects.get_or_create(name=child_name, parent=root_rule)
        child_rules[child_name] = child_rule

    if reset:
        ConfigCompliance.objects.filter(rule__in=child_rules.values()).delete()

    return root_rule, child_rules


def upsert_compliance_rows(items, child_rules, dry_run=False):
    created = 0
    existing = 0
    updated = 0

    for item in items:
        rule_name = item["rule"]
        rule = child_rules[rule_name]
        lookup = {
            "vendor": item["vendor"],
            "pattern": item["pattern"],
            "regex": item["regex"],
            "rule": rule,
        }
        defaults = {
            "intent": item.get("intent", ""),
        }
        compliance = ConfigCompliance.objects.filter(**lookup).first()
        if compliance:
            dirty = False
            for field_name, value in defaults.items():
                if getattr(compliance, field_name, "") != value:
                    setattr(compliance, field_name, value)
                    dirty = True
            if dirty:
                if not dry_run:
                    compliance.save(update_fields=list(defaults.keys()) + ["datetime"])
                updated += 1
            else:
                existing += 1
            continue
        if not dry_run:
            ConfigCompliance.objects.create(**lookup, **defaults)
        created += 1

    return created, existing, updated


class Command(BaseCommand):
    help = "初始化 NetClaw-CN 管理面硬化安全基线规则"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅预览将要创建的数据，不写数据库")
        parser.add_argument("--reset", action="store_true", help="先删除同规则树下已存在的合规项，再重建")

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        reset = options.get("reset", False)

        data = load_baseline_data()
        root_rule, child_rules = ensure_rule_tree(data["rule_tree"], reset=reset and not dry_run)
        created, existing, updated = upsert_compliance_rows(
            data.get("compliance", []),
            child_rules,
            dry_run=dry_run,
        )

        self.stdout.write(self.style.SUCCESS("管理面硬化基线初始化完成"))
        self.stdout.write(f"根规则: {root_rule.name}")
        self.stdout.write(f"子规则数: {len(child_rules)}")
        self.stdout.write(f"新增合规项: {created}")
        self.stdout.write(f"已存在合规项: {existing}")
        self.stdout.write(f"更新合规项: {updated}")
        self.stdout.write(f"模式: {'dry-run' if dry_run else 'apply'}")
