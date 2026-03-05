# -*- coding: utf-8 -*-
"""
TTP 解析结果处理工具。

原 SecFirewallMain.flow_engine 和 FirewallMain.flow_engine 中各有约 40 行
完全相同的 TTP 错误提取逻辑，提取至此处统一维护。
"""
import logging

log = logging.getLogger(__name__)


def extract_ttp_error(ttp_res: dict) -> str:
    """
    从 TTP 解析结果字典中提取人类可读的错误描述字符串。
    返回空字符串表示无错误。

    :param ttp_res: HillstoneFsm 返回的解析结果字典
    :return: 错误描述字符串，无错误时为 ''
    """
    if not isinstance(ttp_res, dict):
        return ''

    if 'unrecognized' in ttp_res:
        val = ttp_res['unrecognized']
        if isinstance(val, dict):
            inner = val.get('unrecognized', val)
            if isinstance(inner, list):
                return 'unrecognized: ' + ' '.join(str(x) for x in inner)
            return 'unrecognized: ' + str(inner)
        if isinstance(val, list):
            return 'unrecognized: ' + '\n'.join(
                str(x.get('unrecognized', x)) for x in val)
        return 'unrecognized: ' + str(val)

    if 'incomplete' in ttp_res:
        val = ttp_res['incomplete']
        if isinstance(val, dict):
            return 'incomplete: ' + str(val.get('incomplete', val))
        if isinstance(val, list):
            return 'incomplete: ' + '\n'.join(
                str(x.get('incomplete', x)) for x in val)
        return 'incomplete: ' + str(val)

    if 'errors' in ttp_res:
        val = ttp_res['errors']
        if isinstance(val, dict):
            return 'error: ' + str(val.get('error', val))
        if isinstance(val, list):
            unique_errors = list(set(str(x.get('error', x)) for x in val))
            return 'error: ' + '\n'.join(unique_errors)
        return 'error: ' + str(val)

    if 'warning' in ttp_res:
        val = ttp_res['warning']
        if isinstance(val, dict):
            return 'warning: ' + str(val.get('error', val))
        return 'warning: ' + str(val)

    if 'wrong_parameter' in ttp_res:
        val = ttp_res['wrong_parameter']
        if isinstance(val, dict):
            return 'wrong_parameter: ' + str(val.get('wrong_parameter', val))
        return 'wrong_parameter: ' + str(val)

    return ''


def apply_ttp_result(flow_record, ttp_res: dict) -> str:
    """
    将 TTP 解析结果应用到流程记录：
    - 若有错误，调用 flow_record.failed() 并返回错误信息
    - 无论是否出错，均将原始 ttp_res JSON 写入 flow_record.ttp

    :param flow_record: AutoFlow 实例
    :param ttp_res: HillstoneFsm 返回的解析结果字典
    :return: 错误描述字符串，无错误时为 ''
    """
    import json
    error_keys = ('unrecognized', 'incomplete', 'errors', 'warning', 'wrong_parameter')
    _ttp_info = ''

    if isinstance(ttp_res, dict):
        for key in error_keys:
            if key in ttp_res:
                flow_record.failed()
                _ttp_info = extract_ttp_error(ttp_res)
                log.warning("TTP 解析发现错误 [%s]: %s", key, _ttp_info)
                break
        flow_record.ttp = json.dumps(ttp_res)

    return _ttp_info
