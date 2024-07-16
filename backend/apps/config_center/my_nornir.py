import os
import re
from typing import List
from datetime import datetime
from nornir import InitNornir
from nornir.core.task import Result
from nornir_netmiko import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir_utils.plugins.tasks.files import write_file
from nornir.core.plugins.inventory import InventoryPluginRegister
from apps.config_center.models import ConfigBackup
from netaxe.settings import BASE_DIR
from utils.cmdb_inventory import CMDBInventory


InventoryPluginRegister.register("cmdb_inventory", CMDBInventory)

BACKUP_PATH = BASE_DIR + '/media/device_config/current-configuration'


def config_ignore(vendor, filename):
    final_lines = []
    # 读取配置文件
    with open(filename, 'r') as f:
        lines = f.readlines()
    for line in lines:
        # 定义要匹配的日期时间模式
        pattern = r'!Last\sconfiguration\swas\ssaved\sat.*'
        # 使用正则表达式替换匹配的字符串
        final_lines.append(re.sub(pattern, '', line))
    # 写回配置文件
    with open('config.txt', 'w') as f:
        f.writelines(final_lines)


# 配置备份
def configure_backup(task, path) -> Result:
    command_map = {
        'H3C': {'cmd': 'display current-configuration', 'expect_string': None, 'enable': False},
        'Huawei': {'cmd': 'display current-configuration', 'expect_string': None, 'enable': False},
        'Mellanox': {'cmd': 'show running-config', 'expect_string': None, 'enable': True},
        'Ruijie': {'cmd': 'show running-config', 'expect_string': None, 'enable': False},
        'centec': {'cmd': 'show running-config', 'expect_string': None, 'enable': False},
        'Hillstone': {'cmd': 'show configuration running', 'expect_string': None, 'enable': False},
        'inspur': {'cmd': 'show running-config', 'expect_string': None, 'enable': False},
        'Cisco': {'cmd': 'show running-config', 'expect_string': None, 'enable': False},
        # 'Maipu': {'cmd': 'show running-config', 'expect_string': ']'},  # 迈普的暂不不支持，待后续驱动适配
    }
    if task.host.data['vendor__alias'] in command_map.keys():
        command = command_map[task.host.data['vendor__alias']]
        res = task.run(task=netmiko_send_command,
                       command_string=command['cmd'],
                       expect_string=command['expect_string'],
                       enable=command['enable'])
        if not os.path.exists(f"{path}/{task.host}"):
            os.makedirs(f"{path}/{task.host}")
        task.run(task=write_file, content=res[0].result,
                 filename=f"{path}/{task.host}/{task.host.platform}-{task.host}.txt")
        return Result(
            host=task.host,
            result=f"{task.host}"
        )


# 配置备份(目前测试华三)
def config_backup_nornir(devices: List[dict]) -> InitNornir:
    """
    """
    log_time = datetime.now().strftime("%Y-%m-%d")
    with InitNornir(
            runner={
                "plugin": "threaded",
                "options": {
                    "num_workers": 10,
                },
            },
            inventory={
                "plugin": "cmdb_inventory",
                "options": {
                    "devices": devices,
                },
            },
            logging={"log_file": "normir.log", "level": "INFO", "enabled": False},
            # core={"raise_on_error": True}
    ) as nr:

        support_platform = [
            'huawei', 'huawei_telnet',
            'hp_comware', 'hp_comware_telnet',
            'ruijie_os', 'ruijie_os_telnet',
            'cisco_ios',
            'mellanox'
            ]
        device = nr.filter(filter_func=lambda host: host.platform in support_platform)
        backup_res = device.run(task=configure_backup, name='配置备份', path=BACKUP_PATH)
        # print_result(backup_res)
        return backup_res


if __name__ == '__main__':
    pass
