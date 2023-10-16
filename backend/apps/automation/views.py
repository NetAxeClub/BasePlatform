from django.http import JsonResponse
from django.apps import apps
# from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from rest_framework import filters
from rest_framework.views import APIView
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.automation.models import CollectionPlan, CollectionRule, CollectionMatchRule
from apps.automation.serializers import CollectionPlanSerializer, CollectionRuleSerializer, CollectionMatchRuleSerializer
from apps.api.tools.custom_viewset_base import CustomViewBase
from django.db.models import CharField, ForeignKey, GenericIPAddressField
from driver import auto_driver_map


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