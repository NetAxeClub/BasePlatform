from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.device_api.views import DeviceCollectionPlansViewSet, DeviceSubCollectionPlanViewSet, \
    NetconfXMLTemplateViewSet, CollectionResultViewSet, PlansToDeviceViewSet, \
    PlatformProfileViewSet, DeviceFactsAPIView, DeviceCapabilitiesAPIView, \
    DeviceCollectionRuleViewSet, DeviceCollectionMatchRuleViewSet, DeviceCollectionRuleToolView

# 创建路由器
router = DefaultRouter()
router.register(r'platform-profiles', PlatformProfileViewSet, basename='platform-profiles')
router.register(r'collection-rules', DeviceCollectionRuleViewSet, basename='collection-rules')
router.register(r'collection-match-rules', DeviceCollectionMatchRuleViewSet, basename='collection-match-rules')
router.register(r'collection-plans', DeviceCollectionPlansViewSet, basename='collection-plans')
router.register(r'sub-collection-plan', DeviceSubCollectionPlanViewSet, basename='sub-collection-plan')
router.register(r'xml-templates', NetconfXMLTemplateViewSet, basename='xml-templates')
router.register(r'collection-results', CollectionResultViewSet, basename='collection-results')
router.register(r'plans-to-device', PlansToDeviceViewSet, basename='plans-to-device')

app_name = 'device_api'

urlpatterns = [
    path('devices/<str:serial_num>/facts/', DeviceFactsAPIView.as_view(), name='device-facts'),
    path('devices/<str:serial_num>/capabilities/', DeviceCapabilitiesAPIView.as_view(), name='device-capabilities'),
    path('collection-rule-tools/', DeviceCollectionRuleToolView.as_view(), name='collection-rule-tools'),
    path('v1/devices/<str:serial_num>/facts/', DeviceFactsAPIView.as_view(), name='device-facts-v1'),
    path('v1/devices/<str:serial_num>/capabilities/', DeviceCapabilitiesAPIView.as_view(), name='device-capabilities-v1'),
    path('v1/collection-rule-tools/', DeviceCollectionRuleToolView.as_view(), name='collection-rule-tools-v1'),
    path('', include(router.urls)),
    path('v1/', include(router.urls)),
]
