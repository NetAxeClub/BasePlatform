# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tmp
   Description:
   Author:          Lijiamin
   date：           2024/3/27 11:09
-------------------------------------------------
   Change Activity:
                    2024/3/27 11:09
-------------------------------------------------
"""
import os

path = '/Users/lijiamin/Downloads/企信部原始数据/'
file_list = os.listdir(path)
for table_name in file_list:
    # print(table_name)
    if table_name.startswith('asset_networkdevice.csv'):
        if table_name.find('.csv') != -1:
            with open(os.path.join(path, table_name), 'r', encoding='utf-8') as r:
                readlines = r.readlines()
                fileds = readlines[0]
                for line in readlines[1:]:
                    line = ','.join(["'{}'".format(v) for v in line.split(',')])
                    sql_str = """insert into {table_name} ({fileds}) values ({values});""".format(table_name=table_name.split('.')[0], fileds=fileds, values=line.strip())
                    print(sql_str)