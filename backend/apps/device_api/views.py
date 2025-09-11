import logging
from datetime import timedelta
from bson import ObjectId
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.device_api.models import DeviceSummaryPlans, DeviceCollectionPlan, NetconfXMLTemplate
from apps.device_api.serializers import (
    DeviceSummaryPlansSerializer, DeviceSummaryPlansCreateSerializer,
    DeviceSummaryPlansUpdateSerializer, DeviceSummaryPlansDetailSerializer,
    DeviceCollectionPlanSerializer, DeviceCollectionPlanCreateSerializer,
    DeviceCollectionPlanUpdateSerializer,
    NetconfXMLTemplateSerializer, NetconfXMLTemplateListSerializer,
    CollectionResultDetailSerializer, CollectionFilterSerializer
)
from apps.device_api.services import DeviceCollectionService
from apps.device_api import COLLECTION_RESULTS_DB
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.asset.models import NetworkDevice
from apps.device_api import COLLECTION_LOG_DB


logger = logging.getLogger(__name__)


class DeviceSummaryPlansViewSet(CustomViewBase):
    """采集汇总方案视图集"""
    queryset = DeviceSummaryPlans.objects.all()
    serializer_class = DeviceSummaryPlansSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['vendor', 'device_type', 'is_active']
    pagination_class = LargeResultsSetPagination
    search_fields = ['name', 'description']
    ordering_fields = ['id', 'name', 'vendor', 'device_type', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'create':
            return DeviceSummaryPlansCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceSummaryPlansUpdateSerializer
        elif self.action == 'retrieve':
            return DeviceSummaryPlansDetailSerializer
        return DeviceSummaryPlansSerializer

    def get_queryset(self):
        """获取查询集"""
        queryset = super().get_queryset()

        # 预加载相关数据
        queryset = queryset.prefetch_related('collect_plans', 'collect_plans__xml_templates')

        # 获取排序参数
        ordering = self.request.query_params.get('ordering', None)
        if ordering:
            # 验证排序字段是否有效
            valid_ordering_fields = ['id', 'name', 'vendor', 'device_type', 'created_at', 'updated_at']
            if ordering.lstrip('-') in valid_ordering_fields:
                # 如果用户指定了排序，使用用户指定的排序
                queryset = queryset.order_by(ordering)

        return queryset

    def create(self, request, *args, **kwargs):
        """重写create方法，确保返回正确的序列化数据"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 直接使用序列化器创建对象
        summary_plan = serializer.save()

        # 刷新实例，确保获取最新数据
        summary_plan.refresh_from_db()

        # 使用标准序列化器来序列化返回的对象
        response_serializer = DeviceSummaryPlansSerializer(summary_plan)
        return JsonResponse({
            'code': 201,
            'message': '创建成功',
            'data': response_serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除采集汇总方案"""
        try:
            summary_plan = self.get_object()
            plan_name = summary_plan.name
            plan_id = summary_plan.id

            # 删除关联的采集方案和XML模板
            collect_plans_count = summary_plan.collect_plans.count()
            xml_templates_count = 0

            for collect_plan in summary_plan.collect_plans.all():
                xml_templates_count += collect_plan.xml_templates.count()
                collect_plan.xml_templates.all().delete()

            summary_plan.collect_plans.all().delete()
            summary_plan.delete()

            return JsonResponse({
                "code": 200,
                "message": f"'{plan_name}' (ID: {plan_id}) 删除成功，同时删除了 {collect_plans_count} 个采集方案和 {xml_templates_count} 个XML模板",
                "data": {
                    "deleted_summary_plan": plan_name,
                    "deleted_collect_plans_count": collect_plans_count,
                    "deleted_xml_templates_count": xml_templates_count
                }
            })

        except Exception as e:
            logger.error(f"删除采集汇总方案失败: {str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"删除失败: {str(e)}",
                "data": None
            })

    @action(detail=True, methods=['get'])
    def collect_plans(self, request, *args, **kwargs):
        """获取指定汇总方案下的所有采集方案"""
        try:
            summary_plan = self.get_object()
            collect_plans = summary_plan.collect_plans.all()
            serializer = DeviceCollectionPlanSerializer(collect_plans, many=True)

            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"获取采集方案失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            })

    @action(detail=True, methods=['post'])
    def execute_all_collections(self, request, *args, **kwargs):
        """执行当前汇总采集方案下所有的子采集方案"""
        summary_plan = self.get_object()
        device_ip = request.data.get('device_ip')

        try:
            # 验证汇总方案是否启用
            if not summary_plan.is_active:
                return JsonResponse({
                    "code": 400,
                    "message": f"汇总方案 '{summary_plan.name}' 已被禁用"
                })

            # 验证设备IP参数
            if not device_ip:
                return JsonResponse({
                    "code": 400,
                    "message": "缺少必要参数: device_ip"
                })

            # 获取设备信息
            try:
                device = NetworkDevice.objects.get(manage_ip=device_ip)
            except NetworkDevice.DoesNotExist:
                return JsonResponse({
                    "code": 400,
                    "message": f"设备 {device_ip} 不存在"
                })

            # 获取所有启用的采集方案
            collect_plans = summary_plan.collect_plans.filter(is_active=True)
            if not collect_plans.exists():
                return JsonResponse({
                    "code": 400,
                    "message": f"汇总方案 '{summary_plan.name}' 下没有启用的采集方案"
                })

            # 执行所有采集方案
            results = []
            success_count = 0
            failed_count = 0

            for plan in collect_plans:
                try:
                    # 验证采集方案是否可用
                    netconf_available = plan.netconf_enabled and device.netconf_account
                    netmiko_available = plan.netmiko_enabled and device.ssh_account
                    
                    if not netconf_available and not netmiko_available:
                        # 跳过不可用的采集方案
                        result = {
                            'plan_id': plan.id,
                            'plan_name': plan.name,
                            'status': 'skipped',
                            'message': '采集方案不可用（未配置相应账户）'
                        }
                        results.append(result)
                        continue

                    # 执行双重采集
                    collection_result = DeviceCollectionService.execute_both_collection(plan, device)
                    
                    if collection_result['success']:
                        result = {
                            'plan_id': plan.id,
                            'plan_name': plan.name,
                            'status': 'success',
                            'message': collection_result['message'],
                            'netconf_result': collection_result['netconf_result'],
                            'netmiko_result': collection_result['netmiko_result']
                        }
                        success_count += 1
                    else:
                        result = {
                            'plan_id': plan.id,
                            'plan_name': plan.name,
                            'status': 'failed',
                            'message': collection_result['error']
                        }
                        failed_count += 1
                    
                    results.append(result)

                except Exception as e:
                    logger.error(f"执行采集方案失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}")
                    result = {
                        'plan_id': plan.id,
                        'plan_name': plan.name,
                        'status': 'failed',
                        'message': f'执行异常: {str(e)}'
                    }
                    results.append(result)
                    failed_count += 1

            # 构建响应消息
            total_plans = len(collect_plans)
            if success_count == total_plans:
                message = f"所有采集方案执行成功 ({success_count}/{total_plans})"
            elif success_count > 0:
                message = f"部分采集方案执行成功 ({success_count}/{total_plans})"
            else:
                message = f"所有采集方案执行失败 ({failed_count}/{total_plans})"

            return JsonResponse({
                "code": 200 if success_count > 0 else 500,
                "message": message,
                "data": {
                    "summary_plan_id": summary_plan.id,
                    "summary_plan_name": summary_plan.name,
                    "device_ip": device_ip,
                    "total_plans": total_plans,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "results": results
                }
            })

        except Exception as e:
            logger.error(f"执行汇总采集方案失败: 方案={summary_plan.name}, 设备={device_ip}, 错误={str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"执行失败: {str(e)}"
            })


