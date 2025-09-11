"""
清理测试数据的管理命令
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.device_api.models import DeviceSummaryPlans, DeviceCollectionPlan, NetconfXMLTemplate


class Command(BaseCommand):
    help = '清理测试数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='清理所有数据（危险操作）',
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='仅清理包含"测试"关键词的数据',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要删除的数据，不实际删除',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='确认删除操作',
        )

    def handle(self, *args, **options):
        if options['all'] and not options['confirm']:
            self.stdout.write(
                self.style.ERROR(
                    '危险操作！使用 --all 参数时必须同时使用 --confirm 参数'
                )
            )
            return
        
        if options['dry_run']:
            self.stdout.write('=== 预览模式 ===')
            self._preview_cleanup(options)
            return
        
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '请使用 --confirm 参数确认删除操作'
                )
            )
            return
        
        # 开始清理
        self.stdout.write('开始清理测试数据...')
        
        try:
            with transaction.atomic():
                deleted_summary_plans = 0
                deleted_collection_plans = 0
                deleted_xml_templates = 0
                
                if options['all']:
                    # 清理所有数据
                    deleted_xml_templates = NetconfXMLTemplate.objects.count()
                    deleted_collection_plans = DeviceCollectionPlan.objects.count()
                    deleted_summary_plans = DeviceSummaryPlans.objects.count()
                    
                    NetconfXMLTemplate.objects.all().delete()
                    DeviceCollectionPlan.objects.all().delete()
                    DeviceSummaryPlans.objects.all().delete()
                    
                    self.stdout.write('✅ 已清理所有数据')
                    
                elif options['test_only']:
                    # 仅清理测试数据
                    # 查找包含"测试"关键词的汇总方案
                    test_summary_plans = DeviceSummaryPlans.objects.filter(
                        name__icontains='测试'
                    )
                    
                    for summary_plan in test_summary_plans:
                        # 统计要删除的数据
                        plan_count = summary_plan.collect_plans.count()
                        xml_count = 0
                        
                        for plan in summary_plan.collect_plans.all():
                            xml_count += plan.xml_templates.count()
                        
                        # 删除关联的XML模板
                        for plan in summary_plan.collect_plans.all():
                            plan.xml_templates.all().delete()
                        
                        # 删除关联的采集方案
                        summary_plan.collect_plans.all().delete()
                        
                        # 删除汇总方案
                        summary_plan.delete()
                        
                        deleted_summary_plans += 1
                        deleted_collection_plans += plan_count
                        deleted_xml_templates += xml_count
                        
                        self.stdout.write(f'✅ 清理测试汇总方案: {summary_plan.name}')
                    
                    # 查找包含"测试"关键词的采集方案（可能没有关联汇总方案）
                    test_collection_plans = DeviceCollectionPlan.objects.filter(
                        name__icontains='测试'
                    )
                    
                    for plan in test_collection_plans:
                        xml_count = plan.xml_templates.count()
                        plan.xml_templates.all().delete()
                        plan.delete()
                        
                        deleted_collection_plans += 1
                        deleted_xml_templates += xml_count
                        
                        self.stdout.write(f'✅ 清理测试采集方案: {plan.name}')
                    
                    # 查找包含"测试"关键词的XML模板
                    test_xml_templates = NetconfXMLTemplate.objects.filter(
                        name__icontains='测试'
                    )
                    
                    for template in test_xml_templates:
                        template.delete()
                        deleted_xml_templates += 1
                        self.stdout.write(f'✅ 清理测试XML模板: {template.name}')
                    
                else:
                    self.stdout.write(
                        self.style.WARNING('请指定清理模式：--all 或 --test-only')
                    )
                    return
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n清理完成！删除汇总方案: {deleted_summary_plans}, '
                        f'删除采集方案: {deleted_collection_plans}, '
                        f'删除XML模板: {deleted_xml_templates}'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'清理失败: {str(e)}')
            )
            return
        
        # 显示清理后的统计信息
        self._show_statistics()
    
    def _preview_cleanup(self, options):
        """预览将要删除的数据"""
        if options['all']:
            self.stdout.write('将要删除所有数据:')
            self.stdout.write(f'  - 汇总方案: {DeviceSummaryPlans.objects.count()} 个')
            self.stdout.write(f'  - 采集方案: {DeviceCollectionPlan.objects.count()} 个')
            self.stdout.write(f'  - XML模板: {NetconfXMLTemplate.objects.count()} 个')
            
        elif options['test_only']:
            self.stdout.write('将要删除的测试数据:')
            
            # 汇总方案
            test_summary_plans = DeviceSummaryPlans.objects.filter(
                name__icontains='测试'
            )
            self.stdout.write(f'  - 汇总方案: {test_summary_plans.count()} 个')
            for plan in test_summary_plans:
                self.stdout.write(f'    * {plan.name}')
            
            # 采集方案
            test_collection_plans = DeviceCollectionPlan.objects.filter(
                name__icontains='测试'
            )
            self.stdout.write(f'  - 采集方案: {test_collection_plans.count()} 个')
            for plan in test_collection_plans:
                self.stdout.write(f'    * {plan.name}')
            
            # XML模板
            test_xml_templates = NetconfXMLTemplate.objects.filter(
                name__icontains='测试'
            )
            self.stdout.write(f'  - XML模板: {test_xml_templates.count()} 个')
            for template in test_xml_templates:
                self.stdout.write(f'    * {template.name}')
    
    def _show_statistics(self):
        """显示清理后的统计信息"""
        self.stdout.write('\n=== 清理后统计信息 ===')
        
        summary_count = DeviceSummaryPlans.objects.count()
        collection_count = DeviceCollectionPlan.objects.count()
        xml_count = NetconfXMLTemplate.objects.count()
        
        self.stdout.write(f'汇总方案: {summary_count} 个')
        self.stdout.write(f'采集方案: {collection_count} 个')
        self.stdout.write(f'XML模板: {xml_count} 个')
        
        if summary_count == 0:
            self.stdout.write(
                self.style.WARNING('⚠️  没有汇总方案数据')
            )
        elif collection_count == 0:
            self.stdout.write(
                self.style.WARNING('⚠️  没有采集方案数据')
            )
        else:
            self.stdout.write('✅ 数据清理完成') 