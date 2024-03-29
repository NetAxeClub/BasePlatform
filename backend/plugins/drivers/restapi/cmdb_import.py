# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      cmdb_import
   Description:
   Author:          Lijiamin
   date：           2023/6/26 15:51
-------------------------------------------------
   Change Activity:
                    2023/6/26 15:51
-------------------------------------------------
"""
import traceback

from driver.cmdb_import import RestApiDriver
from apps.automation.models import CollectionPlan
from apps.asset.models import (NetworkDevice, Vendor, Category, Model, IdcModel, Idc, Role, Rack, Attribute, Framework,
                               NetZone, AssetIpInfo, AssetAccount)
from apps.users.models import Organization
from os import getenv, environ
import logging
import requests
import json

log = logging.getLogger(__name__)


class CmdbImportDriver(RestApiDriver):
    """ 用于从现有第三方CMDB平台中获取资产数据导入到Netaxe 基础平台中 """
    driver_name = 'CmdbImport'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        log.info(f"CmdbImport")
        self.token_url = getenv('CMDB_TOKEN_URL')
        self.base_url = getenv('CMDB_BASE_URL')
        self.asset_account_url = "asset_account_protocol/"
        self.account_url = "cmdb_account/"
        self.protocol_url = "cmdb_protocol_port/"
        self.data = {
            'username': getenv('CMDB_USERNAME'),
            'password': getenv('CMDB_PASSWORD')
        }
        self.token = self.login()

        self.headers = {
            "Content-Type": "application/json;charset=UTF-8",
            'Authorization': 'Token ' + str(self.token)
        }

    def login(self):
        headers = {
            "Content-Type": "application/json;charset=UTF-8"
        }
        r = requests.post(self.token_url, data=json.dumps(self.data), headers=headers)
        try:
            return r.json().get('token')
        except Exception as e:
            raise Exception("Can't get netops_api token {}".format(str(e)))

    def do_something(self, url, params):
        url = self.base_url + url
        res = requests.get(url, params=params, headers=self.headers)
        if res.status_code == 200:
            return res.json()['results'] if 'results' in res.json() else res.json()
        return []

    def import_data(self):
        res = self.do_something('asset_networkdevice/', {'limit': 30000})
        sum_count = 0
        for i in res:
            try:
                # print(i)
                tmp = {
                    "manage_ip": i['manage_ip'],
                    "serial_num": i['serial_num'],
                    "name": i.get('name') or '',
                    "soft_version": i.get('soft_version') or '',
                    "patch_version": i.get('patch_version') or '',
                    "u_location_start": i['u_location_start'],
                    "u_location_end": i['u_location_end'],
                    "uptime": i['uptime'],
                    "expire": i['expire'],
                    "memo": i['memo'],
                    "status": i['status'],
                    "ha_status": i['ha_status'],
                    "chassis": i['chassis'],
                    "slot": i['slot'],
                    "auto_enable": i['auto_enable'],
                }
                idc_instance, _ = Idc.objects.get_or_create(name=i['idc_name'])
                tmp['idc'] = idc_instance
                if i.get('idc_model_name'):
                    idc_model_instance, _ = IdcModel.objects.get_or_create(idc=idc_instance, name=i['idc_model_name'])
                    tmp['idc_model'] = idc_model_instance
                    if i.get('rack_name'):
                        rack_instance, _ = Rack.objects.get_or_create(name=i['rack_name'], idc_model=idc_model_instance)
                        tmp['rack'] = rack_instance
                vendor_instance, _ = Vendor.objects.get_or_create(name=i['vendor_name'], alias=i['vendor_alias'])
                tmp['vendor'] = vendor_instance
                if i.get('model_name'):
                    model_instance, _ = Model.objects.get_or_create(name=i['model_name'].strip(),
                                                                    vendor=vendor_instance)
                    tmp['model'] = model_instance
                if i.get('role_name'):
                    role_instance, _ = Role.objects.get_or_create(name=i['role_name'])
                    tmp['role'] = role_instance
                if i.get('category_name'):
                    category_instance, _ = Category.objects.get_or_create(name=i['category_name'])
                    tmp['category'] = category_instance
                if i.get('attribute_name'):
                    attribute_instance, _ = Attribute.objects.get_or_create(name=i['attribute_name'])
                    tmp['attribute'] = attribute_instance
                if i.get('framework_name'):
                    framework_instance, _ = Framework.objects.get_or_create(name=i['framework_name'])
                    tmp['framework'] = framework_instance
                if i.get('netzone_name'):
                    netzone_instance, _ = NetZone.objects.get_or_create(name=i['netzone_name'])
                    tmp['zone'] = netzone_instance
                device_quert = NetworkDevice.objects.filter(serial_num=i['serial_num'])
                if not device_quert:
                    device_instance, _ = NetworkDevice.objects.create(**tmp)

                    if i['bind_ip']:
                        for _sub in i['bind_ip']:
                            _name, _ip = _sub.split('-')
                            bind_ip_data = {
                                "name": _name,
                                "ipaddr": _ip,
                                "device": device_instance,
                            }
                            AssetIpInfo.objects.get_or_create(defaults=bind_ip_data, **bind_ip_data)
                    if i['bgbu']:
                        org_list = []
                        for _sub in i['bgbu']:
                            org_instance, _ = Organization.objects.get_or_create(name=_sub)
                            org_list.append(org_instance.id)
                        if org_list:
                            device_instance.org.set(org_list)
                    if i.get('plan_name'):
                        plan_instance, _ = CollectionPlan.objects.get_or_create(name=i['plan_name'])
                        device_instance.plan = plan_instance
                    # 账户关联
                    if i.get('adpp_device'):
                        _account_device = self.do_something(url=self.asset_account_url, params={'asset': i['id']})
                        # print(_account_device)
                        account_list = []
                        for _sub_account_device in _account_device:
                            _account = self.do_something(
                                url="{}{}/".format(self.account_url, _sub_account_device['account']), params={})
                            _protocol = self.do_something(
                                url="{}{}/".format(self.protocol_url, _sub_account_device['protocol_port']), params={})
                            _account_tmp = {
                                'name': "{}-{}-{}".format(_account['name'], _protocol['protocol'], _protocol['port']),
                                'username': _account['username'],
                                'password': _account['password'],
                                'en_pwd': _account['en_pwd'],
                                'protocol': _protocol['protocol'],
                                'port': _protocol['port'],
                            }
                            account_instance, _ = AssetAccount.objects.get_or_create(**_account_tmp)
                            # account_instance, _ = AssetAccount.objects.get(**_account_tmp)
                            account_list.append(account_instance)
                        if account_list:
                            device_instance.account.set(account_list)
                            log.info("关联设备账户")
                    device_instance.save()
                    sum_count += 1
                    log.info(sum_count)
            except Exception as e:
                log.error(str(e))
                log.error("{}-{}".format(i['manage_ip'], i['serial_num']))
                print(traceback.print_exc())


if __name__ == '__main__':
    pass
    #  不允许直接运行，或者写任何调用的方法
