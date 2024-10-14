# Create your views here.
import json
import re
import yaml
import io
import django_filters
from jinja2 import Environment, StrictUndefined, exceptions
from datetime import date, datetime
from django.http import JsonResponse, StreamingHttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.views import APIView
from ttp import ttp
from netaxe.settings import BASE_DIR
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.api.tools.custom_viewset_base import CustomViewBase
from utils.connect_layer.auto_main import BatManMain
from apps.config_center.config_parse.config_parse import ConfigTree, FSMTree
from apps.config_center.git_tools.git_proc import ConfigGit
from utils.db.mongo_ops import MongoNetOps
from .serializers import *

_ConfigGit = ConfigGit()


def is_safe_dict(data: dict) -> bool:
    # 定义危险字符的正则表达式
    pattern = re.compile(
        r'<(script|iframe).*?>|([^\w\s./:%,-])', re.IGNORECASE)

    # 遍历字典中的值，使用正则表达式进行匹配验证
    for value in data.values():
        if isinstance(value, str) and pattern.search(value):
            return False

    return True


def jinja_render(data, template):
    """ Render a jinja template
    """
    if is_safe_dict(data):
        env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)

        try:
            jinja2_tpl = env.from_string(template)
            rendered_jinja2_tpl = jinja2_tpl.render(data)
        except (exceptions.TemplateSyntaxError, exceptions.TemplateError) as e:
            return False, "Syntax error in jinja2 template: {0}".format(e)
        except (exceptions.TemplateRuntimeError, ValueError, TypeError) as e:
            return False, "Error in your values input filed: {0}".format(e)

        return True, rendered_jinja2_tpl
    return False, "安全校验失败"


class ConfigBackupFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = ConfigBackup
        fields = '__all__'


# 配置备份
class ConfigBackupViewSet(CustomViewBase):
    queryset = ConfigBackup.objects.all().order_by('-id')
    serializer_class = ConfigBackupSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    filterset_class = ConfigBackupFilter
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('manage_ip', 'name')
    search_fields = ('manage_ip', 'name')

    def get_queryset(self):
        """
        expires  比 expire多一个s ，用来筛选已过期的设备数据 lt 小于  gt 大于  lte小于等于  gte 大于等于
        :return:
        """
        range_time = self.request.query_params.get('range_time', None)
        if range_time is not None:
            dt_object = datetime.fromtimestamp(int(int(range_time)/1000))
            start_date = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            end_data = dt_object.strftime('%Y-%m-%d ') + "23:59:59"
            self.queryset = self.queryset.filter(last_time__range=(
                datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S'),
                datetime.strptime(end_data, '%Y-%m-%d %H:%M:%S')))
        return self.queryset


# 配置合规表
class ConfigComplianceViewSet(CustomViewBase):
    queryset = ConfigCompliance.objects.all().order_by('-id')
    serializer_class = ConfigComplianceSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    search_fields = 'name'


class ConfigComplianceResultViewSet(CustomViewBase):
    queryset = ConfigComplianceResult.objects.all().order_by('-id')
    serializer_class = ConfigComplianceResultSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    search_fields = ('manage_ip', 'hostname', 'rule')


# 配置模板表
class ConfigTemplateViewSet(CustomViewBase):
    """
    配置合规表--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ConfigTemplate.objects.all().order_by('-id')
    serializer_class = ConfigTemplateSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    # pagination_class = LimitSet
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = PublicNetFinalFilter
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    search_fields = 'name'


# TTP模板表
class TTPTemplateViewSet(CustomViewBase):
    """
    配置合规表--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = TTPTemplate.objects.all().order_by('-id')
    serializer_class = TTPTemplateSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    # pagination_class = LimitSet
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = PublicNetFinalFilter
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    search_fields = 'name'


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


