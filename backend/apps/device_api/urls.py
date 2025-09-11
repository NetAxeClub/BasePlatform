from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.device_api.views import DeviceSummaryPlansViewSet, DeviceCollectionPlanViewSet, NetconfXMLTemplateViewSet, \
    CollectionResultViewSet, CollectionLogViewSet

# 创建路由器
router = DefaultRouter()
router.register(r'summary-plans', DeviceSummaryPlansViewSet, basename='summary-plans')
router.register(r'collection-plan', DeviceCollectionPlanViewSet, basename='collection-plan')
router.register(r'xml-templates', NetconfXMLTemplateViewSet, basename='xml-templates')
router.register(r'collection-results', CollectionResultViewSet, basename='collection-results')
router.register(r'collection-logs', CollectionLogViewSet, basename='collection-logs')

app_name = 'device_api'

urlpatterns = [
    # 包含路由器生成的URL
    path('', include(router.urls)),
]
