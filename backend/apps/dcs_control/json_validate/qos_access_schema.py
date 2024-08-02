# -*- coding: utf-8 -*-
# @Time    : 2022/3/4 09:29
# @Author  : jmli12
# @Site    : 
# @File    : qos_policy_schema.py
# @Software: PyCharm
"""

"""
qos_access_schema = {
    # 定义
    "definitions": {
        "mqc_new": {
            "type": "boolean", "enum": [True, False]
        },
        "mqc_edit": {
            "type": "boolean", "enum": [True, False]
        },
        "mqc_del": {
            "type": "boolean", "enum": [True, False]
        },
    },
    # 依赖关系
    "dependencies": {
        "mqc_new": ["server_ip", "cir", "device_ip", "interface", "vendor", "hostid", "overwrite"],
        "mqc_edit": ["server_ip", "cir", "device_ip", "interface", "vendor", "hostid"],
        "mqc_del": ["server_ip", "device_ip", "interface", "vendor", "hostid"],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "qos_access_config",
    "type": "object",
    # 属性/字段
    "properties": {
        "mqc_new": {
            "$ref": "#/definitions/mqc_new"
        },
        "mqc_edit": {
            "$ref": "#/definitions/mqc_edit"
        },
        "mqc_del": {
            "$ref": "#/definitions/mqc_del"
        },
        "server_ip": {
            "type": "string", "description": "服务器IP", "enum": ['42.62.43.58', '42.62.43.59', '42.62.43.60', '42.62.43.61'],
            "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"
        },
        "device_ip": {
            "type": "string", "description": "设备IP", "enum": ['10.254.15.122', '10.254.5.7', '10.254.5.6'],
            "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"
        },
        "cir": {"type": "integer", "default": 4000, "multipleOf": 8},
        "interface": {
            "type": "string",
            "description": "设备接口名",
            "minLength": 3, "maxLength": 50
        },
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "overwrite": {"type": "boolean", "description": "覆盖", "enum": [True, False]},
        "hostid": {"type": "integer"},
        # "name": {"type": "string", "description": "slb name", "minLength": 3, "maxLength": 30,
        #          "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},  # 只含有数字、字母、下划线不能以下划线开头和结尾
    },
    # 必要字段
    "required": ["server_ip"],
    "oneOf": [
        {
            "required": [
                "mqc_new"
            ]
        },
        {
            "required": [
                "mqc_edit"
            ]
        },
        {
            "required": [
                "mqc_del"
            ]
        }
    ]
}

if __name__ == '__main__':
    import json

    print(json.dumps(qos_access_schema))
