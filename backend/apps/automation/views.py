import operator
from django.http import JsonResponse
from django.apps import apps
from datetime import datetime
# from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import Count
from rest_framework import filters
from rest_framework.views import APIView
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.automation.models import CollectionPlan, CollectionRule, CollectionMatchRule, AutoFlow
from apps.automation.serializers import (
    CollectionPlanSerializer, CollectionRuleSerializer, CollectionMatchRuleSerializer, AutoFlowSerializer)
from apps.api.tools.custom_viewset_base import CustomViewBase
from django.db.models import CharField, ForeignKey, GenericIPAddressField
from utils.db.mongo_ops import MongoOps
from driver import auto_driver_map

xunmi_mongo = MongoOps(db='BasePlatform', coll='XunMi')


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
                    }, ]
            }
            return JsonResponse(result, safe=False)
        # 最近一次结果
        elif get_param.get('last') == 'true':
            if get_param.get('server_mac_address', '') or get_param.get('server_ip_address', ''):
                mongo_data = dict()
                # 用于把key值为空的可以过滤掉，只保留有完整key value的字典信息
                for param in get_param.keys():
                    if get_param[param]:
                        if param in ['limit', 'start', 'page', 'method', 'last']:
                            continue
                        mongo_data[param] = get_param[param]
                if get_param['log_time']:
                    start_time = mongo_data['log_time'] + ' 00:00:00'
                    end_time = mongo_data['log_time'] + ' 23:59:59'
                    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    mongo_data['log_time'] = {"$gte": start_time, "$lte": end_time}
                query_tmp = xunmi_mongo.find(query_dict=mongo_data, fileds={'_id': 0}, sort='log_time')
                if query_tmp:
                    mongo_data['log_time'] = query_tmp[-1]['log_time']
                    res = xunmi_mongo.find(query_dict=mongo_data, fileds={'_id': 0}, sort='log_time')
                    for i in res:
                        i['log_time'] = i['log_time'].strftime("%Y-%m-%d %H:%M:%S")
                    result = {
                        "code": 200,
                        "results": res,
                        "count": len(res)
                    }
                    return JsonResponse(result, safe=False)
        else:
            if get_param.get('server_mac_address', '') or get_param.get('server_ip_address', ''):
                mongo_data = dict()
                # 用于把key值为空的可以过滤掉，只保留有完整key value的字典信息
                for param in get_param.keys():
                    if get_param[param]:
                        if param in ['limit', 'start', 'page', 'method', 'last']:
                            continue
                        mongo_data[param] = get_param[param]
                if get_param['log_time']:
                    start_time = mongo_data['log_time'] + ' 00:00:00'
                    end_time = mongo_data['log_time'] + ' 23:59:59'
                    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    mongo_data['log_time'] = {"$gte": start_time, "$lte": end_time}
                res = xunmi_mongo.find_page_query(fileds={'_id': 0}, sort='log_time',
                                                  query_dict=mongo_data,
                                                  page_size=int(get_param['limit']),
                                                  page_num=int(get_param['start']) // 10)
                for i in res:
                    i['log_time'] = i['log_time'].strftime("%Y-%m-%d %H:%M:%S")

                res_count = MongoOps(db='netops', coll='XunMi').find(fileds={'_id': 0}, sort='log_time',
                                                                     query_dict=mongo_data)
                result = {
                    "code": 200,
                    "results": res,
                    "count": len(res_count)
                }
                return JsonResponse(result, safe=False)
        result = {
            "code": 400,
            "count": 0,
            "message": "没有匹配的数据",
            "results": []
        }
        return JsonResponse(result, safe=False)
