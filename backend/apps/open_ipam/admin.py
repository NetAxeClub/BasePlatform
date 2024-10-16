from django.contrib import admin

from .models import Subnet, IpAddress


# Register your models here.
@admin.register(Subnet)
class AdminSubnetModel(admin.ModelAdmin):
    """自定义网段显示字段"""
    list_display = ['subnet', 'id', 'mask', 'description', 'master_subnet']
    list_filter = ['subnet', 'id', 'mask', 'description', 'master_subnet']
    # Related Field got invalid lookup: icontains
    # 这个错误一般是由于你在admin.py文件里的search_fields使用了外键，而没有指定具体的字段。
    search_fields = ['subnet', 'id', 'mask', 'description', 'master_subnet__id']
    autocomplete_fields = ['master_subnet']
    # list_select_related = ['master_subnet']
    # change_form_template = 'admin/openwisp-ipam/subnet/change_form.html'
    # change_list_template = 'admin/openwisp-ipam/subnet/change_list.html'
    app_label = 'open_ipam'


@admin.register(IpAddress)
class AdminIpAddressModel(admin.ModelAdmin):
    """自定义IP地址显示字段"""
    list_display = ['ip_address', 'subnet', 'description', 'tag', 'lastOnlineTime']
    # list_filter = ['ip_address', 'subnet', 'description', 'tag', 'lastOnlineTime']
    search_fields = ['ip_address', 'subnet__name', 'description', 'tag', 'lastOnlineTime']
    autocomplete_fields = ['subnet']
    multitenant_parent = 'subnet'
    # form = IpAddressAdminForm
    # change_form_template = 'admin/openwisp-ipam/ip_address/change_form.html'
    # change_list_template = 'admin/openwisp-ipam/ip_address/change_list.html'
    app_label = 'open_ipam'
