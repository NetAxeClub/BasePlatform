"""
快速开始命令 - 一次性初始化所有Device API数据
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = '快速初始化所有Device API数据（汇总方案、采集方案、XML模板）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建所有数据',
        )
        parser.add_argument(
            '--skip-xml',
            action='store_true',
            help='跳过XML模板初始化',
        )

    def handle(self, *args, **options):
        self.stdout.write('🚀 开始快速初始化Device API数据...')
        self.stdout.write('=' * 50)
        
        try:
            # 1. 初始化汇总方案
            self.stdout.write('\n📋 步骤1: 初始化采集汇总方案...')
            if options['force']:
                call_command('init_summary_plans', force=True)
            else:
                call_command('init_summary_plans')
            self.stdout.write('✅ 汇总方案初始化完成')
            
            # 2. 初始化采集方案
            self.stdout.write('\n📋 步骤2: 初始化设备采集方案...')
            if options['force']:
                call_command('init_collection_plans', force=True)
            else:
                call_command('init_collection_plans')
            self.stdout.write('✅ 采集方案初始化完成')
            
            # 3. 初始化XML模板（可选）
            if not options['skip_xml']:
                self.stdout.write('\n📋 步骤3: 初始化NETCONF XML模板...')
                if options['force']:
                    call_command('init_xml_templates', force=True)
                else:
                    call_command('init_xml_templates')
                self.stdout.write('✅ XML模板初始化完成')
            else:
                self.stdout.write('\n⏭️  步骤3: 跳过XML模板初始化')
            
            # 4. 显示统计信息
            self.stdout.write('\n📊 初始化完成！显示统计信息...')
            self._show_statistics()
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 所有数据初始化完成！')
            )
            
            # 5. 显示下一步建议
            self._show_next_steps()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ 初始化失败: {str(e)}')
            )
            self.stdout.write('请检查错误信息并重试')
    
    def _show_statistics(self):
        """显示数据统计信息"""
        try:
            from apps.device_api.models import DeviceSummaryPlans, DeviceCollectionPlan, NetconfXMLTemplate
            
            summary_count = DeviceSummaryPlans.objects.count()
            collection_count = DeviceCollectionPlan.objects.count()
            xml_count = NetconfXMLTemplate.objects.count()
            
            self.stdout.write(f'\n📈 数据统计:')
            self.stdout.write(f'  - 汇总方案: {summary_count} 个')
            self.stdout.write(f'  - 采集方案: {collection_count} 个')
            self.stdout.write(f'  - XML模板: {xml_count} 个')
            
            # 显示汇总方案详情
            if summary_count > 0:
                self.stdout.write(f'\n📋 汇总方案详情:')
                for summary_plan in DeviceSummaryPlans.objects.all():
                    plan_count = summary_plan.collect_plans.count()
                    self.stdout.write(f'  - {summary_plan.name}: {plan_count} 个采集方案')
                    
        except Exception as e:
            self.stdout.write(f'⚠️  无法获取统计信息: {str(e)}')
    
    def _show_next_steps(self):
        """显示下一步建议"""
        self.stdout.write('\n📖 下一步建议:')
        self.stdout.write('1. 访问Django Admin查看创建的数据')
        self.stdout.write('2. 使用API端点测试数据访问')
        self.stdout.write('3. 根据需要修改或添加更多数据')
        self.stdout.write('4. 运行测试验证功能')
        
        self.stdout.write('\n🔧 常用命令:')
        self.stdout.write('  - 查看帮助: python manage.py help')
        self.stdout.write('  - 清理测试数据: python manage.py cleanup_test_data --test-only --dry-run')
        self.stdout.write('  - 强制重新创建: python manage.py quick_start --force') 