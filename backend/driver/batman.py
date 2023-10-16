# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      batman
   Description:
   Author:          Lijiamin
   date：           2023/7/13 11:05
-------------------------------------------------
   Change Activity:
                    2023/7/13 11:05
-------------------------------------------------
"""
import logging
# from typing import List, Dict
from apps.asset.models import NetworkDevice
from apps.automation.models import CollectionRule

log = logging.getLogger(__name__)


class BatManDriver:
    """ 自动化插件 """

    driver_name = None

    def __init__(self):
        # 数据暂存
        # self.data = List[Dict]
        pass

    def run(self, data: list):
        raise NotImplementedError
