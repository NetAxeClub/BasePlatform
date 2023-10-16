# 城市联动
"""
到乡级 使用方法
1. https://www.npmjs.com/package/china-division 下载数据，把对应的json放入对应目录
2. 修改此文件中对应json名
3. 右击执行此py文件进行初始化
"""
import os
import django
from django.core.management import BaseCommand


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netaxe.settings')
django.setup()


def main():
    pass


class Command(BaseCommand):
    """
    项目初始化命令: python manage.py init_area
    """

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):

        print(f"正在准备初始化省份数据...")
        main()
        print("省份数据初始化数据完成！")
