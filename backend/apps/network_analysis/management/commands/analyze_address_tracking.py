from django.core.management.base import BaseCommand

from apps.network_analysis.services import AddressTrackingAnalysisService


class Command(BaseCommand):
    help = "基于 device_api 标准化采集结果重建地址定位快照。"

    def add_arguments(self, parser):
        parser.add_argument("--ip-address", dest="ip_address", help="仅分析指定IP")

    def handle(self, *args, **options):
        result = AddressTrackingAnalysisService.refresh(ip_address=options.get("ip_address"))
        self.stdout.write(self.style.SUCCESS(f"地址定位分析完成: {result['traces']}"))
