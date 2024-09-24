# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      config.py
   Description:
   Author:          Lijiamin
   date：           2023/3/30 10:09
-------------------------------------------------
   Change Activity:
                    2023/3/30 10:09
-------------------------------------------------
"""
import json
import nacos
import logging
import logging.config
import yaml
import getpass
import bcrypt
from pathlib import Path

log = logging.getLogger(__name__)
# 缺省配置  示例配置
DEFAULTS_FILENAME = "../config/defaults.json"
# 实际运行配置，会覆盖缺省配置
CONFIG_FILENAME = "../config/config.json"
MENU_FILENAME = "../web/default_menu.json"
NAMESPACE = "public"

try:
    yaml_loader = yaml.CSafeLoader
except AttributeError:
    yaml_loader = yaml.SafeLoader


# 加载前端默认菜单
def load_memu_files() -> list:
    try:
        with open(MENU_FILENAME) as infil:
            return json.load(infil)
    except FileNotFoundError:
        log.warning(f"Couldn't find {MENU_FILENAME}")

    return []


# 加载配置文件
def load_config_files() -> dict:
    data = {}
    for fname in (DEFAULTS_FILENAME, CONFIG_FILENAME):
        try:
            with open(fname) as infil:
                data.update(json.load(infil))
        except FileNotFoundError:
            log.warning(f"Couldn't find {fname}")

    if not data:
        raise RuntimeError(
            f"Could not find either {DEFAULTS_FILENAME} or {CONFIG_FILENAME}"
        )

    return data

class Config:
    _instance = None

    def __init__(self):
        self.default_menu = load_memu_files()
        data = load_config_files()
        self.__registerDict = {}
        self.__configDict = {}
        self.healthy = ""
        self.data = data
        self.log_config_filename = data['log_config_filename']
        self.project_name = data['project_name']
        self.nacos = data['nacos']
        self.nacos_port = data['nacos_port']
        self.nacos_password = data['nacos_password']
        self.local_dev = data['local_dev']
        for k, v in self.data.items():
            log.info("[Config set] key:%s, value:%s" % (k, v))
            setattr(self, k, v)
        # if not self.local_dev:
        self.client = nacos.NacosClient(server_addresses=f"{self.nacos}:{self.nacos_port}", username="nacos",
                                        password=self.nacos_password, log_level="INFO")

    # 单例模式
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    # 项目日志配置
    def setup_logging(self, max_debug=False):
        with open(self.log_config_filename) as infil:
            log_config_dict = yaml.load(infil, Loader=yaml_loader)

        if max_debug:
            for handler in log_config_dict["handlers"].values():
                handler["level"] = "DEBUG"

            for logger in log_config_dict["loggers"].values():
                logger["level"] = "DEBUG"

            log_config_dict["root"]["level"] = "DEBUG"

        logging.config.dictConfig(log_config_dict)
        log.info(f"confload: Logging setup @ {__name__}")

    # 获取项目根目录
    @property
    def get_root_path(self):
        file_path = Path(__file__).resolve()  # 获取当前文件的绝对路径
        root_path = file_path.parent  # 获取当前文件所在目录的路径
        while root_path.name != self.project_name:  # 根据实际情况修改根目录的名称
            root_path = root_path.parent  # 获取上级目录的路径
        return str(root_path)

    def service_dicovery(self, serviceName, groupName='default', namespaceId="public"):
        res = self.client.list_naming_instance(service_name=serviceName, group_name=groupName, namespace_id=namespaceId)
        return res

    def save_bcrypt_passwd(self):
        data = {}
        with open(CONFIG_FILENAME) as f:
            data.update(json.load(f))
        hashed_password = bcrypt.hashpw(self.nacos_password.encode("utf-8"), bcrypt.gensalt())
        data['hashed_password'] = hashed_password.decode()
        try:
            with open(CONFIG_FILENAME, "w") as f:
                f.write(json.dumps(data, indent=4))
        except FileNotFoundError:
            log.warning(f"Couldn't find {f}")
        return True


config = Config()


if __name__ == "__main__":
    pass
