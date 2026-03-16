import logging
from datetime import timedelta
from bson import ObjectId
from django.apps import apps
from django.http import JsonResponse
from django.db.models import CharField, ForeignKey, GenericIPAddressField
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.device_api.filters import (
    DeviceCollectionMatchRuleFilter,
    DeviceCollectionRuleFilter,
    DeviceCollectionPlansFilter,
    DeviceSubCollectionPlanFilter,
    PlansToDeviceFilter,
    PlatformProfileFilter,
)
from apps.device_api.models import (
    DeviceCollectionMatchRule,
    DeviceCollectionRule,
    DeviceCollectionPlans,
    DeviceDiscoveryState,
    DeviceSubCollectionPlan,
    NetconfXMLTemplate,
    PlansToDevice,
    PlatformProfile,
)
from apps.device_api.models_api import plan_data_to_mongodb, celery_data_mongodb
from apps.device_api.analysis_hooks import (
    INTERFACE_ANALYSIS_COLLECTION_TYPES,
    extract_webhook_args,
    maybe_schedule_interface_utilization,
)
from apps.device_api.serializers import (
    DeviceCollectionMatchRuleSerializer,
    DeviceCollectionRuleSerializer,
    DeviceCollectionPlansSerializer, DeviceCollectionPlansCreateSerializer,
    DeviceCollectionPlansUpdateSerializer, DeviceCollectionPlansDetailSerializer,
    DeviceSubCollectionPlanSerializer, DeviceSubCollectionPlanCreateSerializer,
    DeviceSubCollectionPlanUpdateSerializer,
    NetconfXMLTemplateSerializer, NetconfXMLTemplateListSerializer,
    CollectionResultDetailSerializer, CollectionFilterSerializer,
    CollectionResultByPlanSerializer, PlansToDeviceSerializer,
    PlatformProfileSerializer, DeviceFactsSerializer, DeviceCapabilitiesSerializer,
    DeviceDiscoveryStateSerializer,
)
from apps.device_api.platform_profiles import PlatformProfileService
from apps.device_api.services_new import DeviceCollectionService
from apps.device_api import COLLECTION_RESULTS_DB, COLLECTION_PLAN, COLLECTION_SUB_PLAN
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.asset.models import NetworkDevice
from apps.device_api.fields_mapping import DEFAULT_COLLECTION_TYPES, field_mapping
from apps.device_api.services_new import FieldMappingDriver
from confload.confload import config
from utils.db.mongo_ops import MongoOps

logger = logging.getLogger(__name__)


class PlatformProfileViewSet(CustomViewBase):
    queryset = PlatformProfile.objects.all()
    serializer_class = PlatformProfileSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PlatformProfileFilter
    search_fields = ['code', 'vendor_alias', 'category', 'os_family']
    ordering_fields = ['code', 'vendor_alias', 'category', 'updated_at']
    ordering = ['code']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        PlatformProfileService.ensure_builtin_profiles()
        return super().get_queryset()


class DeviceCollectionMatchRuleViewSet(CustomViewBase):
    queryset = DeviceCollectionMatchRule.objects.all().order_by("-id")
    serializer_class = DeviceCollectionMatchRuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeviceCollectionMatchRuleFilter
    search_fields = ["name", "fields", "value"]
    ordering_fields = ["id", "name"]
    ordering = ["-id"]
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        return DeviceCollectionMatchRuleSerializer.setup_eager_loading(super().get_queryset())


class DeviceCollectionRuleViewSet(CustomViewBase):
    queryset = DeviceCollectionRule.objects.all().order_by("-id")
    serializer_class = DeviceCollectionRuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeviceCollectionRuleFilter
    search_fields = ["name", "module", "method", "plugin"]
    ordering_fields = ["id", "name", "module", "method"]
    ordering = ["-id"]
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        return DeviceCollectionRuleSerializer.setup_eager_loading(super().get_queryset())