class DeviceCollectionPlanViewSet(CustomViewBase):
    """设备采集方案视图集"""
    queryset = DeviceCollectionPlan.objects.all()
    serializer_class = DeviceCollectionPlanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['summary_plan', 'summary_plan__vendor', 'summary_plan__device_type', 'netmiko_enabled', 'netconf_enabled', 'is_active']
    pagination_class = LargeResultsSetPagination
    search_fields = ['name', 'description', 'summary_plan__name']
    ordering_fields = ['id', 'name', 'summary_plan__vendor', 'summary_plan__device_type', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'create':
            return DeviceCollectionPlanCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceCollectionPlanUpdateSerializer
        return DeviceCollectionPlanSerializer

    def get_queryset(self):
        """获取查询集"""
        queryset = super().get_queryset()
        
        # 预加载相关数据
        queryset = queryset.select_related('summary_plan').prefetch_related('xml_templates')

        # 根据summary_plan_id进行过滤
        summary_plan_id = self.request.query_params.get('summary_plan_id', None)
        if summary_plan_id:
            # 尝试转换为整数
            summary_plan_id = int(summary_plan_id)
            queryset = queryset.filter(summary_plan_id=summary_plan_id)
   
        # 获取排序参数
        ordering = self.request.query_params.get('ordering', None)
        if ordering:
            # 验证排序字段是否有效
            valid_ordering_fields = ['id', 'name', 'summary_plan__vendor', 'summary_plan__device_type', 'created_at', 'updated_at']
            if ordering.lstrip('-') in valid_ordering_fields:
                # 如果用户指定了排序，使用用户指定的排序
                queryset = queryset.order_by(ordering)

        return queryset

    def create(self, request, *args, **kwargs):
        """重写create方法，确保返回正确的序列化数据"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 直接使用序列化器创建对象
        collection_plan = serializer.save()

        # 刷新实例，确保获取最新数据
        collection_plan.refresh_from_db()
        
        # 使用标准序列化器来序列化返回的对象
        response_serializer = DeviceCollectionPlanSerializer(collection_plan)
        return JsonResponse({
            'code': 201,
            'message': '创建成功',
            'data': response_serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除采集方案"""
        try:
            collection_plan = self.get_object()
            plan_name = collection_plan.name
            plan_id = collection_plan.id

            # 删除关联的XML模板
            xml_templates_count = collection_plan.xml_templates.count()
            if xml_templates_count > 0:
                collection_plan.xml_templates.all().delete()

            # 删除采集方案
            collection_plan.delete()

            return JsonResponse({
                "code": 200,
                "message": f"'{plan_name}' (ID: {plan_id}) 删除成功",
                "data": {
                    "deleted_plan_id": plan_id,
                    "deleted_plan_name": plan_name,
                    "deleted_xml_templates_count": xml_templates_count
                }
            })

        except Exception as e:
            logger.error(f"删除采集方案失败: {str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"删除失败: {str(e)}",
                "data": ""
            })

    def validate_execution_params(self, plan, device_ip, collection_type):
        """验证采集执行参数
        
        Args:
            plan: 采集方案对象
            device_ip: 设备IP
            collection_type: 采集类型 ('netmiko', 'netconf' 或 'both')
            
        Returns:
            tuple: (is_valid, error_message, device)
        """
        try:
            # 1. 验证设备IP
            if not device_ip:
                return False, "缺少必要参数: device_ip", None
            
            # 2. 查询设备信息
            try:
                device = NetworkDevice.objects.get(manage_ip=device_ip)
            except NetworkDevice.DoesNotExist:
                return False, f"设备 {device_ip} 不存在", None
            
            # 3. 验证采集方案状态
            if not plan.is_active:
                return False, "采集方案已禁用，无法执行", None
            
            # 4. 根据采集类型进行特定验证
            if collection_type == 'netmiko':
                if not plan.netmiko_enabled:
                    return False, "采集方案未启用Netmiko采集方式", None
                if not device.ssh_account:
                    return False, f"设备 {device_ip} 未配置SSH账号", None
                return True, "验证通过", device
                
            elif collection_type == 'netconf':
                if not plan.netconf_enabled:
                    return False, "采集方案未启用NETCONF采集方式", None
                if not device.netconf_account:
                    return False, f"设备 {device_ip} 未配置netconf账号", None
                return True, "验证通过", device
                
            elif collection_type == 'both':
                # 检查是否至少启用了一种采集方式
                if not plan.netconf_enabled and not plan.netmiko_enabled:
                    return False, "采集方案未启用任何采集方式", None
                
                # 检查设备配置 - 只要有一种方式配置正确就可以
                netconf_available = plan.netconf_enabled and device.netconf_account
                netmiko_available = plan.netmiko_enabled and device.ssh_account
                
                if not netconf_available and not netmiko_available:
                    # 构建详细的错误信息
                    error_parts = []
                    if plan.netconf_enabled and not device.netconf_account:
                        error_parts.append("未配置NETCONF账户")
                    if plan.netmiko_enabled and not device.ssh_account:
                        error_parts.append("未配置SSH账户")
                    
                    return False, f"设备 {device_ip} {', '.join(error_parts)}", None
                
                return True, "验证通过", device
            else:
                return False, f"不支持的采集类型: {collection_type}", None
                
        except Exception as e:
            logger.error(f"验证采集执行参数失败: {str(e)}")
            return False, f"验证失败: {str(e)}", None

    @action(detail=True, methods=['post'])
    def update_field_mappings(self, request, *args, **kwargs):
        """更新字段映射"""

        plan = self.get_object()
        field_mappings_type = request.data.get('field_mappings_type')
        field_mappings = request.data.get('field_mappings')

        if not field_mappings_type or field_mappings is None:
            return JsonResponse({
                "code": 400,
                "message": "缺少必要参数: field_mappings_type, field_mappings",
                "data": ""
            })

        # 验证字段映射类型
        if field_mappings_type not in ['netconf', 'netmiko']:
            return JsonResponse({
                "code": 400,
                "message": "字段映射类型必须是 'netconf' 或 'netmiko'",
                "data": ""
            })

        updated_plan = DeviceCollectionService.update_field_mappings(
            plan, field_mappings_type, field_mappings
        )

        if updated_plan['success']:
            serializer = DeviceCollectionPlanSerializer(updated_plan['plan'])
            return JsonResponse({
                "code": 200,
                "message": "字段映射更新成功",
                "data": serializer.data
            })
        else:
            return JsonResponse({
                "code": 500,
                "message": f"更新失败: {updated_plan['error']}",
                "data": ""
            })

    @action(detail=True, methods=['post'])
    def update_data_processor(self, request, *args, **kwargs):
        """根据执行结果ID更新数据处理函数"""

        plan = self.get_object()

        data_processor_code = request.data.get('data_processor', '').strip()    # 去除首尾空白

        if data_processor_code and 'def' not in data_processor_code:
            return JsonResponse(
                data={"code": 400, "message": "数据处理函数代码必须包含函数定义 (def)。"}
            )

        plan.data_processor_enabled = True
        plan.data_processor = data_processor_code
        plan.save()

        return JsonResponse(data={
            "code": 200,
            "message": "更新成功"
        })

    @action(detail=True, methods=['post'])
    def execute_netmiko(self, request, *args, **kwargs):
        """执行Netmiko采集"""
        plan = self.get_object()
        device_ip = request.data.get('device_ip')

        try:
            # 数据验证
            is_valid, error_msg, device = self.validate_execution_params(plan, device_ip, 'netmiko')
            if not is_valid:
                return JsonResponse({
                    "code": 400,
                    "message": error_msg
                })
            
            # 第一步：执行Netmiko采集（仅执行命令，不保存结果）
            ok, message, collection_result = DeviceCollectionService.execute_netmiko_collection_only(plan, device)
            if not ok:
                return JsonResponse({
                    "code": 500,
                    "message": f"Netmiko采集失败: {message}"
                })
            
            # 第二步：保存采集结果到MongoDB（只有在采集成功时才保存）
            if collection_result is not None:
                save_ok, save_message = DeviceCollectionService.save_collection_result(collection_result)
                if not save_ok:
                    logger.warning(f"采集成功但保存失败: {device_ip} - {save_message}")
                    return JsonResponse({
                        "code": 200,
                        "message": f"采集成功，但保存失败: {save_message}"
                    })
            
            return JsonResponse({
                "code": 200,
                "message": "Netmiko采集执行成功"
            })

        except Exception as e:
            logger.error(f"Netmiko采集执行失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"Netmiko采集失败: {str(e)}"
            })

    @action(detail=True, methods=['post'])
    def execute_netconf(self, request, *args, **kwargs):
        """执行NETCONF采集"""
        plan = self.get_object()
        device_ip = request.data.get('device_ip')

        try:
            # 数据验证
            is_valid, error_msg, device = self.validate_execution_params(plan, device_ip, 'netconf')
            if not is_valid:
                return JsonResponse({
                    "code": 400,
                    "message": error_msg
                })
            
            # 第一步：执行NETCONF采集（仅执行采集，不保存结果）
            ok, message, collection_result = DeviceCollectionService.execute_netconf_collection_only(plan, device)
            if not ok:
                return JsonResponse({
                    "code": 500,
                    "message": f"NETCONF采集失败: {message}"
                })
            
            # 第二步：保存采集结果到MongoDB（只有在采集成功时才保存）
            if collection_result is not None:
                save_ok, save_message = DeviceCollectionService.save_collection_result(collection_result)
                if not save_ok:
                    logger.warning(f"采集成功但保存失败: {device_ip} - {save_message}")
                    return JsonResponse({
                        "code": 200,
                        "message": f"采集成功，但保存失败: {save_message}"
                    })
            
            return JsonResponse({
                "code": 200,
                "message": "NETCONF采集执行成功"
            })

        except Exception as e:
            logger.error(f"NETCONF采集执行失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"NETCONF采集失败: {str(e)}"
            })

    @action(detail=True, methods=['post'])
    def execute_both_collection(self, request, *args, **kwargs):
        """同时执行NETCONF和Netmiko采集"""
        plan = self.get_object()
        device_ip = request.data.get('device_ip')

        try:
            # 使用统一的参数验证方法
            is_valid, error_msg, device = self.validate_execution_params(plan, device_ip, 'both')
            if not is_valid:
                return JsonResponse({
                    "code": 400,
                    "message": error_msg
                })

            # 执行双重采集
            result = DeviceCollectionService.execute_both_collection(plan, device)
            
            if result['success']:
                return JsonResponse({
                    "code": 200,
                    "message": result['message'],
                    "data": {
                        "netconf_result": result['netconf_result'],
                        "netmiko_result": result['netmiko_result']
                    }
                })
            else:
                return JsonResponse({
                    "code": 500,
                    "message": result['error']
                })

        except Exception as e:
            logger.error(f"双重采集执行失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"双重采集失败: {str(e)}"
            })

    @action(detail=False, methods=['post'])
    def execute_data_processor(self, request, *args, **kwargs):
        """执行数据处理函数，将采集结果转换为标准数据格式"""
        try:
            # 获取请求参数
            result_id = request.data.get('result_id')

            # 调用服务层执行数据处理
            result = DeviceCollectionService.execute_data_processor(result_id)
            
            if result['success']:
                return JsonResponse({
                    'code': 200,
                    'message': '数据处理执行成功',
                    'data': result['data']
                })
            else:
                # 根据错误类型返回相应的状态码
                error_code = result.get('code', 500)
                return JsonResponse({
                    'code': error_code,
                    'message': result['error'],
                    'data': result.get('data', None)
                })
                
        except Exception as e:
            logger.error(f"执行数据处理失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'执行失败: {str(e)}',
                'data': None
            })


