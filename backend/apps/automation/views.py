import json
import operator
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from urllib.parse import quote
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from rest_framework.response import Response
from django.apps import apps
from datetime import datetime
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import Count
from rest_framework import filters
from rest_framework.views import APIView
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.automation.models import (CollectionPlan, CollectionRule,
                                    CollectionMatchRule, AutoFlow, AutomationInventory, AutoVars)
from apps.asset.serializers import NetworkDeviceSerializer
from apps.automation.serializers import (
    CollectionPlanSerializer, CollectionRuleSerializer, CollectionMatchRuleSerializer,
    AutoFlowSerializer, AutomationInventorySerializer, AutoVarsSerializer)
from apps.api.tools.custom_viewset_base import CustomViewBase
from django.db.models import CharField, ForeignKey, GenericIPAddressField
from apps.automation.tasks import DiagnoseProc
from utils.db.mongo_ops import MongoOps, MongoNetOps
from driver import auto_driver_map
from .tools.models_api import get_firewall_list

xunmi_mongo = MongoOps(db='BasePlatform', coll='XunMi')
show_ip_mongo = MongoOps(db='Automation', coll='layer3interface')
interface_mongo = MongoOps(db='Automation', coll='layer2interface')


class CollectionPlanFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    # vendor = django_filters.CharFilter(lookup_expr='icontains')
    memo = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = CollectionPlan
        fields = '__all__'


class CollectionRuleFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    # vendor = django_filters.CharFilter(lookup_expr='icontains')
    # memo = django_filters.CharFilter(lookup_expr='icontains')
    # name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = CollectionRule
        fields = '__all__'


class CollectionMatchRuleFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    # vendor = django_filters.CharFilter(lookup_expr='icontains')
    # memo = django_filters.CharFilter(lookup_expr='icontains')
    # name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = CollectionMatchRule
        fields = '__all__'


# 自动化工作流
class AutoFlowViewSet(CustomViewBase):
    queryset = AutoFlow.objects.all().order_by('-commit_time')
    serializer_class = AutoFlowSerializer
    # # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    # filterset_class = NetFileVTEPFilter
    filter_fields = '__all__'
    ordering_fields = ('-id',)


class CollectionPlanViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = CollectionPlan.objects.all().order_by('-id')
    queryset = CollectionPlanSerializer.setup_eager_loading(queryset)
    serializer_class = CollectionPlanSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filterset_class = CollectionPlanFilter
    filter_fields = ('vendor', 'name',)
    # filterset_class = CollectionPlanFilter
    search_fields = ('vendor', 'name',)
    pagination_class = LargeResultsSetPagination


class CollectionMatchRuleViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = CollectionMatchRule.objects.all().order_by('-id')
    queryset = CollectionMatchRuleSerializer.setup_eager_loading(queryset)
    serializer_class = CollectionMatchRuleSerializer
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filterset_class = CollectionMatchRuleFilter
    filter_fields = ('module', 'method', 'vendor__name')
    search_fields = ('module', 'method',)
    pagination_class = LargeResultsSetPagination


class CollectionRuleViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = CollectionRule.objects.all().order_by('-id')
    queryset = CollectionRuleSerializer.setup_eager_loading(queryset)
    serializer_class = CollectionRuleSerializer
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,)
    filterset_class = CollectionRuleFilter
    filter_fields = ('module', 'method',)
    search_fields = ('module', 'method',)
    pagination_class = LargeResultsSetPagination

    # def create(self, request, *args, **kwargs):
    #     serializer = CollectionRuleSerializer(data=request.data)
    #     if serializer.is_valid():
    #         super(CollectionRuleViewSet, self).create(request, *args, **kwargs)
    #     else:
    #         # 校验失败，返回错误信息
    #         return Response(serializer.errors, status=200)
    #
    # def update(self, request, *args, **kwargs):
    #     serializer = CollectionRuleSerializer(data=request.data)
    #     if serializer.is_valid():
    #         super(CollectionRuleViewSet, self).update(request, *args, **kwargs)
    #     else:
    #         # 校验失败，返回错误信息
    #         return Response(serializer.errors, status=200)


# 自动化场景设备变量
class AutoVarsViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = AutoVars.objects.all().order_by('-id')
    queryset = AutoVarsSerializer.setup_eager_loading(queryset)
    serializer_class = AutoVarsSerializer
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination


class AutomationInventoryViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = AutomationInventory.objects.all().order_by('-id')
    queryset = AutomationInventorySerializer.setup_eager_loading(queryset)
    serializer_class = AutomationInventorySerializer
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination


# 对应前端的采集规则页面
class VueCollectionRule(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        print(get_param)
        # if all(k in get_param for k in "get_cmdb_field"):
        # 获取CMDB网络设备表中的所有字段
        if 'get_cmdb_field' in get_param.keys():
            model = apps.get_model(app_label='asset', model_name='NetworkDevice')
            fields = model._meta.get_fields()
            field_res = []
            for field in fields:
                if isinstance(field, ForeignKey):
                    related_model = field.related_model
                    for _field in related_model._meta.get_fields():
                        if isinstance(_field, CharField):
                            if hasattr(_field, 'verbose_name'):
                                field_res.append({
                                    'label': f"{field.verbose_name}-{_field.verbose_name}",
                                    'value': f"{field.name}__{_field.name}"
                                })
                if isinstance(field, CharField) or isinstance(field, GenericIPAddressField):
                    if hasattr(field, 'verbose_name'):
                        field_res.append({
                            'label': field.verbose_name,
                            'value': field.name
                        })
                    else:
                        field_res.append({
                            'label': field.name,
                            'value': field.name
                        })
            # field_names = [field.verbose_name if hasattr(field, 'verbose_name') else field.name for field in fields]
            return JsonResponse({'code': 200, 'msg': 'success', 'data': field_res})
        # 获取自动化插件
        if 'get_pulgin_list' in get_param.keys():
            return JsonResponse({'code': 200, 'msg': 'success', 'data': auto_driver_map})
        return JsonResponse({'code': 400, 'msg': '未匹配动作'})

    def post(self, request):
        post_param = request.data
        print(post_param)
        return JsonResponse({'code': 400, 'msg': '未匹配动作'})


# 自动化chart
class AutomationChart(APIView):
    def get(self, request):
        get_params = request.GET.dict()
        if 'event_task_module' in get_params:
            event_task_module_list = []
            event_task_module_queryset = AutoFlow.objects.values('task').annotate(sum_count=Count('task'))
            for i in event_task_module_queryset:
                event_task_module_list.append(i)
            # 根据数目count排序
            sorted_event_task_module_list = sorted(event_task_module_list, key=operator.itemgetter('sum_count'),
                                                   reverse=True)
            result = {
                "code": 200,
                "data": sorted_event_task_module_list
            }
            return JsonResponse(result, safe=False)

        if 'event_task_user' in get_params:
            event_task_user_list = []
            event_task_user_queryset = AutoFlow.objects.values('commit_user').annotate(sum_count=Count('commit_user'))
            for i in event_task_user_queryset:
                event_task_user_list.append(i)
            # 根据数目count排序
            sorted_event_task_user_list = sorted(event_task_user_list, key=operator.itemgetter('sum_count'),
                                                 reverse=True)
            result = {
                "code": 200,
                "data": sorted_event_task_user_list
            }
            return JsonResponse(result, safe=False)
        if 'event_commit_time' in get_params:
            login_time_list = []
            work_time_list = []
            event_commit_queryset = AutoFlow.objects.values().all()
            for i in event_commit_queryset:
                current_day = i['commit_time'].strftime("%Y-%m-%d %H:%M:%S")[0:11]
                if current_day + '08:30' < i['commit_time'].strftime("%Y-%m-%d %H:%M:%S") < current_day + "17:30":
                    work_time_list.append(i)
            result = {
                'code': 200,
                'data': {
                    'work_time_count': len(work_time_list),
                    'total_time_count': len(event_commit_queryset),
                    'not_work_time': len(event_commit_queryset) - len(work_time_list)
                }
            }
            return JsonResponse(result, safe=False)

        if "collection_plan" in get_params:
            collection_plan_list = []
            collection_plan_queryset = CollectionPlan.objects.values("vendor").annotate(sum_count=Count("vendor"))
            for i in collection_plan_queryset:
                collection_plan_list.append(i)

            result = {
                'code': 200,
                'data': collection_plan_list
            }
            return JsonResponse(result, safe=False)


class XunMiView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        print(get_param)
        mongo_data = dict()
        if get_param.get('get_interface_by_hostip'):
            hostip = get_param['get_interface_by_hostip']
            layer3interface_res = show_ip_mongo.find(query_dict={'hostip': hostip}, fields={'interface': 1})
            layer2interface_res = interface_mongo.find(query_dict={'hostip': hostip}, fields={'interface': 1})
            res = [x['interface'] for x in layer3interface_res if layer3interface_res] + [x['interface'] for x in
                                                                                          layer2interface_res if
                                                                                          layer2interface_res]
            result = {
                "code": 200,
                "count": len(res),
                "message": "成功",
                "results": res
            }
            return JsonResponse(result, safe=False)

        if get_param.get('get_table_columns') == '1':
            result = {
                'code': 200,
                'results': [
                    {
                        'title': '设备名称',
                        'key': 'node_hostname'
                    },
                    {
                        'title': 'IDC',
                        'key': 'idc_name'
                    },
                    {
                        'title': '序列号',
                        'key': 'serial_num'
                    },
                    {
                        'title': '管理IP',
                        'key': 'node_ip'
                    },
                    {
                        'title': '接口',
                        'key': 'node_interface'
                    },
                    {
                        'title': '接入位置',
                        'key': 'node_interface'
                    },
                    {
                        'title': '服务器IP',
                        'key': 'server_ip_address'
                    },
                    {
                        'title': '服务器MAC',
                        'key': 'server_mac_address'
                    },
                    {
                        'title': '记录时间',
                        'key': 'log_time'
                    },
                    {
                        'title': '归属人',
                        'key': 'server_admin'
                    },
                    {
                        'title': '业务线',
                        'key': 'server_department'
                    },
                ]
            }
            return JsonResponse(result, safe=False)
        # 最近一次结果
        elif get_param.get('last') == 'true':
            # 用于把key值为空的可以过滤掉，只保留有完整key value的字典信息
            for param in get_param.keys():
                if get_param[param]:
                    if param in ['limit', 'start', 'page', 'method', 'last', 'idc', 'page_size']:
                        continue
                    else:
                        mongo_data[param] = get_param[param]
            if 'memberport' in get_param.keys():
                if len(get_param['memberport']) > 1:
                    mongo_data['memberport'] = {'$in': json.loads(get_param['memberport'])}
            if get_param.get('log_time'):
                start_time = mongo_data['log_time'] + ' 00:00:00'
                end_time = mongo_data['log_time'] + ' 23:59:59'
                start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                mongo_data['log_time'] = {"$gte": start_time, "$lte": end_time}
            if mongo_data:
                query_tmp = xunmi_mongo.find(query_dict=mongo_data, fields={'_id': 0}, sort='log_time')
                if query_tmp:
                    mongo_data['log_time'] = query_tmp[-1]['log_time']

                    res = xunmi_mongo.find(query_dict=mongo_data, fields={'_id': 0}, sort='log_time')
                    for i in res:
                        i['log_time'] = i['log_time'].strftime("%Y-%m-%d %H:%M:%S")
                    result = {
                        "code": 200,
                        "results": res,
                        "count": len(res)
                    }
                    return JsonResponse(result, safe=False)
            else:
                result = {
                    "code": 400,
                    "count": 0,
                    "message": "没有匹配查询条件的数据",
                    "results": []
                }
                return JsonResponse(result, safe=False)
        else:
            # 用于把key值为空的可以过滤掉，只保留有完整key value的字典信息
            for param in get_param.keys():
                if get_param[param]:
                    if param in ['limit', 'start', 'page', 'method', 'last', 'idc', 'page_size']:
                        continue
                    else:
                        mongo_data[param] = get_param[param]
            if 'memberport' in get_param.keys():
                if len(get_param['memberport']) > 1:
                    mongo_data['memberport'] = {'$in': json.loads(get_param['memberport'])}
            if get_param.get("log_time"):
                start_time = mongo_data['log_time'] + ' 00:00:00'
                end_time = mongo_data['log_time'] + ' 23:59:59'
                start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                mongo_data['log_time'] = {"$gte": start_time, "$lte": end_time}
            page_size = int(get_param.get("page_size", 10))
            page = int(get_param.get("page", 1))
            res = xunmi_mongo.find_page_query(fields={'_id': 0}, sort='log_time',
                                              query_dict=mongo_data,
                                              page_size=page_size,
                                              page_num=page)
            count = xunmi_mongo.count_documents(query=mongo_data)
            for i in res:
                i['log_time'] = i['log_time'].strftime("%Y-%m-%d %H:%M:%S")

            result = {
                "code": 200,
                "results": res,
                "count": count
            }
            return JsonResponse(result, safe=False)
        result = {
            "code": 400,
            "count": 0,
            "message": "没有匹配的数据",
            "results": []
        }
        return JsonResponse(result, safe=False)

    def post(self, request):
        post_param = request.data
        mongo_data = {}                 # mongodb 查询条件

        if 'memberport' in post_param:
            member_port_list = json.loads(post_param['memberport'])
            if member_port_list:
                mongo_data['memberport'] = {'$in': member_port_list}

        # 构建查询条件
        for param, value in post_param.items():
            if value and param not in ['last', 'memberport']:
                mongo_data[param] = value

        # 查询数据
        if post_param.get('last') and mongo_data:
            # 获取最新一条记录的时间
            query_tmp = xunmi_mongo.find(query_dict=mongo_data, fields={'_id': 0}, sort='log_time')
            if query_tmp:
                mongo_data['log_time'] = query_tmp[-1]['log_time']

        # 执行查询
        result = xunmi_mongo.find(fields={'_id': 0}, sort='log_time', query_dict=mongo_data)
        
        # 格式化时间
        for item in result:
            item['log_time'] = item['log_time'].strftime("%Y-%m-%d %H:%M:%S")

        # 导出Excel配置
        columns = [
            {'label': '设备名称', 'key': 'node_hostname'},
            {'label': '机房', 'key': 'idc_name'}, 
            {'label': 'SN号', 'key': 'serial_num'},
            {'label': '主机IP', 'key': 'node_ip'},
            {'label': '接口', 'key': 'node_interface'},
            {'label': '交换机位置', 'key': 'node_location'},
            {'label': '服务器IP', 'key': 'server_ip_address'},
            {'label': 'MAC地址', 'key': 'server_mac_address'},
            {'label': '归属人', 'key': 'server_admin'},
            {'label': '业务线', 'key': 'server_department'},
            {'label': '服务器位置', 'key': 'server_location'},
            {'label': '记录时间', 'key': 'log_time'}
        ]

        # 创建Excel
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Address location"

        # 写入表头
        for col_num, column in enumerate(columns, 1):
            worksheet[f'{get_column_letter(col_num)}1'] = column['label']

        # 写入数据
        for row_num, device in enumerate(result, 2):
            for col_num, column in enumerate(columns, 1):
                worksheet[f'{get_column_letter(col_num)}{row_num}'] = device.get(column['key'], '')

        # 输出Excel文件
        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        filename = quote("地址寻觅.xlsx")
        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{filename}'

        return response


class SecMainView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        if get_param.get("get_firewall_list"):
            res = get_firewall_list()
            result = {
                "code": 200,
                "count": 0,
                "message": "success",
                "results": res
            }
            return JsonResponse(result, safe=False)
        result = {
            "code": 400,
            "count": 0,
            "message": "没有匹配的数据",
            "results": []
        }
        return JsonResponse(result, safe=False)
    def post(self, request):
        pass


class DiagnoseView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        if 'server_ip_address' in get_param.keys():
            _DiagnoseProc = DiagnoseProc(get_param['server_ip_address'])
            xunmi_res = _DiagnoseProc.get_xunmi()
            manage_ip = xunmi_res[0]['node_ip']
            name = xunmi_res[0]['node_hostname']
            cmdb_res = _DiagnoseProc.get_cmdb(manage_ip)
            log_res = _DiagnoseProc.get_log(manage_ip, name)
            lldp_res = _DiagnoseProc.get_lldp(manage_ip)
            alert_res = _DiagnoseProc.get_alert(manage_ip)
            result = {
                "code": 200,
                "results": {
                    'xunmi': xunmi_res,
                    'cmdb': cmdb_res,
                    'log': log_res,
                    'lldp': lldp_res,
                    'alert': alert_res
                },
                "count": 1
            }
            return JsonResponse(result, safe=False)