class DeviceCollectionRuleToolView(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if "get_cmdb_field" in get_param:
            model = apps.get_model(app_label="asset", model_name="NetworkDevice")
            fields = model._meta.get_fields()
            field_res = []
            for field in fields:
                if isinstance(field, ForeignKey):
                    related_model = field.related_model
                    for related_field in related_model._meta.get_fields():
                        if isinstance(related_field, CharField):
                            field_res.append(
                                {
                                    "label": f"{field.verbose_name}-{related_field.verbose_name}",
                                    "value": f"{field.name}__{related_field.name}",
                                }
                            )
                if isinstance(field, CharField) or isinstance(field, GenericIPAddressField):
                    field_res.append(
                        {
                            "label": getattr(field, "verbose_name", field.name),
                            "value": field.name,
                        }
                    )
            return JsonResponse({"code": 200, "msg": "success", "data": field_res})
        if "get_pulgin_list" in get_param:
            from driver import auto_driver_map

            return JsonResponse({"code": 200, "msg": "success", "data": auto_driver_map})
        return JsonResponse({"code": 400, "msg": "未匹配动作"})

    def post(self, request):
        return JsonResponse({"code": 400, "msg": "未匹配动作"})


class PlansToDeviceViewSet(CustomViewBase):
    """采集方案和设备关联序列化"""
    queryset = PlansToDevice.objects.all()
    serializer_class = PlansToDeviceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PlansToDeviceFilter
    search_fields = ['manage_ip', 'device_serial_num', 'execute_node', 'profile_code']
    ordering_fields = ['manage_ip', 'device_serial_num', 'created_at', 'updated_at']
    ordering = ['-created_at']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        """获取查询集"""

        return self.queryset.select_related("plan")

    @action(detail=False, methods=['post'])
    def auto_bind(self, request, *args, **kwargs):
        queryset = NetworkDevice.objects.filter(status=0, auto_enable=True).select_related(
            "vendor", "category", "model"
        )
        manage_ip = (request.data.get("manage_ip") or "").strip()
        serial_num = (request.data.get("serial_num") or "").strip()
        vendor_alias = (request.data.get("vendor_alias") or "").strip()
        profile_code = (request.data.get("profile_code") or "").strip()

        if manage_ip:
            queryset = queryset.filter(manage_ip=manage_ip)
        if serial_num:
            queryset = queryset.filter(serial_num=serial_num)
        if vendor_alias:
            queryset = queryset.filter(vendor__alias=vendor_alias)
        if profile_code:
            serial_nums = list(
                DeviceDiscoveryState.objects.filter(profile_code=profile_code)
                .values_list("device_serial_num", flat=True)
            )
            queryset = queryset.filter(serial_num__in=serial_nums)

        result = PlatformProfileService.auto_bind_devices(list(queryset))
        return JsonResponse({
            'code': 200,
            'message': '自动绑定完成',
            'data': result,
        })


class DeviceFactsAPIView(APIView):
    def get(self, request, serial_num):
        device = (
            NetworkDevice.objects.select_related("vendor", "category", "model", "plan")
            .filter(serial_num=serial_num)
            .first()
        )
        if not device:
            return JsonResponse({'code': 404, 'message': '设备不存在', 'data': None})
        serializer = DeviceFactsSerializer(device)
        discovery_state = DeviceDiscoveryState.objects.filter(device_serial_num=serial_num).first()
        discovery_payload = (
            DeviceDiscoveryStateSerializer(discovery_state).data if discovery_state else {}
        )
        return JsonResponse(
            {
                'code': 200,
                'message': '获取成功',
                'data': {
                    **serializer.data,
                    **discovery_payload,
                },
            }
        )


class DeviceCapabilitiesAPIView(APIView):
    def get(self, request, serial_num):
        device = (
            NetworkDevice.objects.select_related("vendor", "category", "model")
            .filter(serial_num=serial_num)
            .first()
        )
        if not device:
            return JsonResponse({'code': 404, 'message': '设备不存在', 'data': None})
        data = PlatformProfileService.build_capabilities(device)
        serializer = DeviceCapabilitiesSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return JsonResponse({'code': 200, 'message': '获取成功', 'data': serializer.validated_data})


class DeviceCollectionPlansViewSet(CustomViewBase):
    """父级采集方案视图"""
    queryset = DeviceCollectionPlans.objects.all()
    serializer_class = DeviceCollectionPlansSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeviceCollectionPlansFilter
    search_fields = ['name', 'description']
    ordering_fields = ['id', 'name', 'vendor', 'device_type', 'created_at', 'updated_at']
    ordering = ['-created_at']
    pagination_class = LargeResultsSetPagination

    @staticmethod
    def _plan_has_enabled_method(plan):
        return any(
            bool(getattr(plan, field_name, False))
            for field_name in (
                'netmiko_enabled',
                'netconf_enabled',
                'snmp_enabled',
                'restconf_enabled',
                'telemetry_enabled',
            )
        )

    @staticmethod
    def _build_plan_execution_payload(plan, status, message, collection_result=None):
        payload = {
            'plan_id': plan.id,
            'plan_name': plan.name,
            'collection_type': getattr(plan, 'collection_type', ''),
            'status': status,
            'message': message,
        }
        if collection_result is not None:
            payload.update(
                {
                    'netconf_result': collection_result.get('netconf_result'),
                    'netmiko_result': collection_result.get('netmiko_result'),
                    'snmp_result': collection_result.get('snmp_result'),
                    'restconf_result': collection_result.get('restconf_result'),
                    'telemetry_result': collection_result.get('telemetry_result'),
                }
            )
        return payload

    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'create':
            return DeviceCollectionPlansCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceCollectionPlansUpdateSerializer
        elif self.action == 'retrieve':
            return DeviceCollectionPlansDetailSerializer
        return DeviceCollectionPlansSerializer

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
        response_serializer = DeviceCollectionPlansSerializer(summary_plan)
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
            serializer = DeviceSubCollectionPlanSerializer(collect_plans, many=True)

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
    def sync_collect_plans(self, request, *args, **kwargs):
        """按父方案配置补齐并同步默认子采集方案。"""
        try:
            summary_plan = self.get_object()
            sync_result = DeviceCollectionService.sync_summary_plan_sub_plans(summary_plan)
            profile_code = getattr(summary_plan, "profile_code", "")
            if profile_code:
                profile = PlatformProfile.objects.filter(code=profile_code).first()
                if profile:
                    PlatformProfileService.apply_profile_defaults(summary_plan, profile)
            summary_plan.refresh_from_db()
            serializer = DeviceCollectionPlansDetailSerializer(summary_plan)

            return JsonResponse({
                'code': 200,
                'message': '同步成功',
                'data': {
                    'summary_plan': serializer.data,
                    **sync_result,
                }
            })
        except Exception as e:
            logger.error(f"同步采集方案失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'同步失败: {str(e)}',
                'data': None
            })

    @action(detail=True, methods=['get', 'patch'], url_path='field-mappings')
    def field_mappings(self, request, *args, **kwargs):
        """按 collection_type 聚合父方案字段映射，并支持批量回写。"""
        try:
            summary_plan = self.get_object()
            if request.method.lower() == 'get':
                data = DeviceCollectionService.get_summary_plan_field_mappings(summary_plan)
                return JsonResponse({
                    'code': 200,
                    'message': '获取成功',
                    'data': data,
                })

            data = DeviceCollectionService.update_summary_plan_field_mappings(
                summary_plan,
                request.data,
            )
            return JsonResponse({
                'code': 200,
                'message': '更新成功',
                'data': data,
            })
        except ValueError as e:
            return JsonResponse({
                'code': 400,
                'message': str(e),
                'data': None,
            })
        except Exception as e:
            logger.error(f"父方案字段映射聚合操作失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'操作失败: {str(e)}',
                'data': None,
            })

    @action(detail=True, methods=['post'], url_path='validate')
    def validate_plan(self, request, *args, **kwargs):
        """按父方案聚合执行所有启用子方案的验证，并按 collection_type 分组返回结果。"""
        summary_plan = self.get_object()
        device_ip = (request.data.get('device_ip') or '').strip()
        south_driver = request.data.get('south_driver')
        use_local = request.data.get('use_local', False)

        try:
            if not summary_plan.is_active:
                return JsonResponse({
                    'code': 400,
                    'message': f"汇总方案 '{summary_plan.name}' 已被禁用",
                    'data': None,
                })

            if not device_ip:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少必要参数: device_ip',
                    'data': None,
                })

            enabled_plans = [
                plan for plan in summary_plan.collect_plans.all()
                if self._plan_has_enabled_method(plan)
            ]
            if not enabled_plans:
                return JsonResponse({
                    'code': 400,
                    'message': f"汇总方案 '{summary_plan.name}' 下没有启用的采集方案",
                    'data': None,
                })

            if not use_local and not south_driver:
                return JsonResponse({
                    'code': 400,
                    'message': '南向驱动方式执行时缺少参数: south_driver；若需本机直连执行请传 use_local=true',
                    'data': None,
                })

            results = []
            success_count = 0
            failed_count = 0
            skipped_count = 0

            for plan in enabled_plans:
                try:
                    is_valid, error_msg, device = DeviceSubCollectionPlanViewSet.validate_execution_params(
                        plan, device_ip, 'both', use_local=use_local
                    )
                    if not is_valid:
                        results.append(
                            self._build_plan_execution_payload(plan, 'skipped', error_msg)
                        )
                        skipped_count += 1
                        continue

                    if use_local:
                        execution_result = DeviceCollectionService.execute_both_collection_local(plan, device)
                    else:
                        execution_result = DeviceCollectionService.execute_both_collection(
                            plan, device, south_driver
                        )

                    if execution_result.get('success'):
                        results.append(
                            self._build_plan_execution_payload(
                                plan,
                                'success',
                                execution_result.get('message', '验证成功'),
                                execution_result,
                            )
                        )
                        success_count += 1
                    else:
                        results.append(
                            self._build_plan_execution_payload(
                                plan,
                                'failed',
                                execution_result.get('error', '验证失败'),
                                execution_result,
                            )
                        )
                        failed_count += 1
                except Exception as e:
                    logger.error(f"父方案一键验证失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}", exc_info=True)
                    results.append(
                        self._build_plan_execution_payload(plan, 'failed', f'执行异常: {str(e)}')
                    )
                    failed_count += 1

            grouped_results = {}
            for result in results:
                grouped_results.setdefault(result['collection_type'], []).append(result)

            total_plans = len(enabled_plans)
            if success_count == total_plans:
                message = f"所有采集方案验证成功 ({success_count}/{total_plans})"
            elif success_count > 0:
                message = (
                    f"部分采集方案验证成功 ({success_count}/{total_plans})，"
                    f"失败 {failed_count}，跳过 {skipped_count}"
                )
            elif skipped_count == total_plans:
                message = f"所有采集方案均未通过前置校验 ({skipped_count}/{total_plans})"
            else:
                message = f"所有采集方案验证失败 ({failed_count}/{total_plans})"

            result_code = 200 if success_count > 0 else 500
            if skipped_count == total_plans:
                result_code = 400

            return JsonResponse({
                'code': result_code,
                'message': message,
                'data': {
                    'summary_plan_id': summary_plan.id,
                    'summary_plan_name': summary_plan.name,
                    'device_ip': device_ip,
                    'total_plans': total_plans,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count,
                    'results': grouped_results,
                },
            })
        except Exception as e:
            logger.error(f"父方案一键验证失败: 方案={summary_plan.name}, 设备={device_ip}, 错误={str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'验证失败: {str(e)}',
                'data': None,
            })

    @action(detail=True, methods=['post'])
    def execute_all_collections(self, request, *args, **kwargs):
        """执行当前汇总采集方案下所有的子采集方案"""
        summary_plan = self.get_object()
        device_ip = request.data.get('device_ip')
        south_driver = request.data.get('south_driver')
        use_local = request.data.get('use_local', False)

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
            collect_plans = summary_plan.collect_plans.all()
            if not collect_plans.exists():
                return JsonResponse({
                    "code": 400,
                    "message": f"汇总方案 '{summary_plan.name}' 下没有采集方案"
                })

            if not use_local and not south_driver:
                return JsonResponse({
                    "code": 400,
                    "message": "南向驱动方式执行时缺少参数: south_driver；若需本机直连执行请传 use_local=true"
                })

            # 执行所有采集方案
            results = []
            success_count = 0
            failed_count = 0
            interface_trigger = {
                "scheduled": False,
                "reason": "no_interface_collection_success",
            }

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
                    if use_local:
                        collection_result = DeviceCollectionService.execute_both_collection_local(plan, device)
                    else:
                        collection_result = DeviceCollectionService.execute_both_collection(plan, device, south_driver)

                    if collection_result['success']:
                        result = {
                            'plan_id': plan.id,
                            'plan_name': plan.name,
                            'status': 'success',
                            'message': collection_result['message'],
                            'netconf_result': collection_result['netconf_result'],
                            'netmiko_result': collection_result['netmiko_result'],
                            'execute_time': collection_result.get('execute_time', ''),
                        }
                        success_count += 1
                        if use_local and plan.collection_type in INTERFACE_ANALYSIS_COLLECTION_TYPES:
                            interface_trigger = maybe_schedule_interface_utilization(
                                collection_type=plan.collection_type,
                                device_ip=device_ip,
                                execute_time=collection_result.get("execute_time"),
                                triggered_by="device_api-execute_all_collections-local",
                            )
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
                    "results": results,
                    "analysis_trigger": interface_trigger,
                }
            })

        except Exception as e:
            logger.error(f"执行汇总采集方案失败: 方案={summary_plan.name}, 设备={device_ip}, 错误={str(e)}")
            return JsonResponse({
                "code": 500,
                "message": f"执行失败: {str(e)}"
            })


