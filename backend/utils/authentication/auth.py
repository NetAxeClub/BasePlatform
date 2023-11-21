# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      auth
   Description:
   Author:          Lijiamin
   date：           2023/6/19 17:20
-------------------------------------------------
   Change Activity:
                    2023/6/19 17:20
-------------------------------------------------
"""
import requests
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework import serializers
from confload.confload import config


class UserData(object):
    is_authenticated = True
    is_anonymous = False

    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])


def get_auth_user(token):
    rbac_instance = config.service_dicovery('rbac')
    if rbac_instance.status_code == 200:
        rbac_res = rbac_instance.json()
        auth_service_url = "{}/{}".format(rbac_res['hosts'][0]['ip'], rbac_res['hosts'][0]['port'])
        auth_decode_url = f'{auth_service_url}/rbac/userinfo'
        headers = {'Accept': 'application/json', 'Authorization': f'Bearer {str(token)}',
                   'Content-Type': 'application/json'}
        try:
            res = requests.request(method="GET", url=auth_decode_url, headers=headers)

        except requests.ConnectionError as err:
            raise serializers.ValidationError(f"Cannot establish connection: {err}") from err

        except requests.HTTPError as err:
            raise serializers.ValidationError(f"HTTP Error: {err}") from err
        except Exception as err:
            raise serializers.ValidationError(f"Error occurred: {err}") from err

        if 200 <= res.status_code < 300:
            # print(res.json())
            return UserData(res.json())
        else:
            raise AuthenticationFailed
    raise AuthenticationFailed


class CustomJWTAuthentication(JWTAuthentication):

    def get_validated_token(self, raw_token):
        return raw_token.decode()

    def get_user(self, validated_token):
        return get_auth_user(validated_token)


class CustomJWTAuthenticationScheme(SimpleJWTScheme):
    target_class = CustomJWTAuthentication