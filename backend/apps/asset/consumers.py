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


from asgiref.sync import sync_to_async

class SSHConsumer(MySSH):
    def __init__(self, *args, **kwargs):
        super(SSHConsumer, self).__init__(*args, **kwargs)
        self.account = None
        # db.connections.close_all() # 在异步环境中通常不需要手动关闭所有连接，由连接池处理
        self.path = ''.join([x for x in self.scope['path'].split('/') if x])
        self.device_id = re.findall(r'\d+', self.path)
        self.server = None
        self.ip = None

    async def connect(self):
        await super().connect()
        # 将数据库查询移到 connect 中，并使用 sync_to_async
        self.server = await sync_to_async(Server.objects.get)(id=self.device_id[0])
        self.ip = self.server.manage_ip

        if not config.local_dev:
            if self.scope['user'].is_anonymous:
                await self.send('不允许用户匿名登录，请重新登录平台刷新token')
                await self.close()
                return
        
        self.account = await sync_to_async(lambda: AssetAccount.objects.filter(
            server=self.server, server__account__protocol='ssh'
        ).values(
            "server__account__username",
            "server__account__password",
            "server__account__protocol",
            "server__account__port",
        ).first())()

        _CryptPwd = CryptPwd()
        self.username = self.account['server__account__username']
        self.password = _CryptPwd.decrypt_pwd(self.account['server__account__password'])
        self.port = self.account['server__account__port']
        
        try:
            # SSH 连接是阻塞操作，放在 sync_to_async 中执行
            def _ssh_connect():
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
            
            await sync_to_async(_ssh_connect)()
            await self.send("当前使用CMDB账户登陆设备,用户:{}".format(self.username))
        except Exception as e:
            await self.send(
                '用户{}通过webssh连接{}失败！原因：{}，用户名:{},密码:{}'.format(self.username, self.ip, e,
                                                               str(self.username).strip(),
                                                               str(self.password).strip()))
            await self.close()
            return
        
        # invoke_shell 也是阻塞的，但通常很快
        self.chan = self.ssh.invoke_shell(term='xterm', width=self.width, height=self.height)
        self.chan.settimeout(60 * 3)
        self.t1.setDaemon(True)
        self.t1.start()


# 新版本网络设备ssh
class WebSSHConsumer(MySSH):
    def __init__(self, *args, **kwargs):
        super(WebSSHConsumer, self).__init__(*args, **kwargs)
        # db.connections.close_all()
        self.path = ''.join([x for x in self.scope['path'].split('/') if x])
        self.device_id = re.findall(r'\d+', self.path)
        self.server = None
        self.bind_ssh_ip = None
        self.ip = None
        self.account = None

    async def connect(self):
        await super().connect()
        self.server = await sync_to_async(NetworkDevice.objects.get)(id=self.device_id[0])
        self.bind_ssh_ip = await sync_to_async(lambda: list(AssetIpInfo.objects.filter(device=self.scope['path'].split('/')[4], name='SSH').values()))()
        
        # 如果有关联SSH的IP，则使用关联SSH方式登录
        if self.bind_ssh_ip:
            self.ip = self.bind_ssh_ip[0]['ipaddr']
        else:
            self.ip = self.server.manage_ip

        if not config.local_dev:
            if self.scope['user'].is_anonymous:
                await self.send('不允许用户匿名登录，请重新登录平台刷新token')
                await self.close()
                return
        
        _CryptPwd = CryptPwd()
        if self.server.ssh_enable == 'account':
            self.username = await sync_to_async(lambda: self.server.ssh_account.username)()
            pwd = await sync_to_async(lambda: self.server.ssh_account.password)()
            self.password = _CryptPwd.decrypt_pwd(pwd)
            self.port = await sync_to_async(lambda: self.server.ssh_account.port)()
        else:
            self.account = await sync_to_async(lambda: AssetAccount.objects.filter(
                networkdevice=self.server, networkdevice__account__protocol='ssh'
            ).values(
                "networkdevice__account__username",
                "networkdevice__account__password",
                "networkdevice__account__protocol",
                "networkdevice__account__port",
            ).first())()
            self.port = self.account['networkdevice__account__port']
            self.username = self.account['networkdevice__account__username']
            self.password = _CryptPwd.decrypt_pwd(self.account['networkdevice__account__password'])

        try:
            def _ssh_connect():
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(self.ip,
                                 self.port,
                                 self.username.strip(),
                                 self.password.strip(),
                                 timeout=20,
                                 banner_timeout=60,
                                 allow_agent=False,
                                 look_for_keys=False)
            
            await sync_to_async(_ssh_connect)()
            await self.send("当前使用网管账号登陆设备,账号:{},操作用户:{}".format(self.username, self.scope['user'].username))
        except Exception as e:
            await self.send(
                '用户{}通过webssh连接{}失败！原因：{}，用户名:{},密码:{}'.format(self.username, self.ip, e,
                                                               str(self.username).strip(),
                                                               str(self.password).strip()))
            await self.close()
            return
        
        self.chan = self.ssh.invoke_shell(term='xterm', width=self.width, height=self.height)
        self.chan.settimeout(60 * 10)
        self.t1.setDaemon(True)
        self.t1.start()
