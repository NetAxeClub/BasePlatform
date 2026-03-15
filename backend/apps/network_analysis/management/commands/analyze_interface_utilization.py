from django.core.management.base import BaseCommand

from apps.network_analysis.services import InterfaceUtilizationAnalysisService


class Command(BaseCommand):
    help = "基于 device_api 标准化接口结果重建接口利用率快照。"

    def add_arguments(self, parser):
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅分析指定设备")

    def handle(self, *args, **options):
        result = InterfaceUtilizationAnalysisService.refresh(device_ip=options.get("manage_ip"))
        self.stdout.write(self.style.SUCCESS(f"接口利用率分析完成: {result['snapshots']}"))
