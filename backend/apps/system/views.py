# Create your views here.
from rest_framework.views import APIView
from datetime import date, datetime
from django.http import JsonResponse
from netaxe.settings import BASE_DIR

# TextFSM 前端页面接口
class TextFSMParse(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'get_tree' in get_param.keys():
            _tree = FSMTree()
            _tree.produce_tree()
            data = {
                "code": 200,
                "data": _tree.tree_final,
                "msg": "获取文件树成功"
            }
            return JsonResponse(data)
        if 'filename' in get_param.keys():
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + get_param['filename'], "r",
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
        if 'add_fsm_platform' in post_data.keys():
            filename = post_data['add_fsm_platform']
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + filename, "w",
                      encoding="utf-8") as f:
                f.write('')
            data = {
                "code": 200,
                "data": 'ok',
                "msg": "新建配置文件内容成功"
            }
            return JsonResponse(data, safe=False)
        if any(k in post_data for k in ("save_fsm_template", "filename")):
            save_fsm_template = post_data['save_fsm_template']
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + post_data['filename'], "w",
                      encoding="utf-8") as f:
                f.write(save_fsm_template)
            data = {
                "code": 200,
                "data": 'ok',
                "msg": "保存配置文件内容成功"
            }
            return JsonResponse(data, safe=False)

        if any(k in post_data for k in ("test_content", "fsm_platform")):
            data_to_parse = post_data['test_content']
            fsm_platform = post_data['fsm_platform']
            res = BatManMain.test_fsm(content=data_to_parse, template=fsm_platform)
            data = {
                "code": 200,
                "data": json.dumps(res),
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)

        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)