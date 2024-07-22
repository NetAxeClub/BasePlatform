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
from os import getenv
from driver.cmdb_import import RestApiDriver
from apps.automation.models import CollectionPlan
from apps.asset.models import (NetworkDevice, Vendor, Category, Model, IdcModel, Idc, Role, Rack, Attribute, Framework,
                               NetZone, AssetIpInfo, AssetAccount, ServerModel, ServerVendor, Server)
from utils.db.mongo_ops import MongoOps
import logging
import requests
import json

# log = logging.getLogger(__name__)
log = logging.getLogger('server')
log_mongo = MongoOps(db='BasePlatform', coll='CMDBSync')

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
        res = self.do_something('asset_networkdevice/', {'limit': 8000})
        sum_count = 0
        fail_count = 0
        for i in res:
            try:
                log.info(i)
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
                idc_name = i['idc_name']
                model_name = i.get('model_name')
                idc_instance_query = Idc.objects.filter(name=idc_name)
                log.info(str(idc_instance_query))
                if idc_instance_query:
                    tmp['idc'] = Idc.objects.get(name=idc_name)
                else:
                    tmp['idc'] = Idc.objects.create(name=idc_name)

                vendor_instance_query = Vendor.objects.filter(name=i['vendor_name'], alias=i['vendor_alias'])
                if vendor_instance_query:
                    tmp['vendor'] = Vendor.objects.get(name=i['vendor_name'], alias=i['vendor_alias'])
                else:
                    tmp['vendor'] = Vendor.objects.create(name=i['vendor_name'], alias=i['vendor_alias'])

                if model_name is not None:
                    try:
                        model_instance_query = Model.objects.filter(name=model_name.strip(), vendor=tmp['vendor'])
                        if model_instance_query:
                            tmp['model'] = Model.objects.get(name=model_name.strip(), vendor=tmp['vendor'])
                        else:
                            tmp['model'] = Model.objects.create(name=model_name.strip(), vendor=tmp['vendor'])
                    except Exception as e:
                        pass
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
                    category_instance_query = Category.objects.filter(name=i['category_name'])
                    if category_instance_query:
                        tmp['category'] = Category.objects.get(name=i['category_name'])
                    else:
                        tmp['category'] = Category.objects.create(name=i['category_name'])
                device_quert = NetworkDevice.objects.filter(serial_num=i['serial_num'])
                if not device_quert:
                    # device_instance, _ = NetworkDevice.objects.create(**tmp)
                    device_instance = NetworkDevice.objects.create(**tmp)
                else:
                    device_instance = NetworkDevice.objects.get(serial_num=i['serial_num'])
                if i['bind_ip']:
                    for _sub in i['bind_ip']:
                        _name, _ip = _sub.split('-')
                        bind_ip_data = {
                            "name": _name,
                            "ipaddr": _ip,
                            "device": device_instance,
                        }
                        AssetIpInfo.objects.get_or_create(defaults=bind_ip_data, **bind_ip_data)
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
                log_mongo.insert({'manage_ip': i['manage_ip'], 'serial_num': i['serial_num'], 'error': str(e)})
                print(traceback.print_exc())
                fail_count += 1
        print("同步结束")
        print(sum_count)
        print(fail_count)

    def import_account(self):
        res = self.do_something('cmdb_account/', {'limit': 5000})
        for i in res:
            tmp = {
                "name": i['name'],
                "username": i['username'],
                "password": i['password'],
                "role": i['role'],
                "en_pwd": i['en_pwd'],
                "protocol": "ssh",
                "port": "22",
            }
            account_instance_query = AssetAccount.objects.filter(name=i['name'])
            if not account_instance_query:
                AssetAccount.objects.create(**tmp)

    def import_server(self):
        res = self.do_something('asset_server/', {'limit': 5000})
        sum_count = 0
        fail_count = 0
        for i in res:
            try:
                log.info(i)
                tmp = {
                    "name": i.get('name') or '',
                    "serial_num": i['serial_num'],
                    "manage_ip": i['manage_ip'],
                    "sub_asset_type": i['sub_asset_type'],
                    "cpu_model": i['cpu_model'],
                    "cpu_number": i['cpu_number'],
                    "vcpu_number": i['vcpu_number'],
                    "disk_total": i['disk_total'],
                    "ram_total": i['ram_total'],
                    "kernel": i['kernel'],
                    "system": i['system'],
                    "host_vars": i['host_vars'],
                    "status": i['status'],
                    "manager_name": i['manager_name'],
                    "manager_tel": i['manager_tel'],
                    "purpose": i['purpose'],
                    "memo": i['memo'],
                }
                # idc
                # vendor
                # rack
                # idc_model
                # model
                # hosted_on
                # account
                device_quert = Server.objects.filter(serial_num=i['serial_num'])
                if device_quert:
                    continue
                if i.get('u_location'):
                    if i['u_location'].find('-') != -1:
                        tmp['u_location_start'] = i['u_location'].strip('U').split('-')[0]
                        tmp['u_location_end'] = i['u_location'].strip('U').split('-')[-1]
                    else:
                        tmp['u_location_start'] = i['u_location'].strip('U')
                        tmp['u_location_end'] = i['u_location'].strip('U')
                idc_instance, _ = Idc.objects.get_or_create(name=i['idc_name'])
                tmp['idc'] = idc_instance
                vendor_instance, _ = ServerVendor.objects.get_or_create(name=i['vendor_name'])
                tmp['vendor'] = vendor_instance
                if i.get('idc_model_name'):
                    idc_model_instance, _ = IdcModel.objects.get_or_create(idc=idc_instance, name=i['idc_model_name'])
                    tmp['idc_model'] = idc_model_instance
                    if i.get('rack_name'):
                        rack_instance, _ = Rack.objects.get_or_create(name=i['rack_name'], idc_model=idc_model_instance)
                        tmp['rack'] = rack_instance
                if i.get('model_name'):
                    print(vendor_instance.name, i['model_name'], i['manage_ip'])
                    model_instance, _ = ServerModel.objects.get_or_create(name=i['model_name'].strip(),
                                                                          vendor=vendor_instance)
                    tmp['model'] = model_instance

                if not device_quert:
                    device_instance = Server.objects.create(**tmp)
                else:
                    device_instance = Server.objects.get(serial_num=i['serial_num'])
                # 账户关联
                if i.get('to_account'):
                    account_list = []
                    for _sub_account in i['to_account']:
                        _account = self.do_something(
                            url="{}".format(self.account_url), params={'name': _sub_account.split(':')[-1]})
                        if _account:
                            _account_tmp = {
                                'name': _account[0]['name'],
                                'username': _account[0]['username'],
                                'password': _account[0]['password'],
                                'en_pwd': _account[0]['en_pwd'],
                                'protocol': 'ssh',
                                'port': 22,
                            }
                            account_instance, _ = AssetAccount.objects.get_or_create(**_account_tmp)
                            account_list.append(account_instance)
                    if account_list:
                        device_instance.account.set(account_list)
                        log.info("关联设备账户")
                sum_count += 1
                log.info(sum_count)
            except Exception as e:
                log.error(str(e))
                log.error("{}-{}".format(i['manage_ip'], i['serial_num']))
                print(traceback.print_exc())
                fail_count += 1
        print("同步结束")
        print(sum_count)
        print(fail_count)


if __name__ == '__main__':
    pass
    #  不允许直接运行，或者写任何调用的方法
