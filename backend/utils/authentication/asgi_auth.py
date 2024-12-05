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


def get_auth_user(token, url, action):
    logger.info("get_auth_user")
    auth_url = config.iam['url'] + '/users/casbin/'
    headers = {'Authorization': token}
    params = {'data': url, 'action': action}
    try:
        res = requests.request(method="GET", url=auth_url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            logger.info(res.status_code)
            return UserData(res.json()['data']['userinfo'])
        else:
            return AnonymousUser()
    except Exception as e:
        logger.error("function 'get_auth_user' error: {}".format(str(e)))
        return AnonymousUser()


def get_user(scope):
    try:
        if 'netops-token' in scope['cookies'].keys():
            logger.debug('token: {}'.format(scope['cookies']['netops-token']))
            return get_auth_user(parse.unquote(scope['cookies']['netops-token']), scope['path'], scope['type'])
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
        scope["user"] = get_user(scope)

    async def resolve_scope(self, scope):
        logger.info('resolve_scope')


QueryAuthMiddlewareStack = lambda inner: CookieMiddleware(
    SessionMiddleware(QueryAuthMiddleware(inner))
)
