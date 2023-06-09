import django_filters
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.automation.models import CollectionPlan
from apps.automation.serializers import CollectionPlanSerializer
from apps.api.tools.custom_viewset_base import CustomViewBase


class CollectionPlanFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    # vendor = django_filters.CharFilter(lookup_expr='icontains')
    memo = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = CollectionPlan
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
    filter_fields = ('vendor', 'name',)
    # filterset_class = CollectionPlanFilter
    search_fields = ('vendor', 'name',)
    pagination_class = LargeResultsSetPagination
