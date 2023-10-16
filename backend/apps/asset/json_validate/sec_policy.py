# -*- coding: utf-8 -*-
# @Time    : 2021/10/27 16:47
# @Author  : LiJiaMin
# @Site    :
# @File    : slb_pool_schema.py
# @Software: PyCharm
"""

"""
sec_policy_schema = {
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
        "add_object": ["hostip", "hostid", "vendor", "from", "to", "name", "action", "from_addr", "to_addr"],
        "edit_object": ["hostip", "id", "hostid", "vendor", "from", "to", "name", "action", "from_addr",
                        "to_addr"],
        "del_object": ["hostip", "id", "hostid", "vendor", "name"],
        "sort_object": ["hostip", "id", "hostid", "insert", "name"],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "post_sec_policy",
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
        "sort_object": {
            "$ref": "#/definitions/sort_object"
        },
        "hostid": {"type": "integer"},
        "id": {"type": "string", "pattern": "^\d+"},
        "name": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$"},
        "description": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$"},
        "insert": {"type": "string", "pattern": "^(before\s\d|after\s\d|top)"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "vrf": {"type": "string", "description": "vpn实例"},
        "action": {"type": "string", "description": "动作", "enum": ["permit", "deny"]},
        "service": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string", "pattern": "^[\u4e00-\u9fa5a-zA-Z][\u4e00-\u9fa5a-zA-Z0-9_]*$"
                        }
                    ]
                },
                "multi": {
                    "type": "array",
                    "items": [
                        {
                            "type": "object",
                            "properties": {
                                "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                                "start_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                                "end_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                            },
                            "oneOf": [{"required": ["protocol", "start_port", "end_port"]}]
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
                }
            ]
        },
        "log": {"type": "boolean", "default": False},
        "counting": {"type": "boolean", "default": False},
        "from_addr": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string", "pattern": "^\S+"
                        }
                    ]
                },
                "iplist": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string", "pattern": "^\S+"
                        }
                    ]
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
                        "iplist"
                    ]
                },
            ]
        },
        "from": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string", "pattern": "^\S+"
                }
            },
            "oneOf": [
                {
                    "required": [
                        "zone"
                    ]
                }
            ]
        },
        "to_addr": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string", "pattern": "^\S+"
                        }
                    ]
                },
                "iplist": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string", "pattern": "^\S+"
                        }
                    ]
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
                        "iplist"
                    ]
                },
            ]
        },
        # 目的域
        "to": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "pattern": "^\S+"
                },

            },
            "oneOf": [
                {
                    "required": [
                        "zone"
                    ]
                }
            ]
        },

    }
}

if __name__ == '__main__':
    import json

    print(json.dumps(sec_policy_schema))
