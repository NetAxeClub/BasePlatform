# -*- coding: utf-8 -*-
# @Time    : 2021/8/18 17:03
# @Author  : LiJiaMin
# @Site    :
# @File    : jsonschema.py
# @Software: PyCharm
import json

from django.http import JsonResponse

from jsonschema import ValidationError, validate


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
                return JsonResponse(invalid_json(e.path, e.message), safe=False)
            else:
                return func(self, request, *args, **kwargs)

        return _func

    return valieated_func
