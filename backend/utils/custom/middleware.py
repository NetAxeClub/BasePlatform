"""
日志 django中间件
"""
import json
import logging
from urllib import parse

import requests
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from apps.system.models import OperationLog
from confload.confload import config
from utils.custom.request_util import get_request_user, get_request_ip, get_request_data, get_request_path, get_os, \
    get_browser, get_verbose_name

logger = logging.getLogger('websocket')


class ApiLoggingMiddleware(MiddlewareMixin):
    """
    用于记录API访问日志中间件
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.enable = getattr(settings, 'API_LOG_ENABLE', None) or False
        self.methods = getattr(settings, 'API_LOG_METHODS', None) or set()
        self.operation_log_id = None

    @classmethod
    def __handle_request(cls, request):
        request.request_ip = get_request_ip(request)
        request.request_data = get_request_data(request)
        request.request_path = get_request_path(request)

    def __handle_response(self, request, response):
        # request_data,request_ip由PermissionInterfaceMiddleware中间件中添加的属性
        body = getattr(request, 'request_data', {})
        # 请求含有password则用*替换掉(暂时先用于所有接口的password请求参数)
        if isinstance(body, dict) and body.get('password', ''):
            body['password'] = '*' * len(body['password'])
        if not hasattr(response, 'data') or not isinstance(response.data, dict):
            response.data = {}
        try:
            if not response.data and response.content:
                content = json.loads(response.content.decode())
                response.data = content if isinstance(content, dict) else {}
        except Exception:
            return
        user = get_request_user(request)
        info = {
            'request_ip': getattr(request, 'request_ip', 'unknown'),
            'creator': user if not isinstance(user, AnonymousUser) else None,
            'dept_belong_id': getattr(request.user, 'dept_id', None),
            'request_method': request.method,
            'request_path': request.request_path,
            'request_body': body,
            'response_code': response.data.get('code'),
            'request_os': get_os(request),
            'request_browser': get_browser(request),
            'request_msg': request.session.get('request_msg'),
            'status': True if response.data.get('code') in [200, ] else False,
            'json_result': {"code": response.data.get('code'), "msg": response.data.get('msg')},
        }
        operation_log, creat = OperationLog.objects.update_or_create(defaults=info, id=self.operation_log_id)
        if not operation_log.request_modular and settings.API_MODEL_MAP.get(request.request_path, None):
            operation_log.request_modular = settings.API_MODEL_MAP[request.request_path]
            operation_log.save()

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'cls') and hasattr(view_func.cls, 'queryset'):
            if self.enable:
                if self.methods == 'ALL' or request.method in self.methods:
                    log = OperationLog(request_modular=get_verbose_name(view_func.cls.queryset))
                    log.save()
                    self.operation_log_id = log.id

        return

    def process_request(self, request):
        self.__handle_request(request)

    def process_response(self, request, response):
        """
        主要请求处理完之后记录
        :param request:
        :param response:
        :return:
        """
        if self.enable:
            if self.methods == 'ALL' or request.method in self.methods:
                self.__handle_response(request, response)
        return response


class UserData(object):
    is_authenticated = True
    is_anonymous = False

    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])


def get_auth_user(token):
    rbac_instance = config.service_dicovery('rbac')
    # print(rbac_instance)
    if rbac_instance.status_code == 200:
        rbac_res = rbac_instance.json()
        # print(rbac_res)
        auth_service_url = "http://{}:{}".format(rbac_res['hosts'][0]['ip'], rbac_res['hosts'][0]['port'])
        auth_decode_url = f'{auth_service_url}/rbac/userinfo'
        headers = {'Accept': 'application/json', 'Authorization': f'{str(token)}',
                   'Content-Type': 'application/json'}
        try:
            res = requests.request(method="GET", url=auth_decode_url, headers=headers)
            if 200 <= res.status_code < 300:
                logger.info(res.status_code)
                # logger.info(str(res.json()))
                return UserData(res.json()['results'])
            else:
                return AnonymousUser()
        except Exception as e:
            logger.error("function 'get_auth_user' error: {}".format(str(e)))
            return AnonymousUser()


def get_user(scope):
    try:
        if not config.local_dev and 'netops-token' in scope['cookies'].keys():
            logger.debug('token: {}'.format(scope['cookies']['netops-token']))
            return get_auth_user(parse.unquote(scope['cookies']['netops-token']))
        return AnonymousUser()
    except Exception as e:
        logger.error("function 'get_user' error: {}".format(str(e)))
        return AnonymousUser()


class CorsMiddleWare(MiddlewareMixin):
    def process_request(self, request):
        if request.COOKIES.get('netops-token'):
            user = get_auth_user(parse.unquote(request.COOKIES['netops-token']))
            request.user = user

    def process_response(self, request, response):
        if request.headers.get("Username"):
            request.user.username = request.headers.get("Username")
        if request.META.get("HTTP_REFERER") is not None:
            response["Access-Control-Allow-Methods"] = "*"
            response["Access-Control-Allow-Credentials"] = True
            response['Access-Control-Allow-Headers'] = "Authorization"
            response["Access-Control-Allow-Origin"] = "/".join(request.META.get("HTTP_REFERER").split("/")[0:3])
            return response
        else:
            return response
