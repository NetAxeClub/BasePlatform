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
import asyncio
import logging
import os
import re
import threading
import time
from socket import timeout

import paramiko
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.http.request import QueryDict
from apps.asset.models import AdminRecord
from apps.asset.tasks import admin_file

fort_logger = logging.getLogger('webssh')

# WebSSH：单次 recv 上限与批量刷盘阈值，减少 async_to_sync(send) 次数，缓解大回显时事件循环与前端卡顿
_SSH_RECV_MAX = 64 * 1024
_SSH_WS_BATCH_BYTES = 32 * 1024


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

    def _apply_tab_history(self, str_data):
        """按原始 recv 分片处理 tab/历史，避免批量发送时合并破坏补全逻辑。"""
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

    def _flush_pending_ws(self, raw_bytes):
        if not raw_bytes:
            return
        str_data = raw_bytes.decode('utf-8', 'ignore')
        async_to_sync(self.chan.send)(text_data=str_data)
        self.stdout.append([time.time() - self.start_time, 'o', str_data])

    def run(self):
        pending = b''
        try:
            while not self._stop_event.is_set():
                if self.chan.chan.exit_status_ready():
                    if pending:
                        self._flush_pending_ws(pending)
                        pending = b''
                    break
                try:
                    data = self.chan.chan.recv(_SSH_RECV_MAX)
                    if not data:
                        if pending:
                            self._flush_pending_ws(pending)
                            pending = b''
                        break
                    str_chunk = data.decode('utf-8', 'ignore')
                    self._apply_tab_history(str_chunk)
                    pending += data
                    while len(pending) >= _SSH_WS_BATCH_BYTES:
                        self._flush_pending_ws(pending[:_SSH_WS_BATCH_BYTES])
                        pending = pending[_SSH_WS_BATCH_BYTES:]
                    # 本轮读不满缓冲区，通常表示当前 burst 已结束，尽快刷出以降低交互延迟
                    if len(data) < _SSH_RECV_MAX and pending:
                        self._flush_pending_ws(pending)
                        pending = b''
                except timeout:
                    if pending:
                        self._flush_pending_ws(pending)
                        pending = b''
                    continue
                except Exception as e:
                    fort_logger.error(f"SSH Thread error: {e}")
                    if pending:
                        self._flush_pending_ws(pending)
                        pending = b''
                    break
            if pending:
                self._flush_pending_ws(pending)

            # 断开连接后的处理
            if not self._stop_event.is_set():
                async_to_sync(self.chan.send)(text_data='\n由于长时间没有操作或连接已断开!', close=True)
            self.stdout.append([time.time() - self.start_time, 'o', '\n由于长时间没有操作或连接已断开!'])
        finally:
            self.chan.close_ssh()

    def record(self):
        # 记录逻辑保持同步，在异步 consumer 中使用 sync_to_async 调用
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
            "title": "{}-{}".format(self.chan.ip, self.current_time),
            "env": {
                "TERM": os.environ.get('TERM'),
                "SHELL": os.environ.get('SHELL', '/bin/bash')
            },
        }

        login_status_time = self.format_time(time.time() - self.start_time)
        login_user = self.chan.scope['user']
        login_server = r'{}@{}'.format(login_user.username, self.chan.ip)
        try:
            admin_file.delay(record_file_path, self.stdout, header)
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


class MySSH(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super(MySSH, self).__init__(*args, **kwargs)
        self.ssh = paramiko.SSHClient()
        self.ip = None
        self.port = None
        self.username = None
        self.password = None
        self.t1 = None
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

    async def connect(self):
        await self.accept()
        self.t1 = MyThread(self)
        # 具体的连接逻辑由子类实现或在此扩展

    def close_ssh(self):
        """由线程或断开连接时调用，确保资源释放"""
        try:
            if self.chan:
                self.chan.close()
            if self.ssh:
                self.ssh.close()
        except Exception as e:
            fort_logger.error(f"Error closing SSH: {e}")

    async def disconnect(self, close_code):
        if self.t1:
            self.t1.stop()
        
        # 异步执行耗时操作
        await sync_to_async(self.handle_cmd)()
        if self.t1:
            await sync_to_async(self.t1.record)()
        
        self.close_ssh()

    def _ssh_channel_send(self, text_data):
        """在线程中执行 paramiko 写通道，供 run_in_executor 调用。"""
        self.chan.send(text_data)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if self.chan and text_data is not None:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._ssh_channel_send, text_data)
                self.gen_cmd(text_data)
        except Exception as e:
            fort_logger.error(f"Receive error: {e}")
            await self.close()

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
