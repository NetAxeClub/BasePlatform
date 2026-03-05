# -*- coding: utf-8 -*-
"""
多厂商防火墙适配层。

用法::

    from apps.dcs_control.firewall.registry import get_adapter
    from apps.dcs_control.firewall.registry import register_all

    register_all()   # 在 Django ready() 或首次调用前执行一次即可

    adapter = get_adapter('Hillstone', fw_main)
    cmds, back_off_cmds, class_method = adapter.address_cmds(**post_param)
"""
