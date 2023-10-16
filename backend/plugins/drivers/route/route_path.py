# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      route_path
   Description:
   Author:          Lijiamin
   date：           2023/6/26 15:51
-------------------------------------------------
   Change Activity:
                    2023/7/26 15:51
-------------------------------------------------
"""
from driver.batman import BatManDriver
import logging
import requests
import json


log = logging.getLogger(__name__)


class RouteDriver(BatManDriver):
    driver_name = 'route_driver'

    def run(self, data: list):
        pass