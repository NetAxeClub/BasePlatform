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
import logging
import traceback
import requests
from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from confload.confload import config
from urllib.parse import unquote
from urllib.parse import parse_qs

logger = logging.getLogger('custom_middleware')

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
        token = request.COOKIES.get('netops-token')
        logger.info(f"cookies token: {token}")
        if token is None:
            token = request.HEADERS.get('netops-token')
            logger.debug(f"header token: {token}")

        # if token is None:
        #     self.require_permission()
        # flag, res = self.check_permission(unquote(token), request.path, request.method.lower())
        # if not flag:
        #     raise PermissionDenied
        # print(res)
        # if res['code'] == 200:
        #     is_allow = res['data']['is_allow']
        #     request.user = UserData(res['data']['userinfo'])
        # else:
        #     request.user = AnonymousUser()
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

    def require_permission(self):
        raise PermissionDenied