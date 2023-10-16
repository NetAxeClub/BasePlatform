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

deny_schema = {
    "definitions": {
        "add_detail_ip": {
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
        "del_detail_exclude_ip": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_range": {
            "type": "boolean", "enum": [True]
        },
        "del_detail_exclude_range": {
            "type": "boolean", "enum": [True]
        },
    },
    "dependencies": {
        "add_detail_ip": [
            "ip_mask", "inventory_id",
        ],
        "add_detail_exclude_ip": [
             "ip_mask", "inventory_id",
        ],
        "add_detail_range": [
            "range_start",
            "range_end", "inventory_id"
        ],
        "add_detail_exclude_range": [
            "range_start",
            "range_end", "inventory_id"
        ],
        "del_detail_ip": [
            "ip_mask", "inventory_id"
        ],
        "del_detail_range": [
            "range_start",
            "range_end", "inventory_id"
        ],
        "del_detail_exclude_ip": [
            "ip_mask", "inventory_id"
        ],
        "del_detail_exclude_range": [
            "range_start",
            "range_end", "inventory_id"
        ],
    },
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/root.json",
    "type": "object",
    "required": ["inventory_id"],
    "properties": {
        "inventory_id": {"type": "integer"},
        "add_detail_ip": {
            "$ref": "#/definitions/add_detail_ip"
        },
        "add_detail_exclude_ip": {
            "$ref": "#/definitions/add_detail_exclude_ip"
        },
        "del_detail_ip": {
            "$ref": "#/definitions/del_detail_ip"
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
                "add_detail_ip"
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
    print(json.dumps(deny_schema))