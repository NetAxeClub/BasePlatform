# -*- coding: utf-8 -*-
# @Time    : 2021/10/14 11:04
# @Author  : LiJiaMin
# @Site    : 
# @File    : hillstone_address_schema.py
# @Software: PyCharm
# hillstone 地址对象 解决多样性匹配的问题

"""
已知问题：
1. 不能根据厂商名 自定义需要校验的字段，比如操作山石不需要id，而华三需要指定id
"""
address_schema = {
    "definitions": {
        "add_object": {  # 新建对象
            "type": "boolean", "enum": [True]
        },
        "del_object": {  # 删除对象
            "type": "boolean", "enum": [True]
        },
        "add_detail_ip": {  # 新建对象中的条目/成员  新增单个IP
            "type": "boolean", "enum": [True]
        },
        "add_detail_hybrid": {
            "type": "boolean", "enum": [True]
        },
        "add_detail_hostip": {  # 新建对象中的条目/成员 新增单个IP
            "type": "boolean", "enum": [True]
        },
        "add_detail_exclude_ip": {
            "type": "boolean", "enum": [True]
        },
        "add_detail_exclude_range": {
            "type": "boolean", "enum": [True]
        },
        "add_detail_range": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_ip": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_hostip": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_exclude_ip": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_range": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_exclude_range": {
            "type": "boolean", "enum": [True]
        }
    },
    "dependencies": {
        "add_object": ["name", "hostip", "hostid", "vendor"],
        "del_object": ["name", "hostip", "hostid", "vendor"],
        "add_detail_ip": [
            "ip_mask", "name", "hostip", "hostid", "vendor"
        ],
        "add_detail_hybrid": [
            "hybrid", "name", "hostip", "hostid", "vendor"
        ],
        "add_detail_hostip": [
            "hostipv4addr", "name", "hostip", "hostid", "vendor"
        ],
        "add_detail_exclude_ip": [
            "ip_mask", "name", "hostip", "hostid", "vendor"
        ],
        "add_detail_range": [
            "range_start",
            "range_end", "name", "hostip", "hostid", "vendor"
        ],
        "add_detail_exclude_range": [
            "range_start",
            "range_end", "name", "hostip", "hostid", "vendor"
        ],
        "del_detail_ip": [
            "ip_mask", "name", "hostip", "hostid", "vendor"
        ],
        "del_detail_hostip": [
            "hostipv4addr", "name", "hostip", "hostid", "vendor"
        ],
        "del_detail_range": [
            "range_start",
            "range_end", "name", "hostip", "hostid", "vendor"
        ],
        "del_detail_exclude_ip": [
            "ip_mask", "name", "hostip", "hostid", "vendor"
        ],
        "del_detail_exclude_range": [
            "range_start",
            "range_end", "name", "hostip", "hostid", "vendor"
        ],
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/root.json",
    "type": "object",
    "required": ["name", "hostip", "vendor", "hostid"],
    "properties": {
        "name": {"type": "string", "pattern": "^\S+"},
        "description": {"type": "string", "pattern": "^\S+"},
        "hostid": {"type": "integer"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "add_object": {
            "$ref": "#/definitions/add_object"
        },
        "add_detail_hybrid": {
            "$ref": "#/definitions/add_detail_hybrid"
        },
        "del_object": {
            "$ref": "#/definitions/del_object"
        },
        "add_detail_ip": {
            "$ref": "#/definitions/add_detail_ip"
        },
        "add_detail_hostip": {
            "$ref": "#/definitions/add_detail_hostip"
        },
        "add_detail_exclude_ip": {
            "$ref": "#/definitions/add_detail_exclude_ip"
        },
        "del_detail_ip": {
            "$ref": "#/definitions/del_detail_ip"
        },
        "del_detail_hostip": {
            "$ref": "#/definitions/del_detail_hostip"
        },
        "del_detail_exclude_ip": {
            "$ref": "#/definitions/del_detail_exclude_ip"
        },
        "add_detail_range": {
            "$ref": "#/definitions/add_detail_range"
        },
        "add_detail_exclude_range": {
            "$ref": "#/definitions/add_detail_exclude_range"
        },
        "del_detail_range": {
            "$ref": "#/definitions/del_detail_range"
        },
        "del_detail_exclude_range": {
            "$ref": "#/definitions/del_detail_exclude_range"
        },
        "ip_mask": {
            "type": "array",
            "items": [
                {
                    "type": "string",
                    "pattern": "\d+.\d+.\d+.\d+/\d{1,2}"
                },
            ],
            # 待校验JSON数组第一个元素是string类型，且可接受的最短长度为5个字符，第二个元素是number类型，且可接受的最小值为10
            # 剩余的其他元素是string类型，且可接受的最短长度为2。
            # 至少一个
            "miniItems": 1,
            # 最多20个
            "maxItems": 1000,
            # 值为true时，所有元素都具有唯一性时，才能通过校验。
            "uniqueItems": True
        },
        "hybrid": {  # 混合模式，目前仅适配了山石，用于后期做混合模式的适配，支持同时IP/mask和range的列表集合
            "type": "array",
            "items": [
                {
                    "type": "string",
                    "pattern": "(\d+.\d+.\d+.\d+/\d{1,2}|\d+.\d+.\d+.\d+-\d+.\d+.\d+.\d+)"
                },
            ],
            # 待校验JSON数组第一个元素是string类型，且可接受的最短长度为5个字符，第二个元素是number类型，且可接受的最小值为10
            # 剩余的其他元素是string类型，且可接受的最短长度为2。
            # 至少一个
            "miniItems": 1,
            # 最多20个
            "maxItems": 1000,
            # 值为true时，所有元素都具有唯一性时，才能通过校验。
            "uniqueItems": True
        },
        "hostipv4addr": {  # 目前只有华三适配了，主要用于增加主机IP地址
            "type": "array",
            "items": [
                {
                    "type": "string",
                    "pattern": "^\d+.\d+.\d+.\d+$"
                },
            ],
            # 待校验JSON数组第一个元素是string类型，且可接受的最短长度为5个字符，第二个元素是number类型，且可接受的最小值为10
            # 剩余的其他元素是string类型，且可接受的最短长度为2。
            # 至少一个
            "miniItems": 1,
            # 最多5个
            "maxItems": 1000,
            # 值为true时，所有元素都具有唯一性时，才能通过校验。
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
                "add_detail_ip"
            ]
        },
        {
            "required": [
                "add_detail_hostip"
            ]
        },
        {
            "required": [
                "add_detail_exclude_ip"
            ]
        },
        {
            "required": [
                "del_detail_ip"
            ]
        },
        {
            "required": [
                "del_detail_hostip"
            ]
        },
        {
            "required": [
                "del_detail_exclude_ip"
            ]
        },
        {
            "required": [
                "add_detail_range"
            ]
        },
        {
            "required": [
                "add_detail_exclude_range"
            ]
        },
        {
            "required": [
                "del_detail_range"
            ]
        },
        {
            "required": [
                "del_detail_exclude_range"
            ]
        },
    ]
}
if __name__ == '__main__':
    import json
    print(json.dumps(address_schema))