class LegacyCollectionPlanViewSet(DeviceCollectionPlansViewSet):
    """automation.collection_plan 兼容入口，仅保留只读访问。"""

    def create(self, request, *args, **kwargs):
        return JsonResponse({"code": 405, "message": "legacy 接口只读，请改用 /device_api/collection-plans/", "data": None})

    def update(self, request, *args, **kwargs):
        return JsonResponse({"code": 405, "message": "legacy 接口只读，请改用 /device_api/collection-plans/", "data": None})

    def partial_update(self, request, *args, **kwargs):
        return JsonResponse({"code": 405, "message": "legacy 接口只读，请改用 /device_api/collection-plans/", "data": None})

    def destroy(self, request, *args, **kwargs):
        return JsonResponse({"code": 405, "message": "legacy 接口只读，请改用 /device_api/collection-plans/", "data": None})


class DeviceSubCollectionPlanViewSet(CustomViewBase):
    """子采集方案视图"""
    queryset = DeviceSubCollectionPlan.objects.all()
    serializer_class = DeviceSubCollectionPlanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeviceSubCollectionPlanFilter
    search_fields = ['name', 'description']
    ordering_fields = ['id', 'name', 'summary_plan__vendor', 'summary_plan__device_type', 'created_at', 'updated_at']
    ordering = ['-created_at']
    pagination_class = LargeResultsSetPagination
    
    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'create':
            return DeviceSubCollectionPlanCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceSubCollectionPlanUpdateSerializer
        return DeviceSubCollectionPlanSerializer

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
        response_serializer = DeviceSubCollectionPlanSerializer(collection_plan)
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

    @staticmethod
    def validate_execution_params(plan, device_ip, collection_type, use_local=False):
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
            devices = NetworkDevice.objects.select_related('idc').filter(manage_ip=device_ip)
            
            if not devices.exists():
                return False, f"设备 {device_ip} 不存在", None
            device = devices.first()

            # 3. 根据采集类型进行特定验证
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
                enabled_methods = {
                    'netmiko': bool(plan.netmiko_enabled),
                    'netconf': bool(plan.netconf_enabled),
                    'snmp': bool(getattr(plan, 'snmp_enabled', False)),
                    'restconf': bool(getattr(plan, 'restconf_enabled', False)),
                    'telemetry': bool(getattr(plan, 'telemetry_enabled', False)),
                }

                if not any(enabled_methods.values()):
                    return False, "采集方案未启用任何采集方式", None

                available_methods = []
                error_parts = []

                if enabled_methods['netmiko']:
                    if device.ssh_account:
                        available_methods.append('netmiko')
                    else:
                        error_parts.append("未配置SSH账户")

                if enabled_methods['netconf']:
                    if device.netconf_account:
                        available_methods.append('netconf')
                    else:
                        error_parts.append("未配置NETCONF账户")

                if use_local:
                    if enabled_methods['snmp']:
                        if getattr(device, 'snmp_community', '') and getattr(device, 'snmp_community', '') != '-':
                            available_methods.append('snmp')
                        else:
                            error_parts.append("未配置SNMP团体字")

                    if enabled_methods['restconf']:
                        available_methods.append('restconf')

                    if enabled_methods['telemetry']:
                        available_methods.append('telemetry')
                elif enabled_methods['snmp'] or enabled_methods['restconf'] or enabled_methods['telemetry']:
                    error_parts.append("南向驱动验证当前仅支持NETMIKO/NETCONF")

                if not available_methods:
                    return False, f"设备 {device_ip} {', '.join(error_parts)}", None

                return True, "验证通过", device
            else:
                return False, f"不支持的采集类型: {collection_type}", None
                
        except Exception as e:
            logger.error(f"验证采集执行参数失败: {str(e)}")
            return False, f"验证失败: {str(e)}", None

    @action(detail=True, methods=['post'])
    def execute_sub_plan(self, request, *args, **kwargs):
        """执行子采集方案 NETCONF 和 NETMIKO。支持两种方式：南向驱动 / 本机直连。"""
        plan = self.get_object()
        device_ip = request.data.get('device_ip')           # 设备IP
        south_driver = request.data.get('south_driver')      # 南向驱动（可选）
        use_local = request.data.get('use_local', False)     # 是否使用本机直连（不走南向驱动）

        try:
            # 使用统一的参数验证方法
            is_valid, error_msg, device = self.validate_execution_params(
                plan, device_ip, 'both', use_local=use_local
            )
            if not is_valid:
                return JsonResponse({
                    "code": 400,
                    "message": error_msg
                })

            # 不走南向驱动时使用本机直连执行；否则必须提供 south_driver
            if use_local:
                result = DeviceCollectionService.execute_both_collection_local(plan, device)
            else:
                if not south_driver:
                    return JsonResponse({
                        "code": 400,
                        "message": "南向驱动方式执行时缺少参数: south_driver；若需本机直连执行请传 use_local=true"
                    })
                result = DeviceCollectionService.execute_both_collection(plan, device, south_driver)
            
            if result['success']:
                analysis_trigger = {
                    "scheduled": False,
                    "reason": "not_local_execution",
                }
                if use_local:
                    analysis_trigger = maybe_schedule_interface_utilization(
                        collection_type=getattr(plan, "collection_type", ""),
                        device_ip=device_ip,
                        execute_time=result.get("execute_time"),
                        triggered_by="device_api-execute_sub_plan-local",
                    )
                return JsonResponse({
                    "code": 200,
                    "message": result['message'],
                    "data": {
                        "netconf_result": result['netconf_result'],
                        "netmiko_result": result['netmiko_result'],
                        "snmp_result": result.get('snmp_result'),
                        "restconf_result": result.get('restconf_result'),
                        "telemetry_result": result.get('telemetry_result'),
                        "execute_time": result.get("execute_time", ""),
                        "analysis_trigger": analysis_trigger,
                    }
                })
            else:
                return JsonResponse({
                    "code": 500,
                    "message": result['error'],
                    "data": {
                        "netconf_result": result.get('netconf_result'),
                        "netmiko_result": result.get('netmiko_result'),
                        "snmp_result": result.get('snmp_result'),
                        "restconf_result": result.get('restconf_result'),
                        "telemetry_result": result.get('telemetry_result'),
                    }
                })

        except Exception as e:
            logger.error(f"双重采集执行失败: 方案={plan.name}, 设备={device_ip}, 错误={str(e)}", exc_info=True)
            return JsonResponse({
                "code": 500,
                "message": f"双重采集失败: {str(e)}"
            })

    @action(detail=False, methods=['get'])
    def collect_type_list(self, request):
        """根据采集类型获取模型字段"""
        result = []
        for k, v in field_mapping.items():
            result.append({"label": v["label"], "value": v["value"], "icon": v["icon"]})

        return JsonResponse({
            'code': 200,
            'message': '获取成功',
            'data': result
        })

    @action(detail=False, methods=['get'])
    def model_fields(self, request):
        """根据采集类型获取模型字段"""
        model_type = request.query_params.get('model_type')
             
        if model_type in field_mapping:
            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': field_mapping[model_type]["mapping_fields"]
            })
        else:
            return JsonResponse({
                'code': 404,
                'message': f'未找到模型类型: {model_type}',
                'data': None
            })

    @action(detail=False, methods=['post'])
    def collect_keys_with_path(self, request, *args, **kwargs):
        """执行数据处理函数，将采集结果转换为标准数据格式"""

        new_event = request.data
        field_driver = FieldMappingDriver()
        """新建测试数据"""
        try:
            mapped_data = field_driver.collect_keys_with_path(data=new_event)
            # 将字典转换为元组，然后去重
            unique_items = {tuple(d.items()) for d in mapped_data}
            # 将元组转换回字典
            unique_data = [dict(t) for t in unique_items]
            # 找根节点
            root_data = field_driver.collect_keys_with_list_key(data=new_event)
            return JsonResponse({
                'code': 200,
                'data': {'fields': unique_data, 'root_fields': root_data},
                'message': 'success'
            })
        except Exception as e:
            return JsonResponse({
                "code": 400,
                "message": str(e)
            })

    @action(detail=False, methods=['get'])
    def south_driver_list(self, request):
        """获取南向驱动列表"""
        data_list = []
        server_info = config.service_dicovery('south_driver')
        server_hosts = server_info['hosts']
        for server in server_hosts:
            metadata = server['metadata']
            data_list.append({"label": metadata["machine_room"], "value": server["ip"]})

        return JsonResponse({
            'code': 200,
            'message': '获取成功',
            'data': data_list
        })

    @action(detail=False, methods=['post'])
    def record_plan_data(self, request, *args, **kwargs):
        """验证-接收南向驱动数据，存入db"""

        data = request.data
        result = plan_data_to_mongodb(**data)
        webhook_args = extract_webhook_args(data)
        analysis_trigger = {
            "scheduled": False,
            "reason": "collection_save_failed",
        }
        if result.get("status") == "success":
            analysis_trigger = maybe_schedule_interface_utilization(
                collection_type=webhook_args.get("collection_type", ""),
                device_ip=webhook_args.get("device_ip", ""),
                execute_time=webhook_args.get("execute_time"),
                triggered_by="device_api-record_plan_data",
                countdown=5,
            )

        return JsonResponse({
            'code': 200 if result.get("status") == "success" else 500,
            'message': result.get("message", ""),
            'data': {
                'analysis_trigger': analysis_trigger,
            },
        })

    @action(detail=False, methods=['post'])
    def record_collection(self, request, *args, **kwargs):
        """celery-接收南向驱动数据，存入mongodb"""

        data = request.data
        result = celery_data_mongodb(**data)
        webhook_args = extract_webhook_args(data)
        analysis_trigger = {
            "scheduled": False,
            "reason": "collection_save_failed",
        }
        if result.get("status") == "success":
            analysis_trigger = maybe_schedule_interface_utilization(
                collection_type=webhook_args.get("collection_type", ""),
                device_ip=webhook_args.get("device_ip", ""),
                execute_time=webhook_args.get("execute_time"),
                triggered_by="device_api-record_collection",
                countdown=5,
            )

        return JsonResponse({
            'code': 200 if result.get("status") == "success" else 500,
            'message': result.get("message", ""),
            'data': {
                'analysis_trigger': analysis_trigger,
            },
        })

    @action(detail=False, methods=['get'])
    def execute_plan_celery(self, request):
        """获取采集结果统计信息，可以直接删除"""
        from apps.device_api.tasks import plan_collect_device_main

        data = plan_collect_device_main()

        return JsonResponse({
            'code': 200,
            'message': "采集方案定时任务执行成功",
            'results': data
        })


