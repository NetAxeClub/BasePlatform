# -*- coding: utf-8 -*-
# @Time    : 2021/10/14 11:04
# @Author  : LiJiaMin
# @Site    : 
# @File    : hillstone_address_schema.py
# @Software: PyCharm
# hillstone 地址对象 解决多样性匹配的问题

"""
已知问题：
1.
"""
service_schema = {
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
        "add_object": ["objects"],
        "edit_object": ["objects"],
        "del_object": [],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "service_schema",
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
        "objects": {
            "type": "array",
            "items":
                {
                    "definitions": {
                        "add_detail": {
                            "type": "boolean", "enum": [True]
                        },
                        "del_detail": {
                            "type": "boolean", "enum": [True]
                        },
                    },
                    "additionalProperties": False,
                    "dependencies": {
                        "add_detail": ["start_dst_port", "end_dst_port"],
                        "del_detail": ["start_dst_port", "end_dst_port"],
                    },
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "service_sub",
                    "type": "object",
                    "description": "具体操作内容",
                    "properties": {
                        "add_detail": {
                            "$ref": "#/properties/objects/items/definitions/add_detail"
                        },
                        "del_detail": {
                            "$ref": "#/properties/objects/items/definitions/del_detail"
                        },
                        "ID": {"type": "string", "description": "华三ID", "pattern": "^\d+$"},
                        "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                        "start_src_port": {"type": "integer", "minimum": 0, "maximum": 65535, "default": 0},
                        "end_src_port": {"type": "integer", "minimum": 0, "maximum": 65535, "default": 65535},
                        "start_dst_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                        "end_dst_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                    },
                    "oneOf": [
                        {
                            "required": [
                                "add_detail"
                            ]
                        },
                        {
                            "required": [
                                "del_detail"
                            ]
                        }
                    ]
                },
            "miniItems": 1,
            "maxItems": 40,
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
    print(json.dumps(service_schema))