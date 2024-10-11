from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt

from rest_framework import routers

from .views import DashboardChart, WebSshView, DeviceCollectView, AutomationChart, \
    DispatchManageView, JobCenterView, PeriodicTaskViewSet, IntervalScheduleViewSet, ServerWebSshView, \
    NetworkDeviceWebSshView, NewServerWebSshView, TaskResultViewSet

app_name = 'vue_backend'
router = routers.SimpleRouter()
router.register(r'periodic_task', PeriodicTaskViewSet)
router.register(r'interval_schedule', IntervalScheduleViewSet)
router.register(r'task_result', TaskResultViewSet)

urlpatterns = [
    path(r'', include(router.urls)),
    path('dashboardChart/', DashboardChart.as_view(), name='dashboardChart'),
    path('device_webssh/', WebSshView.as_view(), name='device_webssh'),
    path('network_device_webssh/', NetworkDeviceWebSshView.as_view(), name='network_device_webssh'),
    path('new_server_webssh/', NewServerWebSshView.as_view(), name='new_server_webssh'),
    path('server_webssh/', ServerWebSshView.as_view(), name='server_webssh'),
    path('deviceCollect/', DeviceCollectView.as_view(), name='deviceCollect'),
    path('automationChart/', AutomationChart.as_view(), name='automationChart'),
    path('dispatch_page/', csrf_exempt(DispatchManageView.as_view()), name='dispatch_page'),
    path('jobCenter/', JobCenterView.as_view(), name='jobCenter'),
]
