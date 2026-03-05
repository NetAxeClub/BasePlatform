# -*- coding: utf-8 -*-
"""
流程引擎（FlowEngine）。

将 FirewallMain.flow_engine() 的核心逻辑提炼为独立类，
使各 Celery 任务可以直接使用，而无需通过 FirewallMain 间接调用。

设计目标
--------
- 解耦命令生成（FirewallAdapter）与命令执行 + 流程记录（FlowEngine）
- 每个 Celery 任务的调用模式简化为:
    1. fw = FirewallMain(hostip)
    2. adapter = get_adapter(vendor, fw)
    3. cmds, back_off, method = adapter.address_cmds(**post_param)
    4. FlowEngine(fw).run(cmds, back_off, method, **flow_data)

迁移路径
--------
当前 tasks.py 中的 flow_engine 方法仍是主力实现。
FlowEngine 提供相同签名，可在新任务或逐步重构时替换旧调用。
"""
from __future__ import annotations

import json
import logging

from django.core.files.storage import default_storage

from apps.automation.models import AutoFlow
from apps.asset.models import NetworkDevice
from apps.dcs_control.utils.ttp_parser import apply_ttp_result

log = logging.getLogger(__name__)


class FlowEngine:
    """
    命令下发 + AutoFlow 流程记录管理引擎。

    :param fw_main: FirewallMain 实例（提供 dev_info 和执行方法）
    """

    def __init__(self, fw_main):
        self.fw = fw_main

    def run(
        self,
        cmds,
        back_off_cmds,
        class_method: str,
        **flow_kwargs,
    ) -> AutoFlow:
        """
        执行配置下发，并更新 AutoFlow 流程记录状态。

        :param cmds: 下发命令（SSH 时为列表，Netconf 时为 XML）
        :param back_off_cmds: 回退命令
        :param class_method: 'Hillstone' = SSH；其他 = Netconf 类方法名
        :param flow_kwargs: 创建 AutoFlow 所需的字段（commit_user, task, device 等）
        :returns: 已更新的 AutoFlow 实例
        """
        from apps.automation.models import AutoEvent
        from apps.dcs_control.tasks import (
            run_cmd_config, run_netconf_config, send_msg_sec_manage
        )
        from utils.connect_layer.auto_main import HillstoneFsm

        # 处理 event_id → event 对象转换（与原 flow_engine 保持一致）
        if flow_kwargs.get('event_id'):
            event_id = flow_kwargs.pop('event_id')
            flow_kwargs['event'] = AutoEvent.objects.get(id=event_id)

        # 移除 flag 字段（不存入 AutoFlow）
        flag = flow_kwargs.pop('flag', None)

        # 获取设备实例 + 创建流程记录
        flow_record = AutoFlow.objects.create(**flow_kwargs)
        flow_record.approve()

        netmiko_error = netconf_error = path = ''
        res = False

        if class_method != 'Hillstone':
            # NETCONF 下发
            self.fw.dev_info['class_method'] = class_method
            self.fw.dev_info['cmd'] = cmds
            res, netconf_error = run_netconf_config(**self.fw.dev_info)
        else:
            # SSH 下发
            log.info('FlowEngine: 开始 SSH 配置下发')
            res, path, netmiko_error = run_cmd_config(*cmds, **self.fw.dev_info)
            if res:
                data_to_parse = default_storage.open(path).read()
                flow_record.task_result = data_to_parse.decode('utf-8')

        flow_record.publish()

        if res:
            _ttp_info = ''
            if class_method == 'Hillstone' or (path and path.endswith('.txt')):
                ttp_method = HillstoneFsm.get_map("standard")
                if ttp_method:
                    ttp_res = ttp_method(path=path)
                    _ttp_info = apply_ttp_result(flow_record, ttp_res)
            flow_record.save()

            task_name = flow_kwargs.get('task', '未知任务')
            commit_user = flow_kwargs.get('commit_user', '')
            device = flow_kwargs.get('device', '')

            if flow_record.state == 'Failed':
                msg = f"[操作{task_name}失败]\n用户:{commit_user}\n设备:{device}\n状态:{flow_record.state}\n错误:{_ttp_info}\n=========="
            elif flow_record.state == 'Published':
                msg = f"[操作{task_name}成功]\n用户:{commit_user}\n设备:{device}\n状态:发布生产\n=========="
            else:
                msg = f"[操作{task_name}]\n用户:{commit_user}\n设备:{device}\n状态:{flow_record.state}\n未能获取到状态信息\n=========="
            send_msg_sec_manage(msg)
        else:
            flow_record.failed()
            error_info = netconf_error if class_method != 'Hillstone' else netmiko_error
            flow_record.task_result = str(error_info)
            flow_record.save()

            task_name = flow_kwargs.get('task', '未知任务')
            commit_user = flow_kwargs.get('commit_user', '')
            device = flow_kwargs.get('device', '')
            msg = f"[操作{task_name}失败]\n用户:{commit_user}\n设备:{device}\n状态:发布失败\n错误:{error_info}\n=========="
            send_msg_sec_manage(msg)

        return flow_record

    @staticmethod
    def build_flow_data(self_task, post_param: dict, task_type: str, method: str = 'NETCONF') -> dict:
        """
        构建 AutoFlow.objects.create 所需的通用字段字典。

        :param self_task: Celery task 实例（提供 self.request.id）
        :param post_param: 来自 Celery 任务的 post_param 字典
        :param task_type: AutoFlowTasks 中定义的任务类型常量
        :param method: 'SSH' 或 'NETCONF'
        :returns: 可直接传入 FlowEngine.run(**flow_data) 的字典
        """
        import json as _json
        from apps.automation.models import AutoFlowTasks as _AFT

        return dict(
            order_code=post_param.get('order_code') or ' ',
            task_id=post_param.get('task_id') or str(self_task.request.id),
            origin=post_param.get('origin') or '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=post_param.get('task') or task_type,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=_json.dumps(post_param),
            method=method,
            event_id=post_param.get('event_id'),
        )
