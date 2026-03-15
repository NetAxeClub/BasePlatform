from django.core.management.base import BaseCommand

from apps.network_analysis.services import NetworkAnalysisOrchestratorService


class Command(BaseCommand):
    help = "统一重建 network_analysis 的接口利用率和地址定位分析。"

    def add_arguments(self, parser):
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅分析指定设备")
        parser.add_argument("--ip-address", dest="ip_address", help="仅分析指定IP")

    def handle(self, *args, **options):
        result = NetworkAnalysisOrchestratorService.refresh_all(
            manage_ip=options.get("manage_ip"),
            ip_address=options.get("ip_address"),
            triggered_by="management-command",
        )
        self.stdout.write(self.style.SUCCESS("network_analysis 统一重建完成"))
        self.stdout.write(str(result))
