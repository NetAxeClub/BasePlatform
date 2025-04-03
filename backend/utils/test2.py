# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      test2
   Description:
   Author:          Lijiamin
   date：           2024/10/28 15:37
-------------------------------------------------
   Change Activity:
                    2024/10/28 15:37
-------------------------------------------------
"""


import json
import os
import re
from netmiko import NetmikoTimeoutException, NetmikoAuthenticationException
from netmiko._textfsm import _clitable as clitable
from netmiko._textfsm._clitable import CliTableError
from textfsm import TextFSM
from ttp import ttp


def custom_fsm(path, template):
    ins = TextFSM(open(template, "r", encoding='utf8'))
    _content = open(path).read()
    print(_content)
    # _content = _content.decode('utf-8')
    # 将文本简析成字典
    result = ins.ParseTextToDicts(_content)
    return result

def test():
    path = "./test.txt"
    res = custom_fsm(path=path, template='test.textfsm')
    print(res)


if __name__ == '__main__':
    test()