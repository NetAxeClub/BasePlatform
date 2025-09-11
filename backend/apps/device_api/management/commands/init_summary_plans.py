"""
初始化采集汇总方案的管理命令
"""
from django.core.management.base import BaseCommand
from apps.device_api.models import DeviceSummaryPlans


class Command(BaseCommand):
    help = '初始化采集汇总方案数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建，即使数据已存在',
        )

    def handle(self, *args, **options):
        self.stdout.write('开始初始化采集汇总方案...')
        
        # 预定义的汇总方案数据
        summary_plans_data = [
            {
                'name': 'H3C交换机采集方案',
                'vendor': 'H3C',
                'device_type': 'switch',
                'description': '用于采集H3C交换机配置和状态信息的汇总方案'
            },
            {
                'name': 'H3C路由器采集方案',
                'vendor': 'H3C',
                'device_type': 'router',
                'description': '用于采集H3C路由器配置和状态信息的汇总方案'
            },
            {
                'name': '华为交换机采集方案',
                'vendor': 'Huawei',
                'device_type': 'switch',
                'description': '用于采集华为交换机配置和状态信息的汇总方案'
            },
            {
                'name': '华为路由器采集方案',
                'vendor': 'Huawei',
                'device_type': 'router',
                'description': '用于采集华为路由器配置和状态信息的汇总方案'
            },
            {
                'name': '思科交换机采集方案',
                'vendor': 'Cisco',
                'device_type': 'switch',
                'description': '用于采集思科交换机配置和状态信息的汇总方案'
            },
            {
                'name': '思科路由器采集方案',
                'vendor': 'Cisco',
                'device_type': 'router',
                'description': '用于采集思科路由器配置和状态信息的汇总方案'
            },
            {
                'name': '山石防火墙采集方案',
                'vendor': 'Hillstone',
                'device_type': 'firewall',
                'description': '用于采集山石防火墙配置和状态信息的汇总方案'
            },
            {
                'name': '锐捷交换机采集方案',
                'vendor': 'Ruijie',
                'device_type': 'switch',
                'description': '用于采集锐捷交换机配置和状态信息的汇总方案'
            },
            {
                'name': 'Mellanox交换机采集方案',
                'vendor': 'Mellanox',
                'device_type': 'switch',
                'description': '用于采集Mellanox交换机配置和状态信息的汇总方案'
            },
            {
                'name': '盛科交换机采集方案',
                'vendor': 'Centec',
                'device_type': 'switch',
                'description': '用于采集盛科交换机配置和状态信息的汇总方案'
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for plan_data in summary_plans_data:
            name = plan_data['name']
            
            if options['force']:
                # 强制重新创建
                DeviceSummaryPlans.objects.filter(name=name).delete()
                plan = DeviceSummaryPlans.objects.create(**plan_data)
                created_count += 1
                self.stdout.write(f'✅ 重新创建: {name}')
            else:
                # 检查是否已存在
                plan, created = DeviceSummaryPlans.objects.get_or_create(
                    name=name,
                    defaults=plan_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'✅ 创建: {name}')
                else:
                    updated_count += 1
                    self.stdout.write(f'⚠️  已存在: {name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n初始化完成！创建: {created_count}, 已存在: {updated_count}'
            )
        )
        
        # 显示所有汇总方案
        all_plans = DeviceSummaryPlans.objects.all()
        self.stdout.write(f'\n当前共有 {all_plans.count()} 个汇总方案:')
        for plan in all_plans:
            self.stdout.write(f'  - {plan.name} ({plan.get_vendor_display()}-{plan.get_device_type_display()})') 