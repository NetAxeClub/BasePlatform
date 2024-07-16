# Create your views here.
import os
import json
from datetime import datetime, date
from rest_framework.views import APIView
from apps.system.tools.plugin_tree import PluginsTree
from django.http import JsonResponse
from netaxe.settings import BASE_DIR
from autopep8 import fix_code, commented_out_code_lines


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


# 插件管理前端页面接口
class PluginMange(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'get_tree' in get_param.keys():
            _tree = PluginsTree()
            _tree.produce_tree()
            data = {
                "code": 200,
                "data": _tree.tree_final,
                "msg": "获取文件树成功"
            }
            return JsonResponse(data)
        if 'filename' in get_param.keys():
            with open(BASE_DIR + '/plugins/extensibles/' + get_param['filename'], "r",
                      encoding="utf-8") as f:
                file_content = f.read()
            data = {
                "code": 200,
                "data": file_content,
                "msg": "获取配置文件内容成功"
            }
            return JsonResponse(data, safe=False)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        if all(k in post_data for k in ("add_fsm_platform", "type")):
            if post_data['type'] == 'file':
                filename = post_data['add_fsm_platform']
                with open(BASE_DIR + '/plugins/extensibles/' + filename, "w",
                          encoding="utf-8") as f:
                    f.write('# -*- coding: utf-8 -*-')
                data = {
                    "code": 200,
                    "data": 'ok',
                    "msg": "新建配置文件内容成功"
                }
                return JsonResponse(data, safe=False)
            else:
                if not os.path.exists(os.path.join(BASE_DIR, 'plugins/extensibles/{}'.format(post_data['add_fsm_platform']))):
                    os.makedirs(os.path.join(BASE_DIR, 'plugins/extensibles/{}'.format(post_data['add_fsm_platform'])))
                data = {
                    "code": 200,
                    "data": 'ok',
                    "msg": "新建目录成功"
                }
                return JsonResponse(data, safe=False)
        if all(k in post_data for k in ("save_fsm_template", "filename")):
            save_fsm_template = post_data['save_fsm_template']
            pep8_content = fix_code(save_fsm_template, options={'aggressive':2})
            with open(BASE_DIR + '/plugins/extensibles/' + post_data['filename'], "w",
                      encoding="utf-8") as f:
                f.write(pep8_content)
            data = {
                "code": 200,
                "data": 'ok',
                "msg": "保存文件成功"
            }
            return JsonResponse(data, safe=False)

        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)