"""
初始化NETCONF XML模板的管理命令
"""
from django.core.management.base import BaseCommand
from apps.device_api.models import DeviceCollectionPlan, NetconfXMLTemplate


class Command(BaseCommand):
    help = '初始化NETCONF XML模板数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建，即使数据已存在',
        )
        parser.add_argument(
            '--collection-plan',
            type=str,
            help='指定采集方案名称，只创建该方案下的XML模板',
        )

    def handle(self, *args, **options):
        self.stdout.write('开始初始化NETCONF XML模板...')
        
        # 获取所有启用了NETCONF的采集方案
        if options['collection_plan']:
            collection_plans = DeviceCollectionPlan.objects.filter(
                name=options['collection_plan'],
                netconf_enabled=True
            )
            if not collection_plans.exists():
                self.stdout.write(
                    self.style.ERROR(f'错误：找不到名为 "{options["collection_plan"]}" 且启用NETCONF的采集方案')
                )
                return
        else:
            collection_plans = DeviceCollectionPlan.objects.filter(netconf_enabled=True)
        
        if not collection_plans.exists():
            self.stdout.write(
                self.style.WARNING('警告：没有找到启用NETCONF的采集方案，请先创建相关采集方案')
            )
            return
        
        # 预定义的XML模板数据
        xml_templates_data = [
            # H3C交换机接口信息模板
            {
                'collection_plan_name': 'H3C交换机接口信息采集',
                'templates': [
                    {
                        'name': 'H3C交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询H3C交换机接口状态和统计信息'
                    },
                    {
                        'name': 'H3C交换机接口配置查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <description/>
                <type/>
                <enabled/>
                <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
                    <address>
                        <ip/>
                        <prefix-length/>
                    </address>
                </ipv4>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询H3C交换机接口配置信息，包括IP地址'
                    }
                ]
            },
            # H3C路由器路由表模板
            {
                'collection_plan_name': 'H3C路由器路由表采集',
                'templates': [
                    {
                        'name': 'H3C路由器路由表查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <routing xmlns="urn:ietf:params:xml:ns:yang:ietf-routing">
                <routing-instance>
                    <name/>
                    <routing-protocols>
                        <routing-protocol>
                            <name/>
                            <type/>
                            <route>
                                <destination-prefix/>
                                <next-hop>
                                    <next-hop-address/>
                                    <outgoing-interface/>
                                </next-hop>
                                <source-protocol/>
                                <active/>
                            </route>
                        </routing-protocol>
                    </routing-protocols>
                </routing-instance>
            </routing>
        </filter>
</get>''',
                        'description': '查询H3C路由器路由表信息'
                    }
                ]
            },
            # 华为交换机接口信息模板
            {
                'collection_plan_name': '华为交换机接口信息采集',
                'templates': [
                    {
                        'name': '华为交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询华为交换机接口状态和统计信息'
                    }
                ]
            },
            # 思科交换机接口信息模板
            {
                'collection_plan_name': '思科交换机接口信息采集',
                'templates': [
                    {
                        'name': '思科交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询思科交换机接口状态和统计信息'
                    }
                ]
            },
            # 山石防火墙策略模板
            {
                'collection_plan_name': '山石防火墙策略采集',
                'templates': [
                    {
                        'name': '山石防火墙策略查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <security xmlns="urn:ietf:params:xml:ns:yang:ietf-security">
            <policies>
                <policy>
                    <name/>
                    <action/>
                    <source-zone/>
                    <destination-zone/>
                    <source-address/>
                    <destination-address/>
                    <service/>
                    <enabled/>
                </policy>
            </policies>
        </security>
    </filter>
</get>''',
                        'description': '查询山石防火墙安全策略配置'
                    }
                ]
            },
            # 锐捷交换机接口信息模板
            {
                'collection_plan_name': '锐捷交换机接口信息采集',
                'templates': [
                    {
                        'name': '锐捷交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询锐捷交换机接口状态和统计信息'
                    }
                ]
            },
            # Mellanox交换机接口信息模板
            {
                'collection_plan_name': 'Mellanox交换机接口信息采集',
                'templates': [
                    {
                        'name': 'Mellanox交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询Mellanox交换机接口状态和统计信息'
                    }
                ]
            },
            # 盛科交换机接口信息模板
            {
                'collection_plan_name': '盛科交换机接口信息采集',
                'templates': [
                    {
                        'name': '盛科交换机接口状态查询',
                        'xml_template': '''<get>
    <filter type="subtree">
        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
                <name/>
                <type/>
                <enabled/>
                <oper-status/>
                <statistics>
                    <in-octets/>
                    <out-octets/>
                    <in-errors/>
                    <out-errors/>
                </statistics>
            </interface>
        </interfaces>
    </filter>
</get>''',
                        'description': '查询盛科交换机接口状态和统计信息'
                    }
                ]
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in xml_templates_data:
            collection_plan_name = template_data['collection_plan_name']
            
            # 查找对应的采集方案
            try:
                collection_plan = DeviceCollectionPlan.objects.get(name=collection_plan_name)
            except DeviceCollectionPlan.DoesNotExist:
                self.stdout.write(f'⚠️  跳过：找不到采集方案 "{collection_plan_name}"')
                continue
            
            for template in template_data['templates']:
                name = template['name']
                
                # 创建template的副本，避免修改原始数据
                template_copy = template.copy()
                # 添加collection_plan外键
                template_copy['collection_plan'] = collection_plan
                
                if options['force']:
                    # 强制重新创建
                    NetconfXMLTemplate.objects.filter(
                        name=name,
                        collection_plan=collection_plan
                    ).delete()
                    xml_template = NetconfXMLTemplate.objects.create(**template_copy)
                    created_count += 1
                    self.stdout.write(f'✅ 重新创建: {name} (在 {collection_plan_name} 下)')
                else:
                    # 检查是否已存在
                    xml_template, created = NetconfXMLTemplate.objects.get_or_create(
                        name=name,
                        collection_plan=collection_plan,
                        defaults=template_copy
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f'✅ 创建: {name} (在 {collection_plan_name} 下)')
                    else:
                        updated_count += 1
                        self.stdout.write(f'⚠️  已存在: {name} (在 {collection_plan_name} 下)')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n初始化完成！创建: {created_count}, 已存在: {updated_count}'
            )
        )
        
        # 显示统计信息
        total_templates = NetconfXMLTemplate.objects.count()
        self.stdout.write(f'\n当前共有 {total_templates} 个XML模板:')
        
        for collection_plan in collection_plans:
            template_count = collection_plan.xml_templates.count()
            self.stdout.write(f'  - {collection_plan.name}: {template_count} 个XML模板') 