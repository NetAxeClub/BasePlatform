# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      test1
   Description:
   Author:          Lijiamin
   date：           2024/1/24 00:01
-------------------------------------------------
   Change Activity:
                    2024/1/24 00:01
-------------------------------------------------
"""
import os
from git import Repo
from git.compat import defenc
from netaxe.settings import BASE_DIR
repo_path = os.path.join(BASE_DIR, 'media/device_config')
# 初始化仓库位置
repo = Repo(repo_path)


def test():
    # 指定两个commit的hash值
    from_commit = '7c71676e4260f4ff800a75abcfac75bf3277f4c'
    to_commit = 'e3d6cfd54990921b23ad88803105302b629a7228'

    # 指定文件路径
    file_path = 'current-configuration/10.254.4.204/ruijie_os-10.254.4.204.txt'

    # 获取两个commit对象
    from_commit_obj = repo.commit(from_commit)
    to_commit_obj = repo.commit(to_commit)

    # 获取两个commit之间的差异
    diffs = from_commit_obj.diff(to_commit_obj, paths=[file_path], create_patch=True)
    # print(diffs)
    # 遍历差异并打印
    for diff in diffs:
        # 打印文件差异
        print(diff.diff.decode(defenc))