# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      consumers
   Description:
   Author:          lijiamin
   date：           2020/4/24
-------------------------------------------------
   Change Activity:
                    2020/4/24:
-------------------------------------------------
"""
from channels.generic.websocket import AsyncWebsocketConsumer
# from apps.automation.sec_main import _bulk_sec_policy
import json


class SecDeviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join room group
        self.room_name = self.scope['cookies']['username']
        self.room_group_name = 'sec_device_%s' % self.room_name
        # self.room_group_name = 'sec_device'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data=None, bytes_data=None):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        # print('message', message['method'])
        if message.get('method') == "get_room_name":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'sec_device_message',
                    'message': {'room_name': self.room_group_name}
                }
            )
        else:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'sec_device_message',
                    'message': {'msg': message, 'status': 'ok'}
                }
            )
        # # 新建安全策略
        # if all(k in message for k in ("device_object", "policy_object")):
        #     # print('新建安全策略')
        #     message['room_group_name'] = self.room_group_name
        #     _bulk_sec_policy(**message)
        #     await self.channel_layer.group_send(
        #         self.room_group_name,
        #         {
        #             'type': 'sec_device_message',
        #             'message': {'msg': 'create_sec_policy'}
        #         }
        #     )
        # # 编辑安全策略
        # elif all(k in message for k in ("device_object", "edit_policy_object")):
        #     # print('编辑安全策略')
        #     message['room_group_name'] = self.room_group_name
        #     _bulk_sec_policy(**message)
        #     await self.channel_layer.group_send(
        #         self.room_group_name,
        #         {
        #             'type': 'sec_device_message',
        #             'message': {'msg': 'edit_sec_policy'}
        #         }
        #     )
        # else:
        #     # Send message to room group
        #     await self.channel_layer.group_send(
        #         self.room_group_name,
        #         {
        #             'type': 'sec_device_message',
        #             'message': {'msg': 'no method'}
        #         }
        #     )

    # Receive message from room group
    async def sec_device_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))