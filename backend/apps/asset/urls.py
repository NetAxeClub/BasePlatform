# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      urls
   Description:
   Author:          Lijiamin
   date：           2022/7/29 10:57
-------------------------------------------------
   Change Activity:
                    2022/7/29 10:57
-------------------------------------------------
"""
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from .views import *

# app_name = 'asset'
router = DefaultRouter()

router.register(r'cmdb_idc', IdcViewSet)
router.register(r'cmdb_idc_model', CmdbIdcModelViewSet)
router.register(r'cmdb_netzone', CmdbNetzoneModelViewSet)
router.register(r'cmdb_rack', CmdbRackModelViewSet)
router.register(r'cmdb_account', AccountList)
router.register(r'server_account', ServerAccountList)
router.register(r'cmdb_server_vendor', ServerVendorList)
router.register(r'cmdb_vendor', VendorViewSet)
router.register(r'cmdb_role', AssetRoleViewSet)
router.register(r'cmdb_category', CategoryViewSet)
router.register(r'cmdb_model', ModelViewSet)
router.register(r'attribute', AttributelViewSet)
router.register(r'framework', FrameworkViewSet)
router.register(r'asset_networkdevice', NetworkDeviceViewSet)
router.register(r'asset_server', ServerDeviceViewSet)
router.register(r'cmdb_server_vendor', ServerVendorViewSet)
router.register(r'cmdb_server_model', ServerModelViewSet)
router.register(r'container', ContainerServiceViewSet)
router.register(r'login_record', AdminRecordViewSet)

urlpatterns = [
    path(r'', include(router.urls)),
    path('import_template', ResourceManageExcelView.as_view(), name='import_template'),
    path('device_account', DeviceAccountView.as_view(), name='device_account'),
    path('cmdbChart', CmdbChart.as_view(), name='device_account'),
    path('firewall_base/', FirewallBase.as_view(), name="firewall_base"),  # 通用属性
    path('address_set/', AddressSet.as_view(), name="address_set"),  # 地址组
    path('service_set/', ServiceSet.as_view(), name="service_set"),  # 服务组
    path('dnat/', DestAddTranslate.as_view(), name="dnat"),  # DNAT
]
