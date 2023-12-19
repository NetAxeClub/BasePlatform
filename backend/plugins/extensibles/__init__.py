# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      __init__.py
   Description:
   Author:          Lijiamin
   date：           2023/12/6 17:11
-------------------------------------------------
   Change Activity:
                    2023/12/6 17:11
-------------------------------------------------
"""
import pyplugs
# All function names are going to be stored under names
names = pyplugs.names_factory(__package__)
labels = pyplugs.labels_factory(__package__)
info = pyplugs.info_factory(__package__)
# When read function is called, it will call a function received as parameter
call = pyplugs.call_factory(__package__)

"""
demo
import requests, re 
import plugins.extensibles
plugins.extensibles.call('reader_SG',abc='abc')
plugins.extensibles.info('reader_SG')
"""