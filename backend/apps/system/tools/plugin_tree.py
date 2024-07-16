# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      plugin_tree
   Description:
   Author:          Lijiamin
   date：           2023/12/8 15:01
-------------------------------------------------
   Change Activity:
                    2023/12/8 15:01
-------------------------------------------------
"""
import os
from utils.base_file_tree import BaseTree
from netaxe.settings import BASE_DIR

if not os.path.exists(os.path.join(BASE_DIR, 'plugins/extensibles')):
    os.makedirs(os.path.join(BASE_DIR, 'plugins/extensibles'))

class PluginsTree(BaseTree):

    def __init__(self):
        super(PluginsTree, self).__init__(BASE_DIR + '/plugins/extensibles/', 'extensibles/')



if __name__ == "__main__":
    _tree = PluginsTree()
    _tree.produce_tree()
    for i in _tree.tree_final:
        print(i)