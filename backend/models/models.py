# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      models
   Description:
   Author:          Lijiamin
   date：           2023/4/3 15:13
-------------------------------------------------
   Change Activity:
                    2023/4/3 15:13
-------------------------------------------------
"""
from enum import Enum
from typing import Optional, Any, List, Union, Type

from pydantic import BaseModel, validator, create_model, root_validator


class LibraryName(str, Enum):
    sms = "sms"
    wechat = "wechat"
    telephone = "telephone"
    email = "email"


class WebhookMethod(str, Enum):
    http = 'http'
    bus = 'bus'


class SendMsgArgs(BaseModel):
    msg: str


class WebhookHttpArgs(BaseModel):
    url: str
    body: dict


class WebhookBusArgs(BaseModel):
    queue: str
    body: dict


class Webhook(BaseModel):
    method: WebhookMethod
    args: Union[WebhookBusArgs, WebhookHttpArgs]


class SmsArgs(BaseModel):
    phone: List[str]
    content: Optional[str] = None


class WechatType(str, Enum):
    text: str  # 纯文本
    graph: str  # 图片带正文


class WechatArgs(BaseModel):
    user: Optional[str] = '@all'
    content: Optional[str] = None
    channel: Optional[str] = None
    type: WechatType


class EmailArgs(BaseModel):
    user: List[str]
    content: Optional[str] = None
    subject: Optional[str] = None
    content_type: Optional[str] = 'html'


class SendMsg(BaseModel):
    library: LibraryName
    # send_args: Union[SmsArgs, WechatArgs, EmailArgs]
    send_args: dict
    webhook: Optional[Webhook] = {}
    peer_queue: str = None
    peer_routing_key: str = None
    # @validator('send_args')
    # def validate_send_args(cls, v, values):
    #     if values['library'] == 'wechat':
    #         return WechatArgs(**v)
    #     elif values['library'] == 'sms':
    #         return SmsArgs(**v)
    #     else:
    #         raise ValueError('Invalid library name')

    class Config:
        schema_extra = {
            "example": {
                "library": "sms",
                "send_args": {
                     "phone": ["1865111111"],
                     "content": "这是一条测试短信，11223344"
                },
                "webhook": {
                    "name": "test",
                    "args": {
                        "vlans": ["5", "3", "2"]
                    }
                }
            }
        }


class Login(BaseModel):
    username: str
    password: str















