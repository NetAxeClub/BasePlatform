import time
import os
from datetime import datetime
from apps.asset.models import *
import pandas as pd
from django.db import transaction


def str2time(str):
    if not str:
        csv_time = time.strftime("%Y-%m-%d", time.localtime())
        return csv_time
    else:
        str = str.replace('/', '-')
        csv_time = time.strftime("%Y-%m-%d", time.strptime(str, "%Y-%m-%d"))

        return csv_time


def csv_device_status(device_status):
    device_status_dict = {
        '在线': 0,
        '下线': 1,
        '挂牌': 2,
        '备用': 3
    }
    return device_status_dict[device_status]


def csv_attribute(attribute):
    attribute_dict = {
        '其它': 0,
        '研测网络': 1,
        '研发网络': 2,
        '生产网络': 3,
        '骨干网络': 4,
        '公网网络': 5,
    }
    return attribute_dict[attribute]


def csv_framework(framework):
    framework_dict = {
        '其它': '0',
        '大二层': '1',
        '三层': '2',
        '二层': '3',
    }
    return framework_dict[framework]


# 根据机柜编号、机房ID进行检索，若机柜不存在，则创建并返回创建后机柜ID
def search_cmdb_cabinet_id(cmdb_cabinet_name, cmdb_idc_model_id):
    cmdb_cabinet_instance = Rack.objects.filter(name=cmdb_cabinet_name,
                                                idc_model__id=cmdb_idc_model_id).values().first()

    if not cmdb_cabinet_instance:
        idc_model_instance = IdcModel.objects.filter(id=cmdb_idc_model_id).first() if cmdb_idc_model_id else None
        instance = Rack.objects.create(
            idc_model=idc_model_instance,
            name=cmdb_cabinet_name)
        return instance.id

    else:
        return cmdb_cabinet_instance['id']


# 根据机房模块编号、机房ID进行检索，若机房模块不存在，则创建并返回机房模块ID
def search_cmdb_idc_model_id(cmdb_idc_model_name, cmdb_idc_id):
    cmdb_idc_model_id = IdcModel.objects.filter(name=cmdb_idc_model_name, idc__id=cmdb_idc_id).values('id').first()
    if not cmdb_idc_model_id:
        instance = IdcModel.objects.create(idc=Idc.objects.filter(id=cmdb_idc_id).first() if cmdb_idc_id else None,
                                           name=cmdb_idc_model_name)
        return instance.id

    else:
        return cmdb_idc_model_id['id']


# 根据厂商ID进行检索
def search_device_model_id(device_model_name, vendor_id):
    device_model_id = Model.objects.filter(name=device_model_name, vendor_id=vendor_id).values('id').first()
    if not device_model_id:
        instance = Model.objects.create(vendor=Vendor.objects.filter(id=vendor_id).first() if vendor_id else None,
                                        name=device_model_name)
        return instance.id

    else:
        return device_model_id['id']


# 根据网络区域名称、机房ID、网络属性、网络架构等信息进行检索，若网络区域不存在，则创建并返回网络区域ID
def search_cmdb_netzone_id(cmdb_netzone_name):
    cmdb_netzone_instance = NetZone.objects.filter(name=cmdb_netzone_name).values('id').first()
    if not cmdb_netzone_instance:
        instance = NetZone.objects.create(name=cmdb_netzone_name)
        return instance.id
    else:
        return cmdb_netzone_instance['id']


# 根据设备角色名称、网络区域ID等信息进行检索，若设备角色不存在，则创建并返回设备角色ID
def search_cmdb_role_id(cmdb_role_name):
    cmdb_role_instance = Role.objects.filter(name=cmdb_role_name).values('id').first()

    if not cmdb_role_instance:
        instance = Role.objects.create(name=cmdb_role_name)
        return instance.id
    else:
        return cmdb_role_instance['id']


# 根据机房名称进行检索，若机房不存在，则创建并返回机房ID
def search_cmdb_idc_id(cmdb_idc_name):
    cmdb_idc_instance = Idc.objects.filter(name=cmdb_idc_name).values('id').first()

    if not cmdb_idc_instance:
        instance = Idc.objects.create(name=cmdb_idc_name)
        return instance.id

    else:
        return cmdb_idc_instance['id']


# 根据设备型号、厂商名称进行检索，若设备型号不存在，则创建并返回设备型号ID
def search_cmdb_category_id(cmdb_category_name):
    cmdb_category_instance = Category.objects.filter(name=cmdb_category_name).values('id').first()
    if cmdb_category_instance:
        return cmdb_category_instance['id']

    else:
        # print("{} 设备型号不存在，系统正在创建!".format(cmdb_category_name))
        instance = Category.objects.create(name=cmdb_category_name)
        return instance.id