class NetconfXMLTemplateViewSet(CustomViewBase):
    """NETCONF XML模板视图集"""
    queryset = NetconfXMLTemplate.objects.all()
    serializer_class = NetconfXMLTemplateSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['collection_plan', 'is_active']
    pagination_class = LargeResultsSetPagination
    search_fields = ['name', 'description', 'collection_plan__name']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['collection_plan', 'name']
    
    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'list':
            return NetconfXMLTemplateListSerializer
        return NetconfXMLTemplateSerializer
    
    def get_queryset(self):
        """获取查询集"""
        queryset = super().get_queryset()

        plan_id = self.request.query_params.get('plan_id', None)
        if plan_id:
            # 尝试转换为整数
            plan_id = int(plan_id)
            queryset = queryset.filter(collection_plan_id=plan_id)
        
        # 预加载相关数据
        queryset = queryset.select_related('collection_plan', 'collection_plan__summary_plan')
        
        return queryset

    @action(detail=False, methods=['get'])
    def by_collection_plan(self, request):
        """根据采集方案获取XML模板"""
        try:
            plan_id = request.GET.get('plan_id')
            if not plan_id:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少plan_id参数',
                    'data': None
                })
            
            templates = DeviceCollectionService.get_xml_templates_by_plan(int(plan_id))
            serializer = self.get_serializer(templates, many=True)
            
            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"获取XML模板失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            }) 


