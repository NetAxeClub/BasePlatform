from django.core.management.base import BaseCommand
from apps.asset.models import NetworkDevice
from apps.device_api.models import DeviceCollectionPlans, PlansToDevice
from apps.device_api.platform_profiles import PlatformProfileService


class Command(BaseCommand):
    help = "将旧入口 NetworkDevice.plan 的绑定信息同步到 device_api.PlansToDevice，作为并行桥接关系。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据库")
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅同步指定设备")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        manage_ip = options.get("manage_ip")

        queryset = NetworkDevice.objects.filter(
            status=0,
            auto_enable=True,
            plan__isnull=False,
        ).select_related("plan", "vendor", "category")

        if manage_ip:
            queryset = queryset.filter(manage_ip=manage_ip)

        created_count = 0
        skipped_count = 0
        unresolved = []

        for device in queryset.iterator():
            legacy_plan = getattr(device, "plan", None)
            if not legacy_plan:
                continue

            summary_plan = DeviceCollectionPlans.objects.filter(
                name=legacy_plan.name,
                vendor=(device.vendor.alias if device.vendor else ""),
                device_type=(device.category.name if device.category else ""),
            ).first()
            if not summary_plan:
                unresolved.append(
                    {
                        "manage_ip": device.manage_ip,
                        "legacy_plan_id": legacy_plan.id,
                        "legacy_plan_name": legacy_plan.name,
                    }
                )
                continue

            existed = PlansToDevice.objects.filter(
                manage_ip=device.manage_ip,
                plan=summary_plan,
            ).exists()
            if existed:
                skipped_count += 1
                continue

            if not dry_run:
                profile = PlatformProfileService.match_profile_for_device(device)
                PlansToDevice.objects.create(
                    device_serial_num=device.serial_num,
                    manage_ip=device.manage_ip,
                    plan=summary_plan,
                    profile_code=profile.code if profile else "",
                    binding_source=PlansToDevice.BINDING_SOURCE_LEGACY,
                    is_active=True,
                    use_local=True,
                    execute_node="",
                    last_bound_at=None,
                )
            created_count += 1

        if dry_run:
            transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("旧入口绑定同步完成"))
        self.stdout.write(f"新增绑定: {created_count}")
        self.stdout.write(f"已存在跳过: {skipped_count}")
        self.stdout.write(f"未匹配到 device_api 父方案: {len(unresolved)}")
        if unresolved:
            for item in unresolved[:20]:
                self.stdout.write(
                    f"- {item['manage_ip']} -> legacy plan {item['legacy_plan_name']}({item['legacy_plan_id']})"
                )
