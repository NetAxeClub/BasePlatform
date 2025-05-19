# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      iam
   Description:
   Author:          Lijiamin
   date：           2024/4/25 14:32
-------------------------------------------------
   Change Activity:
                    2024/4/25 14:32
-------------------------------------------------
"""
import json
import logging
# import traceback
import requests
from rest_framework.exceptions import NotAuthenticated
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from confload.confload import config
from urllib.parse import unquote
from urllib.parse import parse_qs

logger = logging.getLogger('custom_middleware')


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401


class UserData(object):
    is_authenticated = True
    is_anonymous = False
    is_staff = True
    is_active = True

    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])


class IamMiddleware(MiddlewareMixin):

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def process_response(self, request, response):
        if request.META.get("HTTP_REFERER") is not None:
            response["Access-Control-Allow-Methods"] = "*"
            response["Access-Control-Allow-Credentials"] = True
            response['Access-Control-Allow-Headers'] = "Authorization"
            response["Access-Control-Allow-Origin"] = "/".join(request.META.get("HTTP_REFERER").split("/")[0:3])
            return response
        else:
            return response

    def process_request(self, request):
        """
        平台架构:服务名:app/route名:资源名:<条件属性>
        infr:service:app_name:table_name:<{'name': 'aabb'}>
        """
        is_allow = False
        if request.path.startswith('/admin/'):
            """允许admin后台登录"""
            return
        if request.path.startswith('/base_platform/automation/address_location'):
            """允许寻觅后台操作"""
            return
        if request.path.startswith('/base_platform/monitor/public_net_resource/'):
            """允许公网数据源操作"""
            return
        # if request.path.startswith('/base_platform/monitor/public_net_owner/'):
        #     """允许公网数据源操作"""
        #     return
        api_key = request.COOKIES.get('x-api-key') or request.headers.get('x-api-key')
        if api_key is not None:
            if api_key == config.api_key:
                return
        token = request.COOKIES.get('netops-token') or request.headers.get('netops-token')
        if token is None:
            response_data = {'error': 'Missing netops-token', 'code': 400, 'path': request.path, 'method': request.method}
            return HttpResponseUnauthorized(json.dumps(response_data))
            # raise NotAuthenticated(json.dumps(response_data))
            # self.require_permission()
        flag, res = self.check_permission(unquote(token), request.path, request.method.lower())
        logger.info(f"flag: {flag}, res: {res}")
        if not flag:
            response_data = {'error': 'request netaxe iam failed', 'code': 400, 'path': request.path, 'method': request.method}
            return HttpResponseUnauthorized(json.dumps(response_data))
            # raise NotAuthenticated(json.dumps(response_data))
            # raise PermissionDenied
        if res['code'] == 200:
            is_allow = res['data']['is_allow']
            request.iam = UserData(res['data']['userinfo'])
            # request.session = UserData(res['data']['userinfo']).__dict__
        else:
            request.iam = AnonymousUser()
            response_data = {'error': 'netaxe iam policy not allowed AnonymousUser', 'code': 400, 'path': request.path, 'method': request.method}
            return HttpResponseUnauthorized(json.dumps(response_data))
            # raise NotAuthenticated(json.dumps(response_data))
        # if not is_allow:
        #     raise PermissionDenied

        # if len(_urn.split(':')) == 4:
        #     _params = _urn.split(':')[-1][1:-1]
        #     result = {k: v[0] for k, v in parse_qs(_params).items()}
        #     request.iam = result
        # if len(_urn.split(':')) == 4:
        #     _params = _urn.split(':')[-1][1:-1]
        #     result = {k: v[0] for k, v in parse_qs(_params).items()}
        #     request.iam = result

    def check_permission(self, token, url, method):
        auth_url = config.iam['url'] + '/users/casbin/'
        headers = {'Authorization': token}
        params = {'data': url, 'action': method}
        try:
            res = requests.request(method="GET", url=auth_url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                return True, res.json()
            return False, res.json()
        except Exception as e:
            print(e)
            return False, {}

    # def require_permission(self):
    #     raise PermissionDenied