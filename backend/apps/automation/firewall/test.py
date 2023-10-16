# -*- coding: utf-8 -*-
# @Time    : 2021/8/8 23:38
# @Author  : LiJiaMin
# @Site    : 
# @File    : test.py
# @Software: PyCharm
import jinja2
import os
package_dir = os.path.dirname(__file__)

# def test():
#   my_vars = {
#     'MOD': 2,
#     'VLAN_ID': 200,
#     'VLAN_NAME': 'Route-Access',
#     'SVI_IP': '10.0.0.2',
#     'OSPF_PWD': 'Password',
#     'OSPF_PRCS': 200,
#     'OSPF_AREA': '0.0.0.200'
#   }
#
#   my_template = '''
#   interface Vlan{{ VLAN_ID }}
#     description {{ VLAN_NAME }}
#     no ip redirects
#     no ipv6 redirects
#     ip address {{ SVI_IP }}/25
#     ip ospf authentication message-digest
#     ip ospf message-digest-key 1 md5 {{ OSPF_PWD }}
#     ip ospf dead-interval 4
#     ip ospf hello-interval 1
#     {%- if MOD == 1 %}
#     ip ospf priority 255
#     {%- else %}
#     ip ospf priority 254
#     {%- endif %}
#     ip router ospf {{ OSPF_PRCS }} area {{ OSPF_AREA }}
#     no shutdown
#   '''
#
#   t = jinja2.Template(my_template)
#   print(t.render(my_vars))
#
#
# # 山石SLB测试
# def test_slb():
#   jinja_file = package_dir + '/slb_server_pool.j2'
#   _vars = {
#     "vendor": "hillstone",
#     "hostip": "10.254.1.1",
#     "description": "aa",
#     "slb_name": "test",
#     "monitor": "track-ping",
#     "monitor_threshold": 99,
#     "load_balance": "weighted-round-robin sticky",
#     "objects": [
#       {"ip": "1.1.1.1/24", "type": "ip", "port": 80, "weight": 1, "max_connection": 655350},
#       {"ip": "2.2.2.1 2.2.2.5", "type": "ip-range", "weight": 1, "max_connection": 655350}]
#   }
#   with open(jinja_file) as f:
#     template = jinja2.Template(f.read())
#   tmp_commands = template.render(_vars)
#   print(tmp_commands)
#   return tmp_commands
#
# if __name__ == '__main__':
#   res = test_slb()
#   for i in res.split('\n'):
#     print(i)