from apps.device_api.models import (
    DeviceCollectionMatchRule,
    DeviceCollectionRule,
    DeviceCollectionPlans,
    DeviceSubCollectionPlan,
    PlansToDevice,
    PlatformProfile,
)
import django_filters


class PlansToDeviceFilter(django_filters.FilterSet):
    manage_ip = django_filters.CharFilter(lookup_expr='icontains')
    device_serial_num = django_filters.CharFilter(lookup_expr='icontains')
    profile_code = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = PlansToDevice
        fields = ['manage_ip', 'device_serial_num', 'profile_code', 'binding_source', 'is_active', 'plan']


class DeviceCollectionPlansFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = DeviceCollectionPlans
        fields = ['name', 'vendor', 'device_type', 'profile_code', 'plan_kind', 'collection_method', 'is_default', 'is_active']


class DeviceSubCollectionPlanFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = DeviceSubCollectionPlan
        fields = ['summary_plan', 'summary_plan__vendor', 'summary_plan__device_type', 'name', 'description']


class DeviceCollectionRuleFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = DeviceCollectionRule
        fields = ["name", "module", "method", "plugin"]


class DeviceCollectionMatchRuleFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = DeviceCollectionMatchRule
        fields = ["name", "fields", "operator", "rule"]


class PlatformProfileFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(lookup_expr="icontains")
    vendor_alias = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = PlatformProfile
        fields = ["code", "vendor_alias", "category", "is_active"]
