from django.contrib import admin
from .models import *


class AdminIdcModel(admin.ModelAdmin):
    """自定义机房表显示字段"""
    list_display = ['name', 'floor', 'area', 'idc']
    search_fields = ['name', 'floor', 'area', 'idc__name']


class AdminAssetAccount(admin.ModelAdmin):
    """自定义机房表显示字段"""
    list_display = ['name', 'username', 'protocol', 'port']
    search_fields = ['name', 'username', 'protocol', 'port']


class AdminNetworkDevice(admin.ModelAdmin):
    """自定义设备表显示字段"""
    list_display = ['name', 'manage_ip', 'serial_num', 'account_list']
    search_fields = ['serial_num', 'manage_ip', 'idc__name', 'category__name',
                     'name', 'vendor__name', 'patch_version',  'soft_version',
                     'model__name',  'memo', 'status', 'ha_status']


class AdminServerDevice(admin.ModelAdmin):
    """自定义设备表显示字段"""
    list_display = ['name', 'manage_ip', 'serial_num', ]
    search_fields = ['serial_num', 'manage_ip', 'idc__name', 'model__name',
                     'name', 'vendor__name', 'idc_model__name', 'rack__name',
                     'u_location_start', 'u_location_end', 'uptime', 'expire', 'memo', 'status', 'ha_status']


admin.site.register(Idc)
admin.site.register(Role)
admin.site.register(Rack)
admin.site.register(Model)
admin.site.register(Vendor)
admin.site.register(NetZone)
admin.site.register(Category)
admin.site.register(Attribute)
admin.site.register(Framework)
admin.site.register(ServerAccount)
admin.site.register(ServerVendor)
admin.site.register(ServerModel)
admin.site.register(IdcModel, AdminIdcModel)
admin.site.register(AssetAccount, AdminAssetAccount)
admin.site.register(NetworkDevice, AdminNetworkDevice)
admin.site.register(Server, AdminServerDevice)
