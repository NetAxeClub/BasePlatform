# -*- coding: utf-8 -*-
# @Time    : 2021/10/27 16:47
# @Author  : LiJiaMin
# @Site    :
# @File    : slb_pool_schema.py
# @Software: PyCharm
"""

"""
post_snat_schema = {
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
        "sort_object": {
            "type": "boolean", "enum": [True]
        },
    },
    "dependencies": {
        "add_object": ["hostip", "hostid", "vendor", "service", "trans_to", "name", "nat_mode", "ingress", "egress"],
        "edit_object": ["hostip", "id", "hostid", "vendor", "service", "trans_to", "name", "nat_mode", "ingress",
                        "egress"],
        "del_object": ["hostip", "id", "hostid", "vendor", "name"],
        "sort_object": ["hostip", "id", "hostid", "insert", "name"],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "post_dnat",
    "type": "object",
    "required": ["name", "hostip", "vendor", "hostid"],
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
        "sort_object": {
            "$ref": "#/definitions/sort_object"
        },
        "hostid": {"type": "integer"},
        "id": {"type": "string", "pattern": "^\d+"},
        "name": {"type": "string", "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},
        "description": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$"},
        "insert": {"type": "string", "pattern": "^(before\s\d|after\s\d|top)"},
        "ingress": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["interface", "zone"]},
                "name": {"type": "string", "pattern": "^\S+"}
            }
        },
        "egress": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["interface", "zone"]},
                "name": {"type": "string", "pattern": "^\S+"}
            }
        },
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "nat_mode": {"type": "string", "enum": ["static", "dynamicip", "dynamicport", "dynamicport sticky"]},
        "disable": {"type": "boolean"},
        "service": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "pattern": "^\S+"},
                "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                "start_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                "end_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                "multi": {
                    "type": "array",
                    "items": [
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "pattern": "^\S+"},
                                "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                                "start_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                                "end_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                            },
                            "oneOf": [
                                {"required": ["protocol", "start_port", "end_port"]},
                                {"required": ["name"]},
                            ]
                        },
                    ],
                    # 待校验JSON数组第一个元素是string类型，且可接受的最短长度为5个字符，第二个元素是number类型，且可接受的最小值为10
                    # 剩余的其他元素是string类型，且可接受的最短长度为2。
                    # 至少一个
                    "miniItems": 1,
                    # 最多5个
                    "maxItems": 10,
                    # 值为true时，所有元素都具有唯一性时，才能通过校验。
                    "uniqueItems": True
                },
            },
            "oneOf": [
                {
                    "required": [
                        "name"
                    ]
                },
                {
                    "required": [
                        "multi"
                    ]
                },
                {
                    "required": [
                        "protocol", "start_port", "end_port"
                    ]
                }
            ]
        },
        "track_tcp": {"type": "integer", "minimum": 0, "maximum": 65535},
        "track_ping": {"type": "boolean", "default": False},
        "log": {"type": "boolean", "default": False},
        # 内网地址
        "from": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "string", "pattern": "^\S+"
                },
                "ip": {
                    "type": "string",
                    "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"
                },
                "any": {"type": "boolean", "enum": [True]}
            },
            "oneOf": [
                {
                    "required": [
                        "object"
                    ]
                },
                {
                    "required": [
                        "ip"
                    ]
                },
                {
                    "required": [
                        "any"
                    ]
                }
            ]
        },
        "to": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "string",
                    "pattern": "^\S+"
                },
                "ip": {
                    "type": "string",
                    "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"
                },
            },
            "oneOf": [
                {
                    "required": [
                        "object"
                    ]
                },
                {
                    "required": [
                        "ip"
                    ]
                }
            ]
        },
        # 转换为公网出口地址
        "trans_to": {
            "type": "object",
            "description": "转换到",
            "properties": {
                "address_book": {
                    "type": "string",
                    "pattern": "^\S+"
                },
                "eif_ip": {
                    "type": "string",
                    "pattern": ""
                },
                "ip": {
                    "type": "string",
                    "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"
                }
            },
            "oneOf": [
                {
                    "required": [
                        "address_book"
                    ]
                },
                {
                    "required": [
                        "eif_ip"
                    ]
                },
                {
                    "required": [
                        "ip"
                    ]
                }
            ]
        },
    },
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
        },
        {
            "required": [
                "sort_object"
            ]
        }
    ]
}

if __name__ == '__main__':
    import json

    print(json.dumps(post_snat_schema))
