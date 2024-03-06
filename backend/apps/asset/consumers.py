# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      consumers
   Description:
   Author:          Lijiamin
   date：           2022/9/8 17:46
-------------------------------------------------
   Change Activity:
                    2022/9/8 17:46
-------------------------------------------------
"""

# import os
# import time
import logging
import re
import paramiko
from django import db
from apps.asset.models import NetworkDevice, AssetIpInfo, AssetAccount, Server
from utils.crypt_pwd import CryptPwd
from confload.confload import config
from utils.ssh import MySSH
import socket
socket.gethostname()
logger = logging.getLogger('webssh')


class SSHConsumer(MySSH):
    def __init__(self, *args, **kwargs):
        super(SSHConsumer, self).__init__(*args, **kwargs)
        self.account = None
        db.connections.close_all()
        self.path = ''.join([x for x in self.scope['path'].split('/') if x])
        self.device_id = re.findall(r'\d+', self.path)
        self.server = Server.objects.get(id=self.device_id[0])
        self.ip = self.server.manage_ip

    def connect(self):
        self.accept()
        if not config.local_dev:
            if self.scope['user'].is_anonymous:
                self.send('不允许用户匿名登录，请重新登录平台刷新token')
                self.close()
                return
        self.account = AssetAccount.objects.filter(
            server=self.server, server__account__protocol='ssh'
        ).values(
            "server__account__username",
            "server__account__password",
            "server__account__protocol",
            "server__account__port",
        ).first()
        _CryptPwd = CryptPwd()
        self.username = self.account['server__account__username']
        self.password = _CryptPwd.decrypt_pwd(self.account['server__account__password'])
        self.port = self.account['server__account__port']
        try:
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.ip,
                             self.port,
                             self.username.strip(),
                             self.password.strip(),
                             timeout=15,
                             banner_timeout=60,
                             allow_agent=False,
                             look_for_keys=False)
            self.send("当前使用CMDB账户登陆设备,用户:{}".format(self.username))
        except Exception as e:
            self.send(
                '用户{}通过webssh连接{}失败！原因：{}，用户名:{},密码:{}'.format(self.username, self.ip, e,
                                                               str(self.username).strip(),
                                                               str(self.password).strip()))
            self.close()
            return
        # ansi or xterm ?
        self.chan = self.ssh.invoke_shell(term='xterm', width=self.width, height=self.height)
        # 设置如果3分钟没有任何输入，就断开连接
        self.chan.settimeout(60 * 3)
        self.t1.setDaemon(True)
        self.t1.start()


# 新版本网络设备ssh
class WebSSHConsumer(MySSH):
    def __init__(self, *args, **kwargs):
        super(WebSSHConsumer, self).__init__(*args, **kwargs)
        db.connections.close_all()
        self.path = ''.join([x for x in self.scope['path'].split('/') if x])
        logger.debug(self.path)
        self.device_id = re.findall(r'\d+', self.path)
        # self.server = NetworkDevice.objects.get(id=self.scope['path'].split('/')[4])
        self.server = NetworkDevice.objects.get(id=self.device_id[0])
        # print(self.server)
        self.bind_ssh_ip = AssetIpInfo.objects.filter(device=self.scope['path'].split('/')[4], name='SSH').values()
        # 如果有关联SSH的IP，则使用关联SSH方式登录
        if self.bind_ssh_ip:
            self.ip = self.bind_ssh_ip[0]['ipaddr']
        else:
            self.ip = self.server.manage_ip
        self.account = None

    def connect(self):
        self.accept()
        if not config.local_dev:
            if self.scope['user'].is_anonymous:
                self.send('不允许用户匿名登录，请重新登录平台刷新token')
                self.close()
                return
        _CryptPwd = CryptPwd()
        self.account = AssetAccount.objects.filter(
            networkdevice=self.server, networkdevice__account__protocol='ssh'
        ).values(
            "networkdevice__account__username",
            "networkdevice__account__password",
            "networkdevice__account__protocol",
            "networkdevice__account__port",
        ).first()
        self.port = self.account['networkdevice__account__port']
        self.username = self.account['networkdevice__account__username']
        self.password = _CryptPwd.decrypt_pwd(self.account['networkdevice__account__password'])

        try:
            # self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.ip,
                             self.port,
                             self.username.strip(),
                             self.password.strip(),
                             timeout=20,
                             banner_timeout=60,
                             allow_agent=False,
                             look_for_keys=False)
            self.send("当前使用网管账号登陆设备,账号:{},操作用户:{}".format(self.username, self.scope['user'].username))
        except Exception as e:
            self.send(
                '用户{}通过webssh连接{}失败！原因：{}，用户名:{},密码:{}'.format(self.username, self.ip, e,
                                                               str(self.username).strip(),
                                                               str(self.password).strip()))
            self.close()
            return
        # ansi or xterm ?
        self.chan = self.ssh.invoke_shell(term='xterm', width=self.width, height=self.height)
        # 设置如果60分钟没有任何输入，就断开连接
        self.chan.settimeout(60 * 10)
        self.t1.setDaemon(True)
        self.t1.start()
