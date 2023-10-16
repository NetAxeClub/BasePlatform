#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2022/7/7 19:36
# @Author  : dingyifei
import os
from netaxe.settings import BASE_DIR
from netmiko.ssh_dispatcher import CLASS_MAPPER, CLASS_MAPPER_BASE, FILE_TRANSFER_MAP, ssh_dispatcher
from .hillstone import HillstoneSSH, HillstoneTelnet
from .fiberhome import FiberHomeSSH
from .mypower import MypowerOsSSH

os.environ["NTC_TEMPLATES_DIR"] = BASE_DIR + '/utils/connect_layer/zetmiko/templates'

CLASS_MAPPER['hillstone'] = HillstoneSSH
CLASS_MAPPER['hillstone_telnet'] = HillstoneTelnet
CLASS_MAPPER['fiberhome'] = FiberHomeSSH
CLASS_MAPPER['mypower'] = MypowerOsSSH

platforms = list(CLASS_MAPPER.keys())
platforms.sort()
platforms_base = list(CLASS_MAPPER_BASE.keys())
platforms_base.sort()
platforms_str = "\n".join(platforms_base)
platforms_str = "\n" + platforms_str

scp_platforms = list(FILE_TRANSFER_MAP.keys())
scp_platforms.sort()
scp_platforms_str = "\n".join(scp_platforms)
scp_platforms_str = "\n" + scp_platforms_str

telnet_platforms = [x for x in platforms if "telnet" in x]
telnet_platforms_str = "\n".join(telnet_platforms)
telnet_platforms_str = "\n" + telnet_platforms_str


def ConnectHandler(*args, **kwargs):
    """Factory function selects the proper class and creates object based on device_type."""
    device_type = kwargs["device_type"]
    if device_type not in platforms:
        if device_type is None:
            msg_str = platforms_str
        else:
            msg_str = telnet_platforms_str if "telnet" in device_type else platforms_str
        raise ValueError(
            "Unsupported 'device_type' "
            "currently supported platforms are: {}".format(msg_str)
        )
    ConnectionClass = ssh_dispatcher(device_type)
    return ConnectionClass(*args, **kwargs)
