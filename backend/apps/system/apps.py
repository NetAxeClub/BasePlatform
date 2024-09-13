from django.apps import AppConfig
from utils.nacos_register import nacos_init

class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'

    def ready(self):
        nacos_init()