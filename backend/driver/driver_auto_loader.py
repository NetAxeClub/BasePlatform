import logging


import importlib
import os

from driver.cmdb_import import RestApiDriver
from driver.batman import BatManDriver

from confload.confload import config

log = logging.getLogger(__name__)


def driver_auto_loader():
    driver_map = {}
    driver_dir = config.drivers  # config.drivers
    driver_dir_module_path = driver_dir.replace("/", ".")
    drivers = os.listdir(driver_dir)
    for driver in drivers:
        driver_files = os.listdir(f"{driver_dir}{driver}")
        for driver_file in driver_files:
            if driver_file.endswith(".py") and not driver_file.startswith("__"):
                driver_module = driver_file.replace(".py", "")
                print(f"{driver_dir_module_path}{driver}.{driver_module}")
                driver_module = importlib.import_module(
                    f"{driver_dir_module_path}{driver}.{driver_module}"
                )
                for driver_class in driver_module.__dict__.values():
                    if type(driver_class) == type and issubclass(
                        driver_class, RestApiDriver
                    ):
                        if driver_class != RestApiDriver:
                            try:
                                driver_map[driver_class.driver_name] = driver_class
                                log.debug(f"loaded driver: {driver_class.driver_name}")
                            except Exception as e:
                                log.error(f"unable to load driver with error: {e}")
    return driver_map


# 自动化插件
def auto_driver_auto_loader():
    driver_map = {}
    driver_dir = config.drivers  # config.drivers
    driver_dir_module_path = driver_dir.replace("/", ".")
    drivers = os.listdir(driver_dir)
    for driver in drivers:
        driver_files = os.listdir(f"{driver_dir}{driver}")
        for driver_file in driver_files:
            if driver_file.endswith(".py") and not driver_file.startswith("__"):
                driver_module = driver_file.replace(".py", "")
                log.info(f"加载插件：{driver_dir_module_path}{driver}.{driver_module}")
                driver_module = importlib.import_module(
                    f"{driver_dir_module_path}{driver}.{driver_module}"
                )
                for driver_class in driver_module.__dict__.values():
                    if type(driver_class) == type and issubclass(
                            driver_class, BatManDriver
                    ):
                        if driver_class != BatManDriver:
                            try:
                                driver_map[driver_class.driver_name] = driver_class
                                log.debug(f"loaded driver: {driver_class.driver_name}")
                            except Exception as e:
                                log.error(f"unable to load driver with error: {e}")
    return driver_map