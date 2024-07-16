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
import requests
from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from confload.confload import config
from urllib.parse import parse_qs


class IamMiddleware(MiddlewareMixin):

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def process_request(self, request):
        """
        平台架构:服务名:app/route名:资源名:<条件属性>
        infr:service:app_name:table_name:<{'name': 'aabb'}>
        """

        user = request.COOKIES.get('user')
        if user is None:
            self.require_permission()
        URN = "{}:{}".format(config.iam['urn_prefix'], request.path)
        method = request.method.upper()
        flag, res = self.check_permission(user, URN, method)
        if not flag:
            raise PermissionDenied
        _role, _urn, _action, _eft, _condition, _name = res.json()['data']
        if len(_urn.split(':')) == 4:
            _params = _urn.split(':')[-1][1:-1]
            result = {k: v[0] for k, v in parse_qs(_params).items()}
            request.iam = result

    def check_permission(self, user, URN, method):
        auth_url = config.iam['url'] + '/v1/auth_policy'
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        params = {'user': user, 'urn': URN, 'action': method}
        try:
            res = requests.request(method="GET", url=auth_url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                return True, res
            return False, res
        except Exception as e:
            print(e)

    def require_permission(self):
        raise PermissionDenied