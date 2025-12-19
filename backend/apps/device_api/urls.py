from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.device_api.views import DeviceCollectionPlansViewSet, DeviceSubCollectionPlanViewSet, \
    NetconfXMLTemplateViewSet, CollectionResultViewSet, PlansToDeviceViewSet

# 创建路由器
router = DefaultRouter()
router.register(r'collection-plans', DeviceCollectionPlansViewSet, basename='collection-plans')
router.register(r'sub-collection-plan', DeviceSubCollectionPlanViewSet, basename='sub-collection-plan')
router.register(r'xml-templates', NetconfXMLTemplateViewSet, basename='xml-templates')
router.register(r'collection-results', CollectionResultViewSet, basename='collection-results')
router.register(r'plans-to-device', PlansToDeviceViewSet, basename='plans-to-device')

app_name = 'device_api'

urlpatterns = [
    path('', include(router.urls)),
]
