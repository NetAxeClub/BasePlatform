from django.core.management.base import BaseCommand

from apps.device_api.indexes import ensure_device_api_mongo_indexes


class Command(BaseCommand):
    help = "为 device_api 相关 MongoDB 集合创建/确保复合索引"

    def handle(self, *args, **options):
        created = ensure_device_api_mongo_indexes()
        self.stdout.write(self.style.SUCCESS(f"device_api Mongo 索引已确保，共 {len(created)} 个"))
        for item in created:
            self.stdout.write(f"{item['collection']}: {item['index']}")
