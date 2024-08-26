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
import time
import requests
import logging
import threading
import logging.config
import yaml
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
        # self.ssl = data['ssl']
        for k, v in self.data.items():
            log.info("[Config set] key:%s, value:%s" % (k, v))
            setattr(self, k, v)

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

    def __healthyCheckThreadRun(self):
        while True:
            # 检查registerThread
            try:
                time.sleep(5)
                serviceIp = self.__registerDict["serviceIp"]
                servicePort = self.__registerDict["servicePort"]
                serviceName = self.__registerDict["serviceName"]
                namespaceId = self.__registerDict["namespaceId"]
                groupName = self.__registerDict["groupName"]
                clusterName = self.__registerDict["clusterName"]
                ephemeral = self.__registerDict["ephemeral"]
                metadata = self.__registerDict["metadata"]
                weight = self.__registerDict["weight"]
                enabled = self.__registerDict["enabled"]
                self.registerService(serviceIp, servicePort, serviceName,
                                     namespaceId, groupName, clusterName,
                                     ephemeral, metadata, weight, enabled)
            except Exception as e:
                logging.exception("服务注册心跳进程健康检查失败:{}".format(str(e)), exc_info=True)

            try:
                # 获取nacos配置并复写
                self.get_config()
            except Exception as e:
                logging.exception("配置更新失败:{}".format(str(e)), exc_info=True)

    def healthyCheck(self):
        t = threading.Thread(target=self.__healthyCheckThreadRun)
        t.start()
        logging.info("健康检查线程已启动")

    def registerService(self, serviceIp, servicePort, serviceName, namespaceId="public",
                        groupName="default", clusterName="DEFAULT",
                        ephemeral=True, metadata=None, weight=1, enabled=True):
        if metadata is None:
            metadata = {}
        self.__registerDict["serviceIp"] = serviceIp
        self.__registerDict["servicePort"] = servicePort
        self.__registerDict["serviceName"] = serviceName
        self.__registerDict["namespaceId"] = namespaceId
        self.__registerDict["groupName"] = groupName
        self.__registerDict["clusterName"] = clusterName
        self.__registerDict["ephemeral"] = ephemeral
        self.__registerDict["metadata"] = metadata
        self.__registerDict["weight"] = weight
        self.__registerDict["enabled"] = enabled
        self.__registerDict["healthy"] = int(time.time())

        registerUrl = "http://" + self.nacos + ":" + str(self.nacos_port) + "/nacos/v1/ns/instance"
        params = {
            "ip": serviceIp,
            "port": servicePort,
            "serviceName": serviceName,
            "namespaceId": namespaceId,
            "groupName": groupName,
            "clusterName": clusterName,
            "ephemeral": ephemeral,
            "metadata": json.dumps(metadata),
            "weight": weight,
            "enabled": enabled
        }
        try:
            re = requests.post(registerUrl, params=params)
            if re.text == "ok":
                logging.info("服务注册成功。")
            else:
                logging.error("服务注册失败 " + re.text)
        except:
            logging.exception("服务注册失败", exc_info=True)

    def get_config(self, group="default", tenant="public"):
        logging.info("正在获取配置: dataId=" + self.project_name + "; group=" + group + "; tenant=" + tenant)
        getConfigUrl = "http://" + self.nacos + ":" + str(self.nacos_port) + "/nacos/v1/cs/configs"
        # "dataId": config.project_name,
        params = {
            "dataId": self.project_name,
            "group": group,
            "tenant": tenant
        }
        try:
            res = requests.get(getConfigUrl, params=params)
            # print(res.status_code, res.text)  # 404 config data not exist
            if res.status_code == 200:
                nacos_conf = res.json()
                for k, v in nacos_conf.items():
                    log.info("[nacos ext_config set] key:%s, value:%s" % (k, v))
                    setattr(self, k, v)
        except Exception as e:
            logging.exception("配置获取失败：dataId=" + self.project_name + "; group=" + group + "; tenant=" + tenant,
                              exc_info=True)

    # 发现服务
    def service_dicovery(self, serviceName, groupName='default', namespaceId="public"):
        url = "http://" + self.nacos + ":" + str(self.nacos_port) + "/nacos/v1/ns/instance/list"
        params = {
            "serviceName": serviceName,
            "namespaceId": namespaceId,
            "groupName": groupName,
        }
        res = requests.get(url, params=params)
        return res


config = Config()


if __name__ == "__main__":
    print(config.custom_webhooks)
