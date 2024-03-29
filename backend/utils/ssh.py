# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      ssh
   Description:
   Author:          Lijiamin
   date：           2022/10/7 10:37
-------------------------------------------------
   Change Activity:
                    2022/10/7 10:37
-------------------------------------------------
"""
import logging
import os
import re
import threading
import time
import traceback
from socket import timeout

import paramiko
from channels.generic.websocket import WebsocketConsumer
from django.conf import settings
from django.http.request import QueryDict
from apps.asset.models import AdminRecord
from apps.asset.tasks import admin_file

fort_logger = logging.getLogger('webssh')


class MyThread(threading.Thread):
    def __init__(self, chan):
        super(MyThread, self).__init__()
        self.chan = chan
        self._stop_event = threading.Event()
        self.start_time = time.time()
        self.current_time = time.strftime(settings.TIME_FORMAT)
        self.stdout = []

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set() or not self.chan.chan.exit_status_ready():
            try:
                data = self.chan.chan.recv(1024)
                if data:
                    str_data = data.decode('utf-8', 'ignore')
                    self.chan.send(str_data)
                    self.stdout.append([time.time() - self.start_time, 'o', str_data])
                    # 捕获敲tab键的动作
                    if self.chan.tab_mode:
                        tmp = str_data.split(' ')
                        if len(tmp) == 2 and tmp[1] == '' and tmp[0] != '':
                            self.chan.cmd_tmp = self.chan.cmd_tmp + tmp[0].encode().replace(b'\x07', b'').decode()
                        elif len(tmp) == 1 and tmp[0].encode() != b'\x07':  # \x07 蜂鸣声
                            self.chan.cmd_tmp = self.chan.cmd_tmp + tmp[0].encode().replace(b'\x07', b'').decode()
                        self.chan.tab_mode = False
                    if self.chan.history_mode:
                        self.chan.index = 0
                        if str_data.strip() != '':
                            self.chan.cmd_tmp = re.sub(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]|\x08', '', str_data)
                        self.chan.history_mode = False
                else:
                    return
            except timeout:
                break
        self.chan.send('\n由于长时间没有操作，连接已断开!', close=True)
        self.stdout.append([time.time() - self.start_time, 'o', '\n由于长时间没有操作，连接已断开!'])
        self.chan.close()
        # self.record()

    def record(self):
        record_path = os.path.join(settings.MEDIA_ROOT, 'admin_ssh_records', self.chan.scope['user'].username,
                                   time.strftime('%Y-%m-%d'))
        if not os.path.exists(record_path):
            os.makedirs(record_path, exist_ok=True)
        record_file_name = '{}.{}.cast'.format(self.chan.ip, time.strftime('%Y%m%d%H%M%S'))
        record_file_path = os.path.join(record_path, record_file_name)

        header = {
            "version": 2,
            "width": self.chan.width,
            "height": self.chan.height,
            "timestamp": round(self.start_time),
            # "title": "ssh",
            "title": "{}-{}".format(self.chan.ip, self.current_time),
            "env": {
                "TERM": os.environ.get('TERM'),
                "SHELL": os.environ.get('SHELL', '/bin/bash')
            },
        }

        login_status_time = self.format_time(time.time() - self.start_time)
        login_user = self.chan.scope['user']
        login_server = r'{}@{}'.format(login_user.username, self.chan.ip)
        # print('login_user', login_user) # AnonymousUser
        # print('login_server', login_server) # None@10.254.23.47
        # print(record_file_path) # None@10.254.23.47
        try:
            # if login_user.is_superuser:
            admin_file.delay(record_file_path, self.stdout, header)
            # admin_file(record_file_path, self.stdout, header)
            # if not login_user.is_anonymous:
            AdminRecord.objects.create(
                admin_login_user=login_user.username,
                admin_server=login_server,
                admin_remote_ip=self.chan.remote_ip,
                admin_start_time=self.current_time,
                admin_login_status_time=login_status_time,
                admin_record_file=record_file_path.split('media/')[1],
                admin_record_cmds='\n'.join([x.strip() for x in self.chan.cmd])
            )
        except Exception as e:
            print(traceback.print_exc())
            fort_logger.error('数据库添加用户操作记录失败，原因：{}'.format(e))

    @staticmethod
    def format_time(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)

        if h:
            return "%02dh:%02dm:%02ds" % (h, m, s)
        if m:
            return "%02dm:%02ds" % (m, s)
        else:
            return "%02ds" % s


class MySSH(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super(MySSH, self).__init__(*args, **kwargs)
        self.ssh = paramiko.SSHClient()
        self.ip = None
        self.port = None
        self.username = None
        self.password = None
        self.t1 = MyThread(self)
        self.query = QueryDict(query_string=self.scope.get('query_string'), encoding='utf-8')
        self.remote_ip = self.scope['query_string'].decode('utf8')
        self.width = 150
        self.height = 30
        self.chan = None
        self.cmd = []  # 所有命令
        self.cmd_tmp = ''  # 一行命令
        self.tab_mode = False  # 使用tab命令补全时需要读取返回数据然后添加到当前输入命令后
        self.history_mode = False
        self.index = 0

    def connect(self):
        self.accept()
        # print('accept')
        try:
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.ip, int(self.port), self.username, self.password, timeout=5)
        except Exception as e:
            fort_logger.error('用户{}通过webssh连接{}失败！原因：{}'.format(self.username, self.ip, e))
            self.send('用户{}通过webssh连接{}失败！原因：{}'.format(self.username, self.ip, e), close=True)

        self.chan = self.ssh.invoke_shell(term='ansi', width=self.width, height=self.height)
        # 设置如果3分钟没有任何输入，就断开连接
        self.chan.settimeout(60 * 3)
        self.t1.setDaemon(True)
        self.t1.start()

    def disconnect(self, close_code):
        # print('断开连接', close_code)
        try:
            self.handle_cmd()
            self.t1.record()
        finally:
            self.ssh.close()
            self.t1.stop()

    def receive(self, text_data=None, bytes_data=None):
        try:
            self.chan.send(text_data)
            self.gen_cmd(text_data)
        except:
            self.websocket_disconnect(message=dict(code=4004))

    def gen_cmd(self, text_data):
        if text_data == '\r':
            self.index = 0
            if self.cmd_tmp.strip() != '':
                self.cmd.append(self.cmd_tmp)
                self.cmd_tmp = ''
        elif text_data.encode() == b'\x07':  # \x07 蜂鸣声
            pass
        elif text_data.encode() in (b'\x03', b'\x01'):  # ctrl+c 和 ctrl+a
            self.index = 0
        elif text_data.encode() == b'\x05':  # ctrl+e
            self.index = len(self.cmd_tmp) - 2
        elif text_data.encode() == b'\x1b[D':  # ← 键
            if self.index == 0:
                self.index = len(self.cmd_tmp) - 2
            else:
                self.index -= 1
        elif text_data.encode() == b'\x1b[C':  # → 键
            self.index += 1
        elif text_data.encode() == b'\x7f':  # Backspace键
            if self.index == 0:
                self.cmd_tmp = self.cmd_tmp[:-1]
            else:
                self.cmd_tmp = self.cmd_tmp[:self.index] + self.cmd_tmp[self.index + 1:]
        else:
            if text_data == '\t' or text_data.encode() == b'\x1b':  # \x1b 点击2下esc键也可以补全
                self.tab_mode = True
            elif text_data.encode() == b'\x1b[A' or text_data.encode() == b'\x1b[B':
                self.history_mode = True
            else:
                if self.index == 0:
                    self.cmd_tmp += text_data
                else:
                    self.cmd_tmp = self.cmd_tmp[:self.index] + text_data + self.cmd_tmp[self.index:]

    def handle_cmd(self):  # 将vim或vi编辑文档时的操作去掉
        vi_index = None
        fg_index = None  # 捕捉使用ctrl+z将vim放到后台的操作
        q_index = None
        q_keys = (':wq', ':q', ':q!', 'quit', 'exit')
        for index, value in enumerate(self.cmd):
            if 'vi' in value:
                vi_index = index
            if any([key in value for key in q_keys]):
                q_index = index
            if '\x1a' in value:  # \x1a代表ctrl+z
                self.cmd[index] = value.split('\x1a')[1]
            if 'fg' in value:
                fg_index = index

        first_index = fg_index if fg_index else vi_index
        if vi_index:
            self.cmd = self.cmd[:first_index + 1] + self.cmd[q_index + 1:]
