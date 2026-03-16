import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DeviceApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.device_api'
    verbose_name = '设备API管理'

    def ready(self):
        from apps.device_api.indexes import (
            bootstrap_device_api_mongo_indexes,
            should_auto_ensure_device_api_indexes,
        )

        if not should_auto_ensure_device_api_indexes():
            return

        created = bootstrap_device_api_mongo_indexes()
        if created:
            logger.debug("device_api ready() ensured %s Mongo indexes", len(created))
