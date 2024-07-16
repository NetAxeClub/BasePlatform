# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      ip_test
   Description:
   Author:          Lijiamin
   date：           2023/12/28 10:59
-------------------------------------------------
   Change Activity:
                    2023/12/28 10:59
-------------------------------------------------
"""
from netaddr import IPNetwork
import requests
import json
def test_ip(net_addr):
    net = IPNetwork(net_addr)
    res = list(net.subnet(24))
    for sub in res:
        for i in sub.iter_hosts():
            pass
        url = "http://10adsfa/ipam/v1/ipam_api/"

        payload = {
            "subnet": str(sub),
            "network_type": "研测",
            "update": "1"
        }
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))

        print(response.json())


if __name__ == '__main__':
    test_ip('172.31.0.0/16')