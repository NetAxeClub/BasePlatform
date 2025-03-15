# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      test3
   Description:
   Author:          Lijiamin
   date：           2024/11/14 16:35
-------------------------------------------------
   Change Activity:
                    2024/11/14 16:35
-------------------------------------------------
"""
import requests
from requests.auth import HTTPBasicAuth


def get_prometheus_data(url, params, headers, username, password):
    # 使用HTTPBasicAuth进行基本认证
    auth = HTTPBasicAuth(username, password)

    # 发送GET请求
    try:
        response = requests.get(url, params=params, headers=headers, auth=auth, timeout=5)

        # 获取状态码
        status_code = response.status_code

        # 解析JSON响应
        response_data = response.json()

        return status_code, response_data
    except requests.RequestException as e:
        # 处理请求异常
        print(f"An error occurred: {e}")
        return None, None


if __name__ == '__main__':
    prometheus_url = "http://10.254.12.169:30000/api/v1/query"
    prometheus_username = "admin"
    prometheus_password = "ADASIavsdf^&*)123"
    headers = {
        'Content-Type': 'application/json'
    }
    instance = '172.31.131.243'
    params = {
        'query': 'sum(sum_over_time(probe_success{instance=~"^%s", job=~"icmp_.*"}[30s])) by (value)' % instance
    }
    status_code, response_data = get_prometheus_data(url=prometheus_url, params=params, headers=headers, username=prometheus_username, password=prometheus_password)
    print(status_code)
    print(response_data)


