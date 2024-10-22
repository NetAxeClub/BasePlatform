from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SubnetApiViewSet, IpAddressApiViewSet, SubnetAddressView, \
    IpAmSubnetTreeView, IpAmHandelView, IpamOpenAPI, IpAmAddressTagGroupView

router = DefaultRouter()
router.register(r'subnet_list', SubnetApiViewSet)  # 获取子网段列表
router.register(r'ip_address_list', IpAddressApiViewSet)

urlpatterns = [
    path(r'', include(router.urls)),
    path('subnet_tree/', IpAmSubnetTreeView.as_view(), name='subnet_tree'),
    path('ip_address_tag_group/', IpAmAddressTagGroupView.as_view(), name='ip_address_tag_group'),
    path('ipam_api/', IpamOpenAPI.as_view(), name='ipam_api'),
    path('address_handel/', IpAmHandelView.as_view(), name='address_handel'),
    path('subnet/<str:subnet_id>/ip_address/', SubnetAddressView.as_view(), name='subnet_ip_address'),
    # 供admin后台展示，暂未修改过多逻辑
    # path('subnet/<str:subnet_id>/hosts/', SubnetHostsView.as_view(), name='hosts'),
    # path(
    #     'subnet/<str:subnet_id>/get-next-available-ip/',
    #     AvailableIpView.as_view(),
    #     name='get_next_available_ip',
    # ),
]