class GitConfig(APIView):
    permission_classes = ()
    authentication_classes = ()
    # permission_classes = (IsAuthenticated,)

    # authentication_classes = (JWTAuthentication, SessionAuthentication)

    def get(self, request):
        """

        :param request:
        :return:
        """
        get_param = request.GET.dict()
        # print('get_param', get_param)
        if 'get_hostip' in get_param.keys():
            _tree = ConfigTree()
            _tree.produce_tree()
            res = _tree.tree_final
            host_list = [x for x in res[0]['children']]
            if host_list:
                data = {
                    "code": 200,
                    "data": host_list,
                    "msg": "成功"
                }
                return JsonResponse(data)
            else:
                data = {
                    "code": 400,
                    "data": {},
                    "msg": "没有获取到git配置文件目录的设备IP列表"
                }
                return JsonResponse(data)

        if 'get_tree' in get_param.keys():
            _tree = ConfigTree()
            _tree.produce_tree()
            data = {
                "code": 200,
                "data": _tree.tree_final,
                "msg": "获取配置文件树成功"
            }
            return JsonResponse(data)
        if 'filename' in get_param.keys():
            with open(BASE_DIR + '/media/device_config/' + get_param['filename'], "r") as f:
                file_content = f.read()
                data = {
                    "code": 200,
                    "data": file_content,
                    "msg": "获取配置文件内容成功"
                }
                return JsonResponse(data, safe=False)
        if 'get_commit' in get_param.keys():
            res = _ConfigGit.get_commit()
            # print(res)
            data = {
                "code": 200,
                "data": res,
                "msg": "获取commit记录成功"
            }
            return JsonResponse(data, safe=False)
        if 'commit_detail' in get_param.keys():
            res = _ConfigGit.get_commit_detail(get_param['commit_detail'])
            data = {
                "code": 200,
                "data": res,
                "msg": "获取commit轨迹成功"
            }
            return JsonResponse(data, safe=False)
        if all(k in get_param for k in ("file", "from_commit", "to_commit")):
            res = _ConfigGit.get_commit_by_file_new(**get_param)
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        # 获取单个文件指定commit下的变更信息
        if all(k in get_param for k in ("file", "single_commit")):
            res = _ConfigGit.get_commit_modified_by_filename(get_param['single_commit'], get_param['file'])
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        # 获取单个文件指定commit下的原始文件内容
        if all(k in get_param for k in ("file", "single_commit_real_content")):
            res = _ConfigGit.get_commit_file_content(get_param['single_commit_real_content'], get_param['file'])
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ComplianceResults(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'get_results' in get_param.keys():
            _res = MongoNetOps.compliance_result()
            data = {
                "code": 200,
                "data": _res,
                "msg": "获取合规检查结果成功"
            }
            return JsonResponse(data, encoder=DateEncoder)
        if any(k in get_param for k in ("rule", "compliance")):
            _res = MongoNetOps.compliance_result(**{k: v for k, v in get_param.items() if v != ''})
            data = {
                "code": 200,
                "data": _res,
                "msg": "获取合规检查结果成功"
            }
            return JsonResponse(data, encoder=DateEncoder)


class RegexTest(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)

    def post(self, request):
        post_data = request.data
        if any(k in post_data for k in ("content", "regex")):
            _regex = post_data['regex']
            content = post_data['content']  # match-compliance  mismatch-compliance
            _res = re.compile(pattern=_regex, flags=re.M).findall(string=content)
            data = {
                "code": 200,
                "data": _res,
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)


# TTP 前端页面接口
class TTPParse(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        pass

    def post(self, request):
        post_data = request.data
        if any(k in post_data for k in ("test_content", "ttp_template")):
            data_to_parse = post_data['test_content']
            ttp_template = post_data['ttp_template']
            parser = ttp(data=data_to_parse, template=ttp_template)
            parser.parse()
            # print result in JSON format
            results = parser.result(format='json')[0]
            _res = ''
            data = {
                "code": 200,
                "data": results,
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)


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


class Jinja2View(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        # jinja2渲染结果
        if all(k in post_data for k in ("render", "yaml_content", "jinja2_content")):
            yaml_content = post_data['yaml_content']
            yaml_res = yaml.safe_load(yaml_content)
            data_to_parse = post_data['jinja2_content']
            success, render_res = jinja_render(yaml_res, data_to_parse)
            data = {
                "code": 200 if success else 400,
                "results": [
                    {
                        'yaml_res': yaml_res,
                        'render_res': render_res,
                    }
                ],
                "message": "解析成功"
            }
            return JsonResponse(data)

        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ConfigFileView(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_params = request.GET.dict()
        if 'file_path' in get_params.keys():
            res = _ConfigGit.get_file_all_change_commmit(file_path=get_params['file_path'])
            data = {
                "code": 200,
                "results": res,
                "message": "获取成功"
            }
            return JsonResponse(data)
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        get_file_commit = _ConfigGit.get_file_content_by_commit(post_data['file_path'], post_data["commit"])
        if get_file_commit:
            data = {
                "code": 200,
                "results": get_file_commit,
                "message": "success"
            }
            return JsonResponse(data)
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ConfigFileListView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        get_file_commit = _ConfigGit.get_file_content_by_commit(get_param['file_path'], get_param["commit"])
        if get_file_commit:
            file_stream = io.BytesIO(bytes(get_file_commit.encode()))
            # 设置HTTP响应头
            response = StreamingHttpResponse(file_stream, content_type='application/octet-stream')
            response['Content-Disposition'] = f"attachment; filename={get_param['file_path'].split('/')[-1]}"
            return response
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)