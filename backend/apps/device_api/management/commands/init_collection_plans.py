"""
初始化设备采集方案的管理命令
"""
from django.core.management.base import BaseCommand
from apps.device_api.models import DeviceSummaryPlans, DeviceCollectionPlan


class Command(BaseCommand):
    help = '初始化设备采集方案数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建，即使数据已存在',
        )
        parser.add_argument(
            '--summary-plan',
            type=str,
            help='指定汇总方案名称，只创建该方案下的采集方案',
        )

    def handle(self, *args, **options):
        self.stdout.write('开始初始化设备采集方案...')
        
        # 获取所有汇总方案
        if options['summary_plan']:
            summary_plans = DeviceSummaryPlans.objects.filter(name=options['summary_plan'])
            if not summary_plans.exists():
                self.stdout.write(
                    self.style.ERROR(f'错误：找不到名为 "{options["summary_plan"]}" 的汇总方案')
                )
                return
        else:
            summary_plans = DeviceSummaryPlans.objects.all()
        
        if not summary_plans.exists():
            self.stdout.write(
                self.style.WARNING('警告：没有找到任何汇总方案，请先运行 init_summary_plans 命令')
            )
            return
        
        # 预定义的采集方案数据
        collection_plans_data = [
            # H3C交换机采集方案
            {
                'summary_plan_name': 'H3C交换机采集方案',
                'plans': [
                    {
                        'name': 'H3C交换机接口信息采集',
                        'description': '采集H3C交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'h3c.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'h3c_show_interface.template',
                        'data_processor_enabled': True,
                        'data_processor': '''
def process_data(raw_data):
    """处理H3C交换机接口数据"""
    try:
        result = {
            'device_type': 'switch',
            'vendor': 'H3C',
            'interfaces': [],
            'summary': {
                'total_interfaces': 0,
                'up_interfaces': 0,
                'down_interfaces': 0
            }
        }
        
        if isinstance(raw_data, dict) and 'interfaces' in raw_data:
            for interface in raw_data['interfaces']:
                interface_info = {
                    'name': interface.get('name', 'Unknown'),
                    'status': interface.get('status', 'Unknown'),
                    'ip_address': interface.get('ip_address', 'N/A'),
                    'description': interface.get('description', '')
                }
                result['interfaces'].append(interface_info)
                
                if interface.get('status') == 'up':
                    result['summary']['up_interfaces'] += 1
                else:
                    result['summary']['down_interfaces'] += 1
            
            result['summary']['total_interfaces'] = len(result['interfaces'])
        
        return result
    except Exception as e:
        return {'error': f'Processing failed: {str(e)}'}
'''
                    },
                    {
                        'name': 'H3C交换机VLAN信息采集',
                        'description': '采集H3C交换机VLAN配置信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_vlans',
                        'netmiko_path': 'h3c.switch.vlans',
                        'netconf_enabled': False,
                        'textfsm_enabled': True,
                        'textfsm_template': 'h3c_show_vlan.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # H3C路由器采集方案
            {
                'summary_plan_name': 'H3C路由器采集方案',
                'plans': [
                    {
                        'name': 'H3C路由器路由表采集',
                        'description': '采集H3C路由器路由表信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_routing_table',
                        'netmiko_path': 'h3c.router.routing',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'h3c_show_ip_route.template',
                        'data_processor_enabled': True,
                        'data_processor': '''
def process_data(raw_data):
    """处理H3C路由器路由数据"""
    try:
        result = {
            'device_type': 'router',
            'vendor': 'H3C',
            'routing_table': [],
            'summary': {
                'total_routes': 0,
                'connected_routes': 0,
                'static_routes': 0,
                'dynamic_routes': 0
            }
        }
        
        if isinstance(raw_data, dict) and 'routes' in raw_data:
            for route in raw_data['routes']:
                route_info = {
                    'destination': route.get('destination', 'Unknown'),
                    'next_hop': route.get('next_hop', 'Unknown'),
                    'protocol': route.get('protocol', 'Unknown'),
                    'metric': route.get('metric', 'N/A')
                }
                result['routing_table'].append(route_info)
                
                protocol = route.get('protocol', '').lower()
                if 'connected' in protocol:
                    result['summary']['connected_routes'] += 1
                elif 'static' in protocol:
                    result['summary']['static_routes'] += 1
                else:
                    result['summary']['dynamic_routes'] += 1
            
            result['summary']['total_routes'] = len(result['routing_table'])
        
        return result
    except Exception as e:
        return {'error': f'Processing failed: {str(e)}'}
'''
                    }
                ]
            },
            # 华为交换机采集方案
            {
                'summary_plan_name': '华为交换机采集方案',
                'plans': [
                    {
                        'name': '华为交换机接口信息采集',
                        'description': '采集华为交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'huawei.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'huawei_display_interface.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # 思科交换机采集方案
            {
                'summary_plan_name': '思科交换机采集方案',
                'plans': [
                    {
                        'name': '思科交换机接口信息采集',
                        'description': '采集思科交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'cisco.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'cisco_show_interface.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # 山石防火墙采集方案
            {
                'summary_plan_name': '山石防火墙采集方案',
                'plans': [
                    {
                        'name': '山石防火墙策略采集',
                        'description': '采集山石防火墙安全策略配置',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_security_policies',
                        'netmiko_path': 'hillstone.firewall.policies',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'hillstone_show_policy.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # 锐捷交换机采集方案
            {
                'summary_plan_name': '锐捷交换机采集方案',
                'plans': [
                    {
                        'name': '锐捷交换机接口信息采集',
                        'description': '采集锐捷交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'ruijie.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'ruijie_show_interface.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # Mellanox交换机采集方案
            {
                'summary_plan_name': 'Mellanox交换机采集方案',
                'plans': [
                    {
                        'name': 'Mellanox交换机接口信息采集',
                        'description': '采集Mellanox交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'mellanox.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'mellanox_show_interface.template',
                        'data_processor_enabled': False
                    }
                ]
            },
            # 盛科交换机采集方案
            {
                'summary_plan_name': '盛科交换机采集方案',
                'plans': [
                    {
                        'name': '盛科交换机接口信息采集',
                        'description': '采集盛科交换机接口状态、IP地址等信息',
                        'netmiko_enabled': True,
                        'netmiko_method': 'get_interfaces',
                        'netmiko_path': 'centec.switch.interfaces',
                        'netconf_enabled': True,
                        'textfsm_enabled': True,
                        'textfsm_template': 'centec_show_interface.template',
                        'data_processor_enabled': False
                    }
                ]
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for summary_data in collection_plans_data:
            summary_plan_name = summary_data['summary_plan_name']
            
            # 查找对应的汇总方案
            try:
                summary_plan = DeviceSummaryPlans.objects.get(name=summary_plan_name)
            except DeviceSummaryPlans.DoesNotExist:
                self.stdout.write(f'⚠️  跳过：找不到汇总方案 "{summary_plan_name}"')
                continue
            
            for plan_data in summary_data['plans']:
                name = plan_data['name']
                
                # 创建plan_data的副本，避免修改原始数据
                plan_data_copy = plan_data.copy()
                # 添加summary_plan外键
                plan_data_copy['summary_plan'] = summary_plan
                
                if options['force']:
                    # 强制重新创建
                    DeviceCollectionPlan.objects.filter(name=name).delete()
                    plan = DeviceCollectionPlan.objects.create(**plan_data_copy)
                    created_count += 1
                    self.stdout.write(f'✅ 重新创建: {name} (在 {summary_plan_name} 下)')
                else:
                    # 检查是否已存在
                    plan, created = DeviceCollectionPlan.objects.get_or_create(
                        name=name,
                        defaults=plan_data_copy
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f'✅ 创建: {name} (在 {summary_plan_name} 下)')
                    else:
                        updated_count += 1
                        self.stdout.write(f'⚠️  已存在: {name} (在 {summary_plan_name} 下)')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n初始化完成！创建: {created_count}, 已存在: {updated_count}'
            )
        )
        
        # 显示统计信息
        total_plans = DeviceCollectionPlan.objects.count()
        self.stdout.write(f'\n当前共有 {total_plans} 个采集方案:')
        
        for summary_plan in summary_plans:
            plan_count = summary_plan.collect_plans.count()
            self.stdout.write(f'  - {summary_plan.name}: {plan_count} 个采集方案') 