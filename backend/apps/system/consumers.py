# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      consumers
   Description:
   Author:          Lijiamin
   date：           2025/2/10 15:55
-------------------------------------------------
   Change Activity:
                    2025/2/10 15:55
-------------------------------------------------
"""
import logging
import json
import time
import traceback
import threading
from socket import timeout
from django.conf import settings
from openai import OpenAI
from confload.confload import config
from channels.generic.websocket import WebsocketConsumer

fort_logger = logging.getLogger('webssh')


# class MyThread(threading.Thread):
#     def __init__(self, chan):
#         super(MyThread, self).__init__()
#         self.chan = chan
#         self._stop_event = threading.Event()
#         self.start_time = time.time()
#         self.current_time = time.strftime(settings.TIME_FORMAT)
#         self.stdout = []
#
#     def stop(self):
#         self._stop_event.set()
#
#     def run(self):
#         while not self._stop_event.is_set() or not self.chan.chan.exit_status_ready():
#             try:
#                 data = self.chan.chan.recv(1024)
#                 if data:
#                     str_data = data.decode('utf-8', 'ignore')
#                     self.chan.send(str_data)
#                     self.stdout.append([time.time() - self.start_time, 'o', str_data])
#                     # 捕获敲tab键的动作
#                     if self.chan.tab_mode:
#                         tmp = str_data.split(' ')
#                         if len(tmp) == 2 and tmp[1] == '' and tmp[0] != '':
#                             self.chan.cmd_tmp = self.chan.cmd_tmp + tmp[0].encode().replace(b'\x07', b'').decode()
#                         elif len(tmp) == 1 and tmp[0].encode() != b'\x07':  # \x07 蜂鸣声
#                             self.chan.cmd_tmp = self.chan.cmd_tmp + tmp[0].encode().replace(b'\x07', b'').decode()
#                         self.chan.tab_mode = False
#                     if self.chan.history_mode:
#                         self.chan.index = 0
#                         if str_data.strip() != '':
#                             self.chan.cmd_tmp = re.sub(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]|\x08', '', str_data)
#                         self.chan.history_mode = False
#                 else:
#                     return
#             except timeout:
#                 break
#         self.chan.send('\n由于长时间没有操作，连接已断开!', close=True)
#         self.stdout.append([time.time() - self.start_time, 'o', '\n由于长时间没有操作，连接已断开!'])
#         self.chan.close()
#         # self.record()

class SparkChatConsumer(WebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = config.sparkapi['api_key']
        self.api_base = config.sparkapi['api_base']
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def connect(self):
        self.accept()
        print('accept')

    def disconnect(self, close_code):
        print('断开连接', close_code)
        # self.channel_layer.group_discard(
        #     self.room_group_name,
        #     self.channel_name
        # )

    def receive(self, text_data=None, bytes_data=None):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        try:
            try:
                response = self.client.chat.completions.create(
                    model=config.sparkapi['serviceId'],
                    messages=[{"role": "user", "content": message}],
                    stream=True,
                    temperature=0.7,
                    max_tokens=6144,
                    extra_headers={"lora_id": "0"},
                    stream_options={"include_usage": True}
                )

                full_response = ""
                for chunk in response:
                    # 只对支持深度思考的模型才有此字段
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[
                        0].delta.reasoning_content is not None:
                        reasoning_content = chunk.choices[0].delta.reasoning_content
                        # print(reasoning_content, end="", flush=True)  # 实时打印思考模型输出的思考过程每个片段
                        self.send(json.dumps({'message': {"content": '', 'reasoning_content': reasoning_content, 'end': False}}))
                        # self.channel_layer.group_send(
                        #     self.room_group_name,
                        #     {
                        #         'type': 'deepseek_message',
                        #         'message': {'reasoning_content': reasoning_content, 'content': ''}
                        #     }
                        # )
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        # print(content, end="", flush=True)  # 实时打印每个片段
                        full_response += content
                        self.send(json.dumps({'message': {"content": content, 'reasoning_content': '', 'end': False}}))
                        # self.channel_layer.group_send(
                        #     self.room_group_name,
                        #     {
                        #         'type': 'deepseek_message',
                        #         'message': {'reasoning_content': '', 'content': content}
                        #     }
                        #
                        # )
                self.send(json.dumps({'message': {"content": '', 'reasoning_content': '', 'end': True}}))
                # print("\n\n ------完整响应：", full_response)
            except Exception as e:
                print(traceback.print_exc())
                print(f"Error: {e}")
        except:
            self.websocket_disconnect(message=dict(code=4004))

    # def deepseek_message(self, event):
    #     message = event['message']
    #
    #     # Send message to WebSocket
    #     self.send(text_data=json.dumps({
    #         'message': message
    #     }))