class CollectionResultViewSet(CustomViewBase):
    """采集结果视图集"""
    
    # 移除Django ORM相关的配置，因为数据在MongoDB中
    queryset = None
    serializer_class = None
    pagination_class = None

    @action(detail=False, methods=['get'])
    def list_results(self, request):
        """获取采集结果列表"""
        try:
            # 验证查询参数
            filter_serializer = CollectionFilterSerializer(data=request.GET)
            if not filter_serializer.is_valid():
                return JsonResponse({
                    'code': 400,
                    'message': '查询参数无效',
                    'data': filter_serializer.errors
                })
            
            filter_data = filter_serializer.validated_data
            
            # 构建MongoDB查询条件
            query = {}
            
            # 基本字段过滤
            if filter_data.get('plan_id'):
                query['plan_id'] = filter_data['plan_id']
            if filter_data.get('plan_name'):
                query['plan_name'] = {'$regex': filter_data['plan_name'], '$options': 'i'}
            if filter_data.get('device_ip'):
                query['device_ip'] = filter_data['device_ip']
            if filter_data.get('device_name'):
                query['device_name'] = {'$regex': filter_data['device_name'], '$options': 'i'}
            if filter_data.get('collection_method'):
                query['collection_method'] = filter_data['collection_method']
            if filter_data.get('method_name'):
                query['method_name'] = {'$regex': filter_data['method_name'], '$options': 'i'}
            if filter_data.get('status'):
                query['status'] = filter_data['status']
            if filter_data.get('vendor'):
                query['vendor'] = filter_data['vendor']
            if filter_data.get('device_type'):
                query['device_type'] = filter_data['device_type']
            
            # 时间范围过滤
            time_query = {}
            if filter_data.get('start_date') and filter_data.get('end_date'):
                start_date = f"{filter_data['start_date']}T00:00:00"
                end_date = f"{filter_data['end_date']}T23:59:59"
                time_query = {'$gte': start_date, '$lte': end_date}
            elif filter_data.get('start_time') and filter_data.get('end_time'):
                time_query = {'$gte': filter_data['start_time'], '$lte': filter_data['end_time']}
            elif filter_data.get('days'):
                end_time = timezone.now()
                start_time = end_time - timedelta(days=filter_data['days'])
                time_query = {'$gte': start_time.isoformat(), '$lte': end_time.isoformat()}
            
            if time_query:
                query['collected_at'] = time_query
            
            # 分页和排序参数
            page = filter_data.get('page', 1)
            page_size = filter_data.get('page_size', 10)
            sort_by = filter_data.get('sort_by', 'collected_at')
            sort_order = filter_data.get('sort_order', 'desc')
            sort_direction = -1 if sort_order == 'desc' else 1
            
            # 使用 MongoOps 内置的分页查询
            # 构建排序参数
            sort_param = (sort_by, sort_direction) if sort_by and sort_direction else None
            
            # 执行分页查询
            results = COLLECTION_RESULTS_DB.find_page_query(
                query_dict=query,
                sort=sort_param,
                page_size=page_size,
                page_num=page
            )
            
            # 获取总数
            total_count = COLLECTION_RESULTS_DB.count_documents(query)
            
            # 序列化结果
            serializer = CollectionResultDetailSerializer(results, many=True)
            
            # 构建分页响应
            total_pages = (total_count + page_size - 1) // page_size
            response_data = {
                'code': 200,
                'message': '获取成功',
                'count': total_count,
                'next': page + 1 if page < total_pages else None,
                'previous': page - 1 if page > 1 else None,
                'results':  serializer.data
            }
            
            return JsonResponse(response_data)
                
        except Exception as e:
            logger.error(f"获取采集结果列表失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            })

    @action(detail=False, methods=['get'])
    def by_plan(self, request):
        """根据采集方案ID查询最新的10条结果，逆序返回"""
        try:
            plan_id = request.GET.get('plan_id')
            collection_method = request.GET.get('collection_method')
            device_ip = request.GET.get('device_ip')
            status = request.GET.get('status')
            
            # 构建查询条件
            query = {}
            if plan_id:
                query['plan_id'] = int(plan_id)
            if collection_method:
                query['collection_method'] = collection_method
            if device_ip:
                query['device_ip'] = device_ip
            if status:
                query['status'] = status
            
            # 直接使用MongoDB原生查询确保正确的排序和限制
            # 查询最新的10条结果，按collected_at倒序排列
            cursor = COLLECTION_RESULTS_DB.coll.find(query).sort('collected_at', -1).limit(10)
            results = list(cursor)

            # 序列化结果
            serializer = CollectionResultDetailSerializer(results, many=True)
            
            response_data = {
                'code': 200,
                'message': '获取成功',
                'plan_id': plan_id,
                'collection_method': collection_method,
                'latest_count': len(serializer.data),
                'results': serializer.data
            }
            return JsonResponse(response_data)
                
        except Exception as e:
            logger.error(f"根据条件查询最新结果失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'查询失败: {str(e)}',
                'data': None
            })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取采集结果统计信息"""
        try:
            # 获取查询参数
            plan_id = request.GET.get('plan_id')
            collection_method = request.GET.get('collection_method')
            days = int(request.GET.get('days', 7))

            # 构建查询条件
            query = {}
            if plan_id:
                try:
                    query['plan_id'] = int(plan_id)
                except ValueError:
                    return JsonResponse({
                        'code': 400,
                        'message': 'plan_id必须是整数',
                        'data': None
                    })

            if collection_method:
                if collection_method not in ['netmiko', 'netconf']:
                    return JsonResponse({
                        'code': 400,
                        'message': 'collection_method必须是 netmiko 或 netconf',
                        'data': None
                    })
                query['collection_method'] = collection_method

            # 时间范围
            end_time = timezone.now()
            start_time = end_time - timedelta(days=days)
            query['collected_at'] = {
                '$gte': start_time.isoformat(),
                '$lte': end_time.isoformat()
            }

            # 统计总数
            total_count = COLLECTION_RESULTS_DB.count_documents(query)

            # 按状态统计
            status_pipeline = [
                {'$match': query},
                {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
            ]
            status_stats = list(COLLECTION_RESULTS_DB.aggregate(status_pipeline))

            # 按采集方式统计
            method_pipeline = [
                {'$match': query},
                {'$group': {'_id': '$collection_method', 'count': {'$sum': 1}}}
            ]
            method_stats = list(COLLECTION_RESULTS_DB.aggregate(method_pipeline))

            # 按天统计
            daily_pipeline = [
                {'$match': query},
                {
                    '$group': {
                        '_id': {
                            '$dateToString': {
                                'format': '%Y-%m-%d',
                                'date': {'$dateFromString': {'dateString': '$collected_at'}}
                            }
                        },
                        'count': {'$sum': 1}
                    }
                },
                {'$sort': {'_id': 1}}
            ]
            daily_stats = list(COLLECTION_RESULTS_DB.aggregate(daily_pipeline))

            response_data = {
                'code': 200,
                'message': '获取成功',
                'data': {
                    'total_count': total_count,
                    'status_statistics': status_stats,
                    'method_statistics': method_stats,
                    'daily_statistics': daily_stats,
                    'time_range': {
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat(),
                        'days': days
                    },
                    'filters': {
                        'plan_id': plan_id,
                        'collection_method': collection_method
                    }
                }
            }

            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"获取采集结果统计信息失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            })

    @action(detail=False, methods=['get'])
    def result_detail(self, request, *args, **kwargs):
        """获取采集结果详情"""
        try:
            # 验证ObjectId格式
            try:
                object_id_str = self.request.query_params.get('result_id', "")
                object_id = ObjectId(object_id_str)
            except Exception as e:
                logger.error(f"{e}")
                return JsonResponse({
                    'code': 400,
                    'message': '无效的结果ID格式',
                    'data': None
                })
            
            # 使用 MongoOps 查询单个文档
            results = COLLECTION_RESULTS_DB.find({'_id': object_id})
            
            if not results:
                return JsonResponse({
                    'code': 404,
                    'message': '采集结果不存在',
                    'data': None
                })
            
            # 获取第一个匹配的文档
            result = results[0]
            
            # 序列化结果
            serializer = CollectionResultDetailSerializer(result)
            
            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': serializer.data
            })
                
        except Exception as e:
            logger.error(f"获取采集结果详情失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            })


class CollectionLogViewSet(CustomViewBase):
    """采集日志视图集"""

    queryset = None
    serializer_class = None
    pagination_class = None

    @action(detail=False, methods=['get'])
    def list_logs(self, request):
        """获取采集日志列表"""
        try:
            # 获取查询参数
            summary_plan_id = request.query_params.get('summary_plan_id')
            plan_id = request.query_params.get('plan_id')
            device_ip = request.query_params.get('device_ip')
            collection_type = request.query_params.get('collection_type')
            status = request.query_params.get('status')
            start_time = request.query_params.get('start_time')
            end_time = request.query_params.get('end_time')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            
            # 构建查询条件
            query = {}
            
            if device_ip:
                query['device_ip'] = device_ip
            if summary_plan_id:
                query['summary_plan_id'] = int(summary_plan_id)
            if plan_id:
                query['plan_id'] = int(plan_id)
            if collection_type:
                query['collection_type'] = collection_type
            if status:
                query['status'] = status
                
            # 时间范围查询
            if start_time or end_time:
                time_query = {}
                if start_time:
                    time_query['$gte'] = start_time
                if end_time:
                    time_query['$lte'] = end_time
                query['executed_at'] = time_query
            
            # 执行查询

            logs = COLLECTION_LOG_DB.find_page_query(
                query_dict=query,
                sort=('executed_at', -1),
                page_size=page_size,
                page_num=page
            )

            # 获取总数
            total_count = COLLECTION_LOG_DB.count_documents(query)
            
            # 转换为列表
            log_list = []
            for log in logs:
                log['_id'] = str(log['_id'])
                log_list.append(log)

            return JsonResponse(data={
                'code': 200,
                'message': '获取成功',
                'count': total_count,
                'results': log_list
            })

        except Exception as e:
            logger.error(f"获取采集日志失败: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'count': 0,
                'results': None
            })
