import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.device_api.platform_profiles import PlatformProfileService


class Command(BaseCommand):
    help = "审计 device_api 默认方案 legacy alias，并给出收编/退役建议。"

    def add_arguments(self, parser):
        parser.add_argument("--profile-code", dest="profile_code", help="仅审计指定画像编码")
        parser.add_argument("--sample-limit", type=int, default=20, help="输出样例数量上限")
        parser.add_argument("--output", dest="output", help="将完整审计结果写入 JSON 文件")

    def handle(self, *args, **options):
        profile_code = (options.get("profile_code") or "").strip()
        sample_limit = options.get("sample_limit") or 20
        audit_result = PlatformProfileService.audit_legacy_default_plan_aliases(
            profile_codes=[profile_code] if profile_code else None,
        )
        summary = audit_result["summary"]
        results = audit_result["results"]

        self.stdout.write(self.style.SUCCESS("legacy alias 审计完成"))
        self.stdout.write(
            "summary: "
            f"profiles_scanned={summary['profiles_scanned']} "
            f"alias_names_declared={summary['alias_names_declared']} "
            f"alias_plans_found={summary['alias_plans_found']} "
            f"adoptable={summary['adoptable']} "
            f"retirable={summary['retirable']} "
            f"blocked_by_active_bindings={summary['blocked_by_active_bindings']} "
            f"readiness_blocked={summary['readiness_blocked']}"
        )

        if not results:
            self.stdout.write("samples: none")
        else:
            self.stdout.write("samples:")
            for item in results[:sample_limit]:
                self.stdout.write(
                    "- "
                    f"profile={item['profile_code']} "
                    f"alias={item['alias_plan_name']}#{item['alias_plan_id']} "
                    f"canonical={item['canonical_plan_name'] or '-'} "
                    f"action={item['recommended_action']} "
                    f"active_bindings={item['active_bindings']} "
                    f"issues={','.join(item['issues']) or '-'}"
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
