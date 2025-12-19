import django_filters
from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan, PlansToDevice


class PlansToDeviceFilter(django_filters.FilterSet):
    manage_ip = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = PlansToDevice
        fields = ['manage_ip', 'execute_node']


class DeviceCollectionPlansFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = DeviceCollectionPlans
        fields = ['name', 'vendor', 'device_type', 'is_active']


class DeviceSubCollectionPlanFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = DeviceSubCollectionPlan
        fields = ['summary_plan', 'summary_plan__vendor', 'summary_plan__device_type', 'name', 'description']
