# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      asgi_auth.py
   Description:
   Author:          Lijiamin
   date：           2023/6/20 09:53
-------------------------------------------------
   Change Activity:
                    2023/6/20 09:53
-------------------------------------------------
"""
import requests
import logging
from urllib import parse
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import LazyObject
from channels.middleware import BaseMiddleware
from channels.sessions import CookieMiddleware, SessionMiddleware
from confload.confload import config

logger = logging.getLogger('websocket')


class UserData(object):
    is_authenticated = True
    is_anonymous = False

    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])


def get_auth_user(token):
    logger.info("get_auth_user")
    rbac_instance = config.service_dicovery('rbac')
    logger.info(rbac_instance.status_code)
    if rbac_instance.status_code == 200:
        rbac_res = rbac_instance.json()
        auth_service_url = "http://{}:{}".format(rbac_res['hosts'][0]['ip'], rbac_res['hosts'][0]['port'])
        auth_decode_url = f'{auth_service_url}/rbac/userinfo'
        headers = {'Accept': 'application/json', 'Authorization': f'{str(token)}',
                   'Content-Type': 'application/json'}
        try:
            res = requests.request(method="GET", url=auth_decode_url, headers=headers)
            logger.info(str(res.json()))
            if 200 <= res.status_code < 300:
                logger.info(res.status_code)
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


class UserLazyObject(LazyObject):
    """
    Throw a more useful error message when scope['user'] is accessed before it's resolved
    """

    def _setup(self):
        raise ValueError("Accessing scope user before it is ready.")


class QueryAuthMiddleware(BaseMiddleware):
    """
    Middleware which populates scope["user"] from a Django session.
    Requires SessionMiddleware to function.
    """

    def populate_scope(self, scope):
        logger.info('populate_scope')
        # Make sure we have a session
        if "session" not in scope:
            raise ValueError(
                "AuthMiddleware cannot find session in scope. SessionMiddleware must be above it."
            )
        # Add it to the scope if it's not there already
        if "user" not in scope:
            scope["user"] = get_user(scope)

    async def resolve_scope(self, scope):
        logger.info('resolve_scope')
        # scope["user"] = get_user(scope)


QueryAuthMiddlewareStack = lambda inner: CookieMiddleware(
    SessionMiddleware(QueryAuthMiddleware(inner))
)
