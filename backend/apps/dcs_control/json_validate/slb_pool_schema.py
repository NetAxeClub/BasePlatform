# -*- coding: utf-8 -*-
# @Time    : 2021/10/27 16:47
# @Author  : LiJiaMin
# @Site    : 
# @File    : slb_pool_schema.py
# @Software: PyCharm
"""
有一个小功能待完善，就是对象中，ip和range不能实现联动检查，
比如ip就必须符合ip的正则，range就必须对应range的正则，现在两个是并行检查的，可能会出现ip类型的range写法通过验证
考虑anyOf验证
"""
post_slb_pool_schema = {
    "definitions": {
        "add_object": {
            "type": "boolean", "enum": [True]
        },
        "del_object": {
            "type": "boolean", "enum": [True]
        },
        "edit_object": {
            "type": "boolean", "enum": [True]
        },
    },
    "dependencies": {
        "add_object": ["load_balance", "monitor", "monitor_threshold", "objects"],
        "edit_object": ["load_balance", "monitor", "monitor_threshold", "objects"],
        "del_object": [],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "post_slb_pool",
    "type": "object",
    "properties": {
        "add_object": {
            "$ref": "#/definitions/add_object"
        },
        "del_object": {
            "$ref": "#/definitions/del_object"
        },
        "edit_object": {
            "$ref": "#/definitions/edit_object"
        },
        "hostid": {"type": "integer"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "name": {"type": "string", "description": "slb name", "minLength": 3, "maxLength": 30,
                 "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},  # 只含有数字、字母、下划线不能以下划线开头和结尾
        "description": {"type": "string"},
        "load_balance": {"type": "string",
                         "pattern": "^(weighted-hash|weighted-round-robin(\ssticky)?|weighted-least-connection(\ssticky)?)"},
        "monitor": {"type": "string", "enum": ["track-ping", "track-tcp"]},
        "monitor_threshold": {"type": "integer", "minimum": 1, "maximum": 255, "default": 3},
        "objects": {
            "type": "array",
            "items":
                {
                    "definitions": {
                        "add_detail_ip": {
                            "type": "boolean", "enum": [True]
                        },
                        "add_detail_range": {
                            "type": "boolean", "enum": [True]
                        },
                        "del_detail_ip": {
                            "type": "boolean", "enum": [True]
                        },
                        "del_detail_range": {
                            "type": "boolean", "enum": [True]
                        },
                    },
                    "additionalProperties": False,
                    "dependencies": {
                        "add_detail_ip": ["ip_mask", "port", "weight"],
                        "del_detail_ip": ["ip_mask", "port"],
                        "add_detail_range": ["range_start", "range_end", "port", "weight"],
                        "del_detail_range": ["range_start", "range_end", "port"]
                    },
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "slb_pool_sub",
                    "type": "object",
                    "description": "具体操作内容",
                    "properties": {
                        "add_detail_ip": {
                            "$ref": "#/properties/objects/items/definitions/add_detail_ip"
                        },
                        "del_detail_ip": {
                            "$ref": "#/properties/objects/items/definitions/del_detail_ip"
                        },
                        "add_detail_range": {
                            "$ref": "#/properties/objects/items/definitions/add_detail_range"
                        },
                        "del_detail_range": {
                            "$ref": "#/properties/objects/items/definitions/del_detail_range"
                        },
                        "ip_mask": {
                            "type": "array",
                            "additionalProperties": False,
                            "items": [
                                {
                                    "type": "string",
                                    "pattern": "\d+.\d+.\d+.\d+/\d{1,2}"
                                },
                            ],
                            "miniItems": 1,
                            "maxItems": 10,
                            "uniqueItems": True
                        },
                        "range_start": {
                            "type": "string",
                            "pattern": "^\d+.\d+.\d+.\d{1,3}$"
                        },
                        "range_end": {
                            "type": "string",
                            "pattern": "^\d+.\d+.\d+.\d{1,3}$"
                        },
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "weight": {"type": "integer", "minimum": 1, "maximum": 255, "default": 1},
                        "max_connection": {"type": "integer", "minimum": 0, "maximum": 1000000000, "default": 0},
                    },
                    "oneOf": [
                        {
                            "required": [
                                "add_detail_ip"
                            ]
                        },
                        {
                            "required": [
                                "del_detail_ip"
                            ]
                        },
                        {
                            "required": [
                                "add_detail_range"
                            ]
                        },
                        {
                            "required": [
                                "del_detail_range"
                            ]
                        }
                    ]
                },
            "miniItems": 1,
            "maxItems": 5,
            "uniqueItems": True
        },
    },
    "required": ["hostip", "hostid", "vendor", "name"],
    "oneOf": [
        {
            "required": [
                "add_object"
            ]
        },
        {
            "required": [
                "del_object"
            ]
        },
        {
            "required": [
                "edit_object"
            ]
        }
    ]
}

if __name__ == '__main__':
    import json

    print(json.dumps(post_slb_pool_schema))
