# -*- coding: utf-8 -*-
# @Time    : 2021/10/27 16:47
# @Author  : LiJiaMin
# @Site    :
# @File    : slb_pool_schema.py
# @Software: PyCharm
"""

"""
post_dnat_schema = {
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
        "add_object": ["hostip", "hostid", "vendor", "service", "from", "to", "trans_to", "name"],
        "edit_object": ["hostip", "id", "hostid", "vendor", "service", "from", "to", "trans_to", "name"],
        "del_object": ["hostip", "id", "hostid", "vendor", "name"],
        "sort_object": ["hostip", "id", "hostid", "insert", "name"],
        "additionalProperties": False,
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "post_dnat",
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
        "name": {"type": "string", "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},
        "description": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$"},
        "insert": {"type": "string", "pattern": "^(before\s\d|after\s\d|top)"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "service": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string", "pattern": "^\S+"
                },
                "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                "start_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                "end_port": {"type": "integer", "minimum": 0, "maximum": 65535},
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
                },
                {
                    "required": [
                        "protocol", "start_port", "end_port"
                    ]
                }
            ]
        },
        "port": {"type": "integer", "minimum": 0, "maximum": 65535},
        "track_tcp": {"type": "integer", "minimum": 0, "maximum": 65535},
        "track_ping": {"type": "boolean", "default": False},
        "log": {"type": "boolean", "default": False},
        "load_balance": {"type": "boolean", "default": False},
        "from": {
            "type": "object",
            "properties": {
                "address_book": {
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
                        "address_book"
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
        # 公网地址
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
                }
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
        # 转换为内网
        "trans_to": {
            "type": "object",
            "description": "转换到",
            "properties": {
                "address_book": {
                    "type": "string",
                    "pattern": "^\S+"
                },
                "slb_server_pool": {
                    "type": "string",
                    "pattern": "^\S+"
                },
                "ip": {
                    "type": "string",
                    "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))$"
                },
                "custom_slb": {
                    "type": "array",
                    "items": [
                        {
                            "type": "object",
                            "properties": {
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
                                "protocol": {"type": "string", "description": "协议", "enum": ["TCP", "UDP", "ICMP"]},
                                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                                "weight": {"type": "integer", "minimum": 1, "maximum": 255, "default": 1},
                                "max_connection": {"type": "integer", "minimum": 0, "maximum": 1000000000,
                                                   "default": 65535},
                            },
                            "oneOf": [
                                {
                                    "required": [
                                        "ip_mask", "port", "protocol"
                                    ]
                                },
                                {
                                    "required": [
                                        "range_start", "range_end", "port", "protocol"
                                    ]
                                },
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
                        "custom_slb"
                    ]
                },
                {
                    "required": [
                        "address_book"
                    ]
                },
                {
                    "required": [
                        "ip"
                    ]
                },
                {
                    "required": [
                        "slb_server_pool"
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

    print(json.dumps(post_dnat_schema))
