# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      base_file_tree
   Description:
   Author:          Lijiamin
   date：           2023/12/8 15:25
-------------------------------------------------
   Change Activity:
                    2023/12/8 15:25
-------------------------------------------------
"""
from pathlib import Path


class BaseTree:
    def __init__(self, pathname, root_path):
        self.tree_data = {}
        self.tree_final = []
        self.pathname = Path(pathname)
        self.tree_str = ''
        self.key = 0
        self.root_path = root_path
        self.black_list = ['.git', '__pycache__']

    def _second_path(self, root_name, pathname):
        self.key += 1
        data = {
            'id': self.key,
            'key': root_name + '/' + pathname.name,
            'label': pathname.name,
        }
        if pathname.is_dir():
            data['children'] = []
            for cp in pathname.iterdir():
                self.key += 1
                sub_data = {
                    'id': self.key,
                    'key': data['key'] + '/' + cp.name,
                    'label': cp.name,
                }
                data['children'].append(sub_data)
        self.tree_data[root_name]['children'].append(data)

    def root_tree(self):
        # 遍历根目录下所有文件
        for root in self.pathname.iterdir():
            if root.name not in self.black_list:
                self.key += 1
                data = {
                    'id': root.name,
                    'key': root.name,
                    'label': root.name,
                }
                self.tree_data[root.name] = data
                if root.is_dir():
                    data['children'] = []
                    for cp in root.iterdir():
                        if cp.name not in self.black_list:
                            self._second_path(root.name, cp)

    def produce_tree(self):
        self.root_tree()
        self.tree_final = [self.tree_data[k] for k in self.tree_data.keys()]