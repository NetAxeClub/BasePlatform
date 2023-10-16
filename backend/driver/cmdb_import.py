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
import logging
from typing import List, Dict

log = logging.getLogger(__name__)


class RestApiDriver:
    """ 用于从现有第三方平台Restful api中获取数据导入到Netaxe 基础平台中 """

    driver_name = None

    def __init__(self, **kwargs):
        # 数据暂存
        self.data = List[Dict]

    def login(self):
        """connect to the device"""
        raise NotImplementedError

    def requests_get(self, url, params):
        """send a command to the device"""
        raise NotImplementedError

    def import_data(self):
        raise NotImplementedError