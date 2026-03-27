# -*- coding: utf-8 -*-
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class DeviceCollectionTaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        username = getattr(self.scope.get("user"), "username", "")
        if not username:
            await self.close(code=4001)
            return
        self.room_group_name = f"device_collection_{username}"
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        room_group_name = getattr(self, "room_group_name", "")
        if room_group_name:
            await self.channel_layer.group_discard(
                room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except Exception:
            payload = {"message": text_data}
        await self.send(text_data=json.dumps({"message": payload}))

    async def device_collection_message(self, event):
        await self.send(text_data=json.dumps(event.get("message", {})))