class NetconfXMLTemplateViewSet(CustomViewBase):
    """NETCONF XML模板视图集"""
    queryset = NetconfXMLTemplate.objects.all()
    serializer_class = NetconfXMLTemplateSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['collection_plan']
    pagination_class = LargeResultsSetPagination
    search_fields = ['collect_method', 'description', 'collection_plan__name']
    ordering_fields = ['collect_method', 'created_at', 'updated_at']
    ordering = ['collection_plan', 'collect_method']
    
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

    @staticmethod
    def _pick_latest_record(records):
        if not records:
            return None
        return sorted(
            records,
            key=lambda item: (
                str(item.get('execute_time', '') or ''),
                float(item.get('log_time', 0) or 0),
            ),
            reverse=True,
        )[0]

    @action(detail=False, methods=['get'])
    def latest(self, request):
        serial_num = request.GET.get('serial_num', '').strip()
        manage_ip = request.GET.get('manage_ip', '').strip()
        collection_type = request.GET.get('collection_type', '').strip()

        device = None
        if serial_num:
            device = NetworkDevice.objects.filter(serial_num=serial_num).first()
            if device and not manage_ip:
                manage_ip = device.manage_ip
        elif manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
            if device and not serial_num:
                serial_num = device.serial_num

        if not manage_ip:
            return JsonResponse({
                'code': 400,
                'message': '缺少必要参数: serial_num 或 manage_ip',
                'data': None,
            })

        types = [collection_type] if collection_type else DEFAULT_COLLECTION_TYPES
        latest_results = []
        for current_type in types:
            collection_db = MongoOps(db='Automation', coll=f'plan_{current_type}')
            records = list(
                collection_db.coll.find({'hostip': manage_ip}, {'_id': 0})
                .sort('execute_time', -1)
                .limit(1)
            )
            if records:
                latest_results.append({
                    'collection_type': current_type,
                    'record': records[0],
                })

        return JsonResponse({
            'code': 200,
            'message': '获取成功',
            'data': {
                'serial_num': serial_num,
                'manage_ip': manage_ip,
                'results': latest_results,
            },
        })

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """根据厂商统计4个指标：
          1. 覆盖率：参与自动化任务的网络设备数 / 网络设备总数 * 100
          2. 成功率：成功执行采集任务的网络设备数 / 参与采集任务的网络设备数 * 100
          3. 纳管设备总数：纯数字展示，单位(台)
          4. 采集方案数：纯数字展示
        """
        try:
            vendor = request.GET.get('vendor')
            vendor = None if vendor == "All" else vendor
            
            # 构建基础查询条件
            device_filters = {'status': 0}  # 在线状态
            plan_filters = {'is_active': True}
            
            if vendor:
                device_filters['vendor__alias'] = vendor
                plan_filters['vendor'] = vendor

            # 1. 纳管设备总数：在线状态的网络设备数
            total_devices = NetworkDevice.objects.filter(**device_filters).count()

            # 2. 采集方案数：启用的采集方案数
            plan_count = DeviceCollectionPlans.objects.filter(**plan_filters).count()

            # 3. 参与采集任务的网络设备数：由 PlansToDevice 绑定关系决定
            participated_manage_ips = list(
                NetworkDevice.objects.filter(**device_filters, auto_enable=True)
                .values_list('manage_ip', flat=True)
            )
            participated_devices = (
                PlansToDevice.objects.filter(
                    is_active=True,
                    manage_ip__in=participated_manage_ips,
                )
                .values('manage_ip')
                .distinct()
                .count()
            )

            # 4. 覆盖率计算：参与自动化任务的设备数 / 总设备数 * 100
            coverage_rate = round((participated_devices / total_devices * 100), 2) if total_devices > 0 else 0.0

            # 5. 成功率计算：从COLLECTION_PLAN获取最新execute_time，统计该次执行成功的数量
            success_rate = 0.0
            if participated_devices > 0:
                try:
                    # 构建MongoDB查询条件，获取最新的execute_time
                    mongo_query = {}
                    if vendor:
                        mongo_query['vendor'] = vendor
                    
                    # 获取最新的一条记录的execute_time
                    latest_record = COLLECTION_PLAN.coll.find(mongo_query).sort('execute_time', -1).limit(1)
                    latest_records = list(latest_record)
                    
                    if latest_records and latest_records[0].get('execute_time'):
                        latest_execute_time = latest_records[0]['execute_time']
                        
                        # 根据execute_time和task_status="success"统计成功的数量
                        success_query = {
                            'execute_time': latest_execute_time,
                            'task_status': 'success'
                        }
                        if vendor:
                            success_query['vendor'] = vendor

                        success_count = COLLECTION_PLAN.count_documents(success_query)
                        
                        # 计算成功率：成功数量 / 参与设备数 * 100
                        success_rate = round((success_count / participated_devices * 100), 2) if participated_devices > 0 else 0.0
                    else:
                        logger.warning("未找到最新的execute_time记录")
                except Exception as e:
                    logger.error(f"计算成功率失败: {str(e)}", exc_info=True)
                    success_rate = 0.0

            data = {
                "total_devices": total_devices,
                "plan_count": plan_count,
                "success_rate": success_rate,
                "coverage_rate": coverage_rate
            }

            return JsonResponse({
                'code': 200,
                'message': "获取成功",
                'results': data
            })
        except Exception as e:
            logger.error(f"获取概览数据失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f"获取失败: {str(e)}",
                'results': None
            })

    @action(detail=False, methods=['get'])
    def device_traceability(self, request):
        """按设备维度展示采集方案绑定、最新执行批次与子采集状态。"""
        try:
            manage_ip = request.GET.get('manage_ip', '').strip()
            if not manage_ip:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少必要参数: manage_ip',
                    'data': None,
                })

            plan_relations = list(
                PlansToDevice.objects.select_related('plan').filter(manage_ip=manage_ip, is_active=True)
            )

            results = []
            for relation in plan_relations:
                summary_plan = relation.plan
                if not summary_plan:
                    continue

                expected_sub_plans = list(summary_plan.collect_plans.all())
                parent_records = list(
                    COLLECTION_PLAN.coll.find(
                        {'summary_plan_id': summary_plan.id, 'device_ip': manage_ip},
                        {'_id': 0},
                    )
                )
                latest_parent = self._pick_latest_record(parent_records)

                latest_execute_time = latest_parent.get('execute_time') if latest_parent else None
                latest_sub_runs = []
                if latest_execute_time:
                    latest_sub_runs = list(
                        COLLECTION_SUB_PLAN.coll.find(
                            {
                                'summary_plan_id': summary_plan.id,
                                'device_ip': manage_ip,
                                'execute_time': latest_execute_time,
                            },
                            {'_id': 0},
                        )
                    )

                latest_sub_runs_map = {}
                for run in latest_sub_runs:
                    plan_id = run.get('plan_id')
                    if plan_id is None:
                        continue
                    existing = latest_sub_runs_map.get(plan_id)
                    if not existing or (
                        float(run.get('log_time', 0) or 0) > float(existing.get('log_time', 0) or 0)
                    ):
                        latest_sub_runs_map[plan_id] = run

                sub_plan_items = []
                successful_count = 0
                failed_count = 0
                for sub_plan in expected_sub_plans:
                    latest_run = latest_sub_runs_map.get(sub_plan.id)
                    latest_status = latest_run.get('task_status') if latest_run else 'pending'
                    if latest_status in {'finished', 'success'}:
                        successful_count += 1
                    elif latest_run:
                        failed_count += 1

                    enabled_methods = []
                    if getattr(sub_plan, 'netmiko_enabled', False):
                        enabled_methods.append('netmiko')
                    if getattr(sub_plan, 'netconf_enabled', False):
                        enabled_methods.append('netconf')
                    if getattr(sub_plan, 'snmp_enabled', False):
                        enabled_methods.append('snmp')
                    if getattr(sub_plan, 'restconf_enabled', False):
                        enabled_methods.append('restconf')
                    if getattr(sub_plan, 'telemetry_enabled', False):
                        enabled_methods.append('telemetry')

                    collection_type = getattr(sub_plan, 'collection_type', '')
                    sub_plan_items.append({
                        'plan_id': sub_plan.id,
                        'plan_name': sub_plan.name,
                        'collection_type': collection_type,
                        'collection_label': field_mapping.get(collection_type, {}).get('label', collection_type),
                        'description': getattr(sub_plan, 'description', ''),
                        'enabled_methods': enabled_methods,
                        'latest_run': {
                            'task_status': latest_status,
                            'collection_method': latest_run.get('collection_method') if latest_run else '',
                            'execute_time': latest_run.get('execute_time') if latest_run else latest_execute_time,
                            'task_errors': latest_run.get('task_errors', []) if latest_run else [],
                            'detail_query': {
                                'summary_plan_id': summary_plan.id,
                                'plan_id': sub_plan.id,
                                'device_ip': manage_ip,
                                'execute_time': latest_run.get('execute_time') if latest_run else latest_execute_time,
                                'collection_type': collection_type,
                            } if latest_run or latest_execute_time else None,
                        },
                    })

                results.append({
                    'relation_id': relation.id,
                    'manage_ip': relation.manage_ip,
                    'use_local': relation.use_local,
                    'execute_node': relation.execute_node,
                    'summary_plan': {
                        'id': summary_plan.id,
                        'name': summary_plan.name,
                        'vendor': summary_plan.vendor,
                        'device_type': summary_plan.device_type,
                        'is_active': summary_plan.is_active,
                    },
                    'latest_execution': {
                        'task_status': latest_parent.get('task_status') if latest_parent else 'never_run',
                        'device_name': latest_parent.get('device_name', '') if latest_parent else '',
                        'idc_name': latest_parent.get('idc_name', '') if latest_parent else '',
                        'execute_time': latest_execute_time,
                        'sub_plans_count': latest_parent.get('sub_plans_count', len(expected_sub_plans)) if latest_parent else len(expected_sub_plans),
                        'successful_sub_plans': successful_count,
                        'failed_sub_plans': failed_count,
                    },
                    'sub_plans': sub_plan_items,
                })

            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': {
                    'manage_ip': manage_ip,
                    'count': len(results),
                    'results': results,
                }
            })

        except Exception as e:
            logger.error(f"查询设备采集链路概览失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'查询失败: {str(e)}',
                'data': None,
            })

    @action(detail=False, methods=['get'])
    def parent_collection_list(self, request):
        """分页查询主采集方案记录列表
        
        查询条件（模糊查询）：
        - idc_name: 机房名称
        - vendor: 厂商
        - device_name: 设备名称
        - device_ip: 设备IP
        - execute_node: 执行节点
        
        分页参数：
        - page: 页码，默认1
        - page_size: 每页数量，默认10
        """
        try:
            # 获取查询参数
            search = request.GET.get('search', '').strip()
            idc_name = request.GET.get('idc_name', '').strip()
            vendor = request.GET.get('vendor', '').strip()
            device_name = request.GET.get('device_name', '').strip()
            device_ip = request.GET.get('device_ip', '').strip()
            execute_node = request.GET.get('execute_node', '').strip()
            summary_plan_id = request.GET.get('summary_plan_id', '').strip()
            sub_plan_id = request.GET.get('sub_plan_id', '').strip()
            try:
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('page_size', 10))
            except (TypeError, ValueError):
                return JsonResponse({
                    'code': 400,
                    'message': '分页参数无效',
                    'data': None
                })

            conditions = []

            # search字段：同时对summary_plan_name、device_ip和device_name进行模糊查询
            if search:
                conditions.append({
                    '$or': [
                        {'summary_plan_name': {'$regex': search, '$options': 'i'}},
                        {'device_ip': {'$regex': search, '$options': 'i'}},
                        {'device_name': {'$regex': search, '$options': 'i'}}
                    ]
                })

            # 其他模糊查询条件
            if idc_name:
                conditions.append({'idc_name': {'$regex': idc_name, '$options': 'i'}})
            if vendor:
                conditions.append({'vendor': {'$regex': vendor, '$options': 'i'}})
            if device_name and not search:
                conditions.append({'device_name': {'$regex': device_name, '$options': 'i'}})
            if device_ip and not search:
                conditions.append({'device_ip': {'$regex': device_ip, '$options': 'i'}})
            if execute_node:
                conditions.append({'execute_node': {'$regex': execute_node, '$options': 'i'}})
            if summary_plan_id:
                conditions.append({'summary_plan_id': int(summary_plan_id)})

            # 支持按子采集方案筛选主结果列表
            if sub_plan_id:
                sub_plan_query = {'plan_id': int(sub_plan_id)}
                if summary_plan_id:
                    sub_plan_query['summary_plan_id'] = int(summary_plan_id)

                related_sub_runs = list(COLLECTION_SUB_PLAN.coll.find(
                    sub_plan_query,
                    {'_id': 0, 'summary_plan_id': 1, 'device_ip': 1, 'execute_time': 1}
                ))

                if not related_sub_runs:
                    return JsonResponse({
                        'code': 200,
                        'message': '获取成功',
                        'data': {
                            'results': [],
                            'total': 0
                        }
                    })

                matched_runs = []
                seen_run_keys = set()
                for item in related_sub_runs:
                    run_key = (
                        item.get('summary_plan_id'),
                        item.get('device_ip'),
                        item.get('execute_time')
                    )
                    if run_key in seen_run_keys:
                        continue
                    seen_run_keys.add(run_key)
                    matched_runs.append({
                        'summary_plan_id': item.get('summary_plan_id'),
                        'device_ip': item.get('device_ip'),
                        'execute_time': item.get('execute_time'),
                    })

                conditions.append({'$or': matched_runs})

            if not conditions:
                query = {}
            elif len(conditions) == 1:
                query = conditions[0]
            else:
                query = {'$and': conditions}

            # 计算分页参数
            skip = page_size * (page - 1)
            
            # 查询总数
            total = COLLECTION_PLAN.count_documents(query)
            
            # 查询数据（按创建时间倒序排列）
            cursor = COLLECTION_PLAN.coll.find(query).sort('log_time', -1).limit(page_size).skip(skip)
            results = list(cursor)
            
            # 处理ObjectId，转换为字符串
            for result in results:
                if '_id' in result:
                    result['_id'] = str(result['_id'])

            # 构建响应数据
            response_data = {
                'code': 200,
                'message': '获取成功',
                'data': {
                    'results': results,
                    'total': total
                }
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"分页查询主采集方案记录失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'查询失败: {str(e)}',
                'data': None
            })

    @action(detail=False, methods=['get'])
    def sub_collection_detail(self, request):
        """根据主采集方案ID和采集类型查询子采集方案详情"""
        try:
            summary_plan_id = request.GET.get('summary_plan_id', '').strip()
            plan_id = request.GET.get('plan_id', '').strip()
            device_ip = request.GET.get('device_ip', '').strip()
            execute_time = request.GET.get('execute_time', '').strip()
            collection_type = request.GET.get('collection_type', '').strip()
            try:
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('page_size', 10))
            except (TypeError, ValueError):
                return JsonResponse({
                    'code': 400,
                    'message': '分页参数无效',
                    'data': None
                })

            # 查询子采集方案数据
            query = {}
            if summary_plan_id:
                query['summary_plan_id'] = int(summary_plan_id)
            if plan_id:
                query['plan_id'] = int(plan_id)
            if collection_type:
                query['collection_type'] = collection_type
            if device_ip:
                query['device_ip'] = device_ip
            if execute_time:
                query['execute_time'] = execute_time

            if not query:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少查询条件',
                    'data': None
                })

            sub_plan_data = COLLECTION_SUB_PLAN.coll.find_one(
                query,
                {'_id': 0},
                sort=[('log_time', -1), ('execute_time', -1)]
            )

            if not sub_plan_data:
                return JsonResponse({
                    'code': 200,
                    'message': '未找到对应的子采集方案数据',
                    'data': None
                })

            collection_method = sub_plan_data.get("collection_method")
            effective_collection_type = sub_plan_data.get('collection_type') or collection_type

            # 查询出对应采集类型下的数据
            collection_name = f"plan_{effective_collection_type}"
            collection_db = MongoOps(db='Automation', coll=collection_name)
            data_query = {
                'collection_type': effective_collection_type,
            }
            if sub_plan_data.get('summary_plan_id') is not None:
                data_query['summary_plan_id'] = sub_plan_data['summary_plan_id']
            if sub_plan_data.get('plan_id') is not None:
                data_query['plan_id'] = sub_plan_data['plan_id']
            if sub_plan_data.get('device_ip'):
                data_query['hostip'] = sub_plan_data['device_ip']
            if sub_plan_data.get('execute_time'):
                data_query['execute_time'] = sub_plan_data['execute_time']
            # 获取总记录数
            total = collection_db.coll.count_documents(data_query)
            # 计算分页参数
            skip = (page - 1) * page_size
            # 使用聚合管道查询，在查询时添加 collection_type 字段
            pipeline = [
                {'$match': data_query},
                {'$addFields': {'collection_method': collection_method}},  # 添加 collection_method 字段
                {'$project': {'_id': 0}},  # 排除 _id 字段
                {'$skip': skip},  # 跳过记录
                {'$limit': page_size}  # 限制返回数量
            ]
            collection_data = list(collection_db.coll.aggregate(pipeline)) 

            # 根据 collection_type 获取表头信息
            columns = [{"label": "时间", "value": "log_time"}, {"label": "设备IP", "value": "hostip"}, {"label": "采集方式", "value": "collection_method"}]
            if effective_collection_type in field_mapping:
                mapping_fields = field_mapping[effective_collection_type].get('mapping_fields', [])
                for field in mapping_fields:
                    label = field.get('label', '')
                    value = field.get('value', '')
                    # 提取冒号之前的内容作为 label
                    if ':' in label:
                        label = label.split(':')[0].strip()
                    columns.append({
                        'label': label,
                        'value': value
                    })

            # 构建返回数据
            response_data = {
                'code': 200,
                'message': '获取成功',
                'data': {
                    'sub_plan': sub_plan_data,
                    'columns': columns,
                    'collection_data': collection_data,
                    'total': total
                }
            }
            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"查询子采集方案详情失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'查询失败: {str(e)}',
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

            # 查询最新的10条结果，按collected_at倒序排列
            cursor = COLLECTION_RESULTS_DB.coll.find(query).sort('collected_at', -1).limit(10)
            results = list(cursor)

            # 序列化结果
            serializer = CollectionResultByPlanSerializer(results, many=True)
            
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
                query['device_ip'] = {'$regex': filter_data['device_ip'], '$options': 'i'}
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

            # 计算分页参数
            skip = page_size * (page - 1)

            # 直接使用MongoDB原生查询确保正确的分页和排序
            cursor = COLLECTION_RESULTS_DB.coll.find(query).sort(sort_by, sort_direction).limit(page_size).skip(skip)
            results = list(cursor)

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
                'results': serializer.data
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
