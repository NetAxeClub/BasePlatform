# -*- coding: utf-8 -*-
# 2023/8/28
from django.db import connections
from apps.asset.models import NetworkDevice, Category


def get_firewall_list(manage_ip_list=None):
    connections.close_all()
    category = Category.objects.filter(name='防火墙').values('id').first()
    all_devs = []
    # 获取所有cmdb设备
    if manage_ip_list:
        all_devs = NetworkDevice.objects.filter(auto_enable=True,
                                                manage_ip__in=manage_ip_list, category=category['id'], status=0,
                                                ha_status__in=[0, 1]).select_related(
            'id', 'vendor', 'category').prefetch_related('bind_ip').values(
            'id', 'manage_ip', 'name', 'vendor__alias', 'bind_ip__ipaddr', 'soft_version')
    else:
        all_devs = NetworkDevice.objects.filter(auto_enable=True,
                                                status=0, category=category['id'], ha_status__in=[0, 1]).select_related(
            'vendor', 'category').prefetch_related('bind_ip').values(
            'id', 'manage_ip', 'name', 'vendor__alias', 'bind_ip__ipaddr', 'soft_version')
    return all_devs


def get_device_info(**kwargs):
    res =  NetworkDevice.objects.filter(**kwargs).values()
    return list(res)