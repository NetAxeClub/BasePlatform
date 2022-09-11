# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      init_asset
   Description:
   Author:          Lijiamin
   date：           2022/9/8 16:36
-------------------------------------------------
   Change Activity:
                    2022/9/8 16:36
-------------------------------------------------
"""
import json
import os
import django
from django.core.management import BaseCommand
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netboost.settings')
django.setup()
from netboost.settings import BASE_DIR
from django.apps import apps
from apps.asset.models import Idc


def main():
    with open(os.path.join(BASE_DIR, 'utils', 'init_asset.json'), 'r', encoding="utf-8") as load_f:
        code_list = json.load(load_f)
        for table, values in code_list.items():
            my_model = apps.get_model("asset", table)
            if my_model:
                for value in values:
                    if table == "IdcModel":
                        value['idc'] = Idc.objects.get(id=value['idc_id'])
                    my_model.objects.get_or_create(**value)


class Command(BaseCommand):
    """
    项目初始化命令: python manage.py init_asset
    """

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):

        print(f"正在准备初始化资产数据...")
        main()
        print("数据初始化资产数据完成！")
