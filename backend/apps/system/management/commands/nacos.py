# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      nacos
   Description:
   Author:          Lijiamin
   date：           2023/5/26 18:27
-------------------------------------------------
   Change Activity:
                    2023/5/26 18:27
-------------------------------------------------
"""
from django.core.management import BaseCommand
from utils.nacos_register import nacos_init


class Command(BaseCommand):
    """
    项目初始化命令: python manage.py init_asset
    """

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        print(f"开始nacos注册...")
        nacos_init()
