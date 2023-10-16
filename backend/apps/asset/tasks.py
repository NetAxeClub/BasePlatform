# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:
   Author:          Lijiamin
   date：           2022/9/8 17:46
-------------------------------------------------
   Change Activity:
                    2022/9/8 17:46
-------------------------------------------------
"""
from __future__ import absolute_import, unicode_literals
import json
import logging
from netaxe.celery import AxeTask, app
admin_file_logger = logging.getLogger('webssh')


@app.task(base=AxeTask, once={'graceful': True})
def admin_file(filename, txts, header=None):
    try:
        if header:
            f = open(filename, 'a')
            f.write(json.dumps(header) + '\n')
            for txt in txts:
                f.write(json.dumps(txt) + '\n')
            f.close()
        else:
            with open(filename, 'a') as f:
                for txt in txts:
                    f.write(txt)
    except Exception as e:
        admin_file_logger.error("记录操作失败:{}".format(str(e)))
