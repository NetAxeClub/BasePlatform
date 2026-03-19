from copy import deepcopy
from typing import Dict, Optional


ERROR_CODE_CATALOG = {
    "DEVICE_NOT_FOUND": {
        "http_status": 404,
        "retryable": False,
        "category": "resource",
        "recommended_action": "确认设备序列号或目标设备是否存在。",
    },
    "INVALID_TARGET": {
        "http_status": 400,
        "retryable": False,
        "category": "validation",
        "recommended_action": "补齐或修正目标设备、设备 IP 或序列号参数。",
    },
    "EXECUTION_NOT_FOUND": {
        "http_status": 404,
        "retryable": False,
        "category": "resource",
        "recommended_action": "确认 execution_id 是否正确，或等待执行记录落库后重试查询。",
    },
    "APPROVAL_REQUIRED": {
        "http_status": 400,
        "retryable": False,
        "category": "policy",
        "recommended_action": "先完成审批，再以 approved 状态重新发起变更。",
    },
    "BASELINE_REQUIRED": {
        "http_status": 400,
        "retryable": False,
        "category": "policy",
        "recommended_action": "先补齐 baseline_ref，再重新执行变更。",
    },
    "UNAUTHORIZED": {
        "http_status": 401,
        "retryable": False,
        "category": "auth",
        "recommended_action": "使用已认证的 agent 身份调用接口。",
    },
    "UPSTREAM_TIMEOUT": {
        "http_status": 504,
        "retryable": True,
        "category": "upstream",
        "recommended_action": "检查上游设备或依赖服务状态后按限流策略重试。",
    },
    "DEVICE_UNREACHABLE": {
        "http_status": 503,
        "retryable": True,
        "category": "upstream",
        "recommended_action": "确认设备在线和网络可达后再重试。",
    },
    "RATE_LIMITED": {
        "http_status": 429,
        "retryable": True,
        "category": "throttle",
        "recommended_action": "等待限流窗口结束后重试，避免并发突发调用。",
    },
    "INVALID_SERIAL_NUM": {
        "http_status": 400,
        "retryable": False,
        "category": "validation",
        "recommended_action": "修正 serial_num 格式后重试。",
    },
    "INVALID_ANALYSIS_KIND": {
        "http_status": 400,
        "retryable": False,
        "category": "validation",
        "recommended_action": "改用已注册的 analysis kind。",
    },
    "CHANGE_TEMPLATE_REQUIRED": {
        "http_status": 400,
        "retryable": False,
        "category": "validation",
        "recommended_action": "补齐 change_template 字段后重试。",
    },
    "UNSUPPORTED_CHANGE_TEMPLATE": {
        "http_status": 400,
        "retryable": False,
        "category": "validation",
        "recommended_action": "改用已注册的低风险变更模板编码。",
    },
}


def get_error_code_definition(code: str) -> Dict[str, object]:
    definition = deepcopy(ERROR_CODE_CATALOG.get(code, {}))
    if not definition:
        return {
            "http_status": 400,
            "retryable": False,
            "category": "unknown",
            "recommended_action": "检查调用参数与服务端日志。",
        }
    return definition


def build_error_summary(code: str, message: Optional[str] = None, **extra) -> Dict[str, object]:
    definition = get_error_code_definition(code)
    summary = {
        "error_code": code,
        "message": message or "",
        **definition,
    }
    if extra:
        summary.update(extra)
    return summary
