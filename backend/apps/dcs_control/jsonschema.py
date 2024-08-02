# -*- coding: utf-8 -*-
# @Time    : 2021/8/18 17:03
# @Author  : LiJiaMin
# @Site    : 
# @File    : jsonschema.py
# @Software: PyCharm
import json

from django.http import JsonResponse

from jsonschema import ValidationError, validate

# slb验证
"""
有一个小功能待完善，就是对象中，ip和range不能实现联动检查，
比如ip就必须符合ip的正则，range就必须对应range的正则，现在两个是并行检查的，可能会出现ip类型的range写法通过验证
考虑anyOf验证
"""
post_slb_pool_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "get_slb_pool",
    "type": "object",
    "properties": {
        # "author": {"type": "string", "pattern": "\S+"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "slb_name": {"type": "string", "description": "slb name", "minLength": 3, "maxLength": 30,
                     "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},  # 只含有数字、字母、下划线不能以下划线开头和结尾
        "description": {"type": "string"},
        "load_balance": {"type": "string",
                         "pattern": "^(weighted-hash|weighted-round-robin(\ssticky)?|weighted-least-connection(\ssticky)?)"},
        "monitor": {"type": "string", "enum": ["track-ping", "track-tcp", "track-udp"]},
        "monitor_threshold": {"type": "integer", "minimum": 1, "maximum": 255},
        "objects": {
            "type": "array",
            "items": [
                {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "slb_pool_sub",
                    "type": "object",
                    "description": "具体操作内容",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "pattern": "\d+.\d+.\d+.\d+/\d{1,2}|\d+.\d+.\d+.\d+\s+\d+.\d+.\d+.\d+"
                        },
                        "type": {
                            "type": "string", "enum": ["ip", "ip-range"]
                        },
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "weight": {"type": "integer", "minimum": 1, "maximum": 255},
                        "max_connection": {"type": "integer", "minimum": 1, "maximum": 1000000000},
                    },
                    "required": ["ip", "type", "weight", "max_connection"]
                },
            ],
            # 待校验JSON数组第一个元素是string类型，且可接受的最短长度为5个字符，第二个元素是number类型，且可接受的最小值为10
            # 剩余的其他元素是string类型，且可接受的最短长度为2。
            # 至少一个
            "miniItems": 1,
            # 最多5个
            "maxItems": 5,
            # 值为true时，所有元素都具有唯一性时，才能通过校验。
            "uniqueItems": True
        },
    },
    "required": ["hostip", "vendor", "objects", "slb_name", "monitor", "load_balance"]
}

# DNAT验证
post_dnat_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    # "$schema": "http://json-schema.org/draft/2020-12/schema",
    "title": "get_slb_pool",
    "type": "object",
    "properties": {
        "author": {"type": "string", "pattern": "^(?!_)(?!.*?_$)[a-zA-Z0-9_]+$"},
        "id": {"type": "string", "pattern": "^\d+"},
        "name": {"type": "string", "pattern": "^\S+"},
        "description": {"type": "string", "pattern": "^\S+"},
        "insert": {"type": "string", "pattern": "^(before\s\d|after\s\d|top)"},
        "hostip": {"type": "string", "description": "设备IP",
                   "pattern": "^((25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d)))"},
        "vendor": {"type": "string", "description": "设备品牌", "enum": ["Hillstone", "H3C", "Huawei"]},
        "service": {"type": "string", "description": "服务对象"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "track_tcp": {"type": "integer", "minimum": 1, "maximum": 65535},
        "track_ping": {"type": "boolean"},
        "log": {"type": "boolean"},
        "load_balance": {"type": "boolean"},
        "from": {
            "type": "object",
            "properties": {
                "object": {
                    "type": "string",
                    "pattern": "^\S+"
                },
                "ip": {
                    "type": "string", "pattern": "\d+.\d+.\d+.\d+/\d{1,2}"
                }
            }
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
                    "type": "string", "pattern": "(\d+.\d+.\d+.\d+/\d{1,2}|\d+.\d+.\d+.\d+/)"
                }
            }
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
                    "type": "string", "pattern": "\d+.\d+.\d+.\d+"
                }
            }

        },
    },
    "required": ["author", "hostip", "vendor", "service", "from", "to", "trans_to"]
}


def invalid_json(path=None, message=None):
    result = {
        'code': 400,
        'data': ' --> '.join([str(i) for i in path]),
        'message': message if message else 'Invalid JSON'
    }
    return result


# 适用于一个view下多个json校验
def single_json_validate(json_data, schema):
    try:
        validate(json_data, schema)
        return True, {}
    except ValidationError as e:
        return False, invalid_json(e.path, e.message)


def json_validate(schema):
    def valieated_func(func):
        def _func(self, request, *args, **kwargs):
            try:
                if not request.body:
                    return JsonResponse(invalid_json(), safe=False)
                else:
                    validate(json.loads(request.body), schema)
            except ValidationError as e:
                """
                ValidationError 的示例返回，通过e.args  e.instance  e.message来调用
                args ("'hostip' is a required property", <unset>, (), None, (), <unset>, <unset>, <unset>, (), None)
                context []
                instance {'vendor': 'hillstone'}
                schema {'$schema': 'http://json-schema.org/draft-07/schema#', 'title': 'get_slb_pool', 'type': 'object', 'properties': {'hostip': {'type': 'string'}, 'vendor': {'type': 'string'}}, 'required': ['hostip', 'vendor']}
                message 'hostip' is a required property
                """
                print(e.path)
                # return JsonResponse(invalid_json(e.instance, e.message), safe=False)
                return JsonResponse(invalid_json(e.path, e.message), safe=False)
            else:
                return func(self, request, *args, **kwargs)

        return _func

    return valieated_func