# 根据设备属性名称查询设备属性ID
def search_cmdb_attribute_id(attribute_name):
    attribute_id_info = Attribute.objects.filter(name=attribute_name).values('id').first()
    if attribute_id_info:
        return attribute_id_info['id']

    else:
        instance = Attribute.objects.create(name=attribute_name)
        return instance.id


# 根据设备架构名称查询设备架构ID
def search_cmdb_framework_id(framework_name):
    framework_id_instance = Framework.objects.filter(name=framework_name).values('id').first()
    if framework_id_instance:
        return framework_id_instance['id']

    else:
        instance = Framework.objects.create(name=framework_name)
        return instance.id


# 根据厂商名称进行检索，若厂商不存在，则抛出msg
def search_cmdb_vendor_id(cmdb_vendor_name):
    if type(cmdb_vendor_name) == str:
        cmdb_vendor_instance = Vendor.objects.filter(name=cmdb_vendor_name).values('id').first()
        if cmdb_vendor_instance:
            return cmdb_vendor_instance['id']
        else:
            instance = Vendor.objects.create(name=cmdb_vendor_name)
            return instance.id
    else:
        return None


def new_import_server_parse(import_list):
    data_list = import_list
    new_lst = []
    import_fail_list = []  # 导入错误
    import_success_list = []  # 导入成功
    import_exists_list = []  # 导入失败-已存在
    # 预收集所有序列号用于批量检查
    all_serials = [str(item[0]).strip() for item in data_list if len(item) > 0]

    try:
        with transaction.atomic():
            devices_to_create = []
            for index, data in enumerate(data_list):
                if not data:  # 没有数据直接continue
                    continue

                # ok, msg = check_row(data, new_lst)  # 检查行数据是否完整，同时检查序列化是否相同
                # if not ok:
                #     import_fail_list.append({'reason': f"第{index + 1}行 {msg}"})
                #     continue

                new_lst.append(str(data[0]).strip())
                name = str(data[0]).strip()  # 名称
                manege_ip = str(data[1]).strip()  # 管理IP
                cmdb_idc_id = search_cmdb_idc_id(data[2])  # 机房

                server = {
                    'name': name,
                    'manage_ip': manege_ip,
                    'idc': Idc.objects.filter(id=cmdb_idc_id).first() if cmdb_idc_id else None,
                }
                try:
                    # 构造设备对象但不立即保存
                    device = Server(**server)
                    devices_to_create.append(device)
                    import_success_list.append({"manage_ip": manege_ip})
                except Exception as e:
                    print(f"数据校验失败: {e}")
                    import_fail_list.append({"manage_ip": manege_ip, "reason": f"第{index + 1}行数据校验失败: {e}"})

            # 批量创建所有有效设备
            if devices_to_create:
                Server.objects.bulk_create(devices_to_create, batch_size=100)

        return import_success_list, import_exists_list, import_fail_list, 'success'
    except Exception as e:
        print(f"事务执行失败: {e}")
        # 回滚事务后返回所有失败记录
        return [], import_exists_list, [{"reason": str(e)} for _ in import_success_list + import_fail_list], "error"

def new_import_parse(import_list):
    data_list = import_list
    new_lst = []
    import_fail_list = []  # 导入错误
    import_success_list = []  # 导入成功
    import_exists_list = []  # 导入失败-已存在

    # 预收集所有序列号用于批量检查
    all_serials = [str(item[0]).strip() for item in data_list if len(item) > 0]
    existing_serials = set(
        NetworkDevice.objects.filter(serial_num__in=all_serials).values_list('serial_num', flat=True))

    try:
        with transaction.atomic():
            devices_to_create = []
            for index, data in enumerate(data_list):
                if not data:  # 没有数据直接continue
                    continue

                ok, msg = check_row(data, new_lst)  # 检查行数据是否完整，同时检查序列化是否相同
                if not ok:
                    import_fail_list.append({'reason': f"第{index + 1}行 {msg}"})
                    continue

                new_lst.append(str(data[0]).strip())
                # SN1107500140038130	172.16.75.253	三层	深信服	交换机	合肥B3	4-3号	J05	万兆接入	公网区域	11 	11 	在线	生产网络	教育公共综合业务防火墙
                serial_num = str(data[0]).strip()  # 序列号
                manege_ip = str(data[1]).strip()  # 管理IP
                cmdb_framework_id = search_cmdb_framework_id(data[2])  # 网络架构
                cmdb_vendor_id = None if isinstance(data[3], float) else search_cmdb_vendor_id(
                    data[3].strip())  # 产商，非必填
                cmdb_category_id = search_cmdb_category_id(data[4])  # 设备类型
                cmdb_idc_id = search_cmdb_idc_id(data[5])  # 机房
                cmdb_idc_model_id = search_cmdb_idc_model_id(data[6], cmdb_idc_id)  # 模块
                cmdb_cabinet_id = search_cmdb_cabinet_id(data[7], cmdb_idc_model_id)  # 机柜
                cmdb_role_id = None if isinstance(data[8], float) else search_cmdb_role_id(data[8])  # 设备角色, 非必填
                cmdb_netzone_id = None if isinstance(data[9], float) else search_cmdb_netzone_id(data[9])  # 网络区域，非必填
                u_location_start = data[10]  # 起始U位
                u_location_end = data[11]  # 结束U位
                status = csv_device_status(data[12])  # 设备状态
                cmdb_attribute_id = None if isinstance(data[13], float) else None  # 网络属性，非必填
                memo = None if isinstance(data[14], float) else str(data[14]).strip()  # 备注，非非必填
                device_model_id = search_device_model_id(data[15], cmdb_vendor_id)  # 设备型号

                networkdevices = {
                    'serial_num': serial_num,
                    'manage_ip': manege_ip,
                    'vendor': Vendor.objects.filter(id=cmdb_vendor_id).first() if cmdb_vendor_id else None,
                    'idc': Idc.objects.filter(id=cmdb_idc_id).first() if cmdb_idc_id else None,
                    'category': Category.objects.filter(id=cmdb_category_id).first() if cmdb_category_id else None,
                    'role': Role.objects.filter(id=cmdb_role_id).first() if cmdb_role_id else None,
                    "attribute": Attribute.objects.filter(id=cmdb_attribute_id).first() if cmdb_attribute_id else None,
                    "framework": Framework.objects.filter(id=cmdb_framework_id).first() if cmdb_framework_id else None,
                    'zone': NetZone.objects.filter(id=cmdb_netzone_id).first() if cmdb_netzone_id else None,
                    'rack': Rack.objects.filter(id=cmdb_cabinet_id).first() if cmdb_cabinet_id else None,
                    'idc_model': IdcModel.objects.filter(id=cmdb_idc_model_id).first() if cmdb_idc_model_id else None,
                    'model': Model.objects.filter(id=device_model_id).first() if device_model_id else None,
                    'u_location_start': int(u_location_start),  # U位
                    'u_location_end': int(u_location_end),  # U位
                    'uptime': datetime.now().strftime('%Y-%m-%d'),  # 上线时间必须要，默认当前日期
                    'expire': '2099-01-01',  # 维保时间必须有，默认3年
                    'memo': memo,  # memo为备注信息
                    'status': status,
                    'auto_enable': True,
                    'is_monitor': True
                }

                if serial_num in existing_serials:
                    import_exists_list.append({"serial_num": serial_num, "manage_ip": manege_ip})
                    continue

                try:
                    # 构造设备对象但不立即保存
                    device = NetworkDevice(**networkdevices)
                    devices_to_create.append(device)
                    import_success_list.append({"serial_num": serial_num, "manage_ip": manege_ip})
                except Exception as e:
                    print(f"数据校验失败: {e}")
                    import_fail_list.append({"manage_ip": manege_ip, "reason": f"第{index + 1}行数据校验失败: {e}"})

            # 批量创建所有有效设备
            if devices_to_create:
                NetworkDevice.objects.bulk_create(devices_to_create, batch_size=100)

        return import_success_list, import_exists_list, import_fail_list, 'success'
    except Exception as e:
        print(f"事务执行失败: {e}")
        # 回滚事务后返回所有失败记录
        return [], import_exists_list, [{"reason": str(e)} for _ in import_success_list + import_fail_list], "error"


def check_row(data: list, serial_exists: list):
    error_message = ""
    for i in range(len(data)):
        if i not in [3, 8, 9, 13, 14] and isinstance(data[i], float):
            error_message += f"第{i + 1}列存在数据为空\n"
            break

        if i == 0 and str(data[0]).strip() in serial_exists:  # 判断序列号是否重复
            error_message += f"第{i + 1}列序列号已存在\n"
            break

    if error_message:
        return False, error_message.strip()
    return True, "数据检查通过"


def pandas_read_file(filename, **kwargs):
    """Read file with **kwargs; files supported: xls, xlsx, csv, csv.gz, pkl"""

    read_map = {'xls': pd.read_excel, 'xlsx': pd.read_excel, 'csv': pd.read_csv,
                'gz': pd.read_csv, 'pkl': pd.read_pickle}

    ext = os.path.splitext(filename)[1].lower()[1:]
    assert ext in read_map, "Input file not in correct format, must be xls, xlsx, csv, csv.gz, pkl; current format '{0}'".format(
        ext)
    assert os.path.isfile(filename), "File Not Found Exception '{0}'.".format(filename)

    return read_map[ext](filename, engine='openpyxl')


if __name__ == "__main__":
    pass
