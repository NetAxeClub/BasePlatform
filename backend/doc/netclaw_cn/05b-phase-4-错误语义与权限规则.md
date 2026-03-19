# Phase 4 错误语义与权限规则

## 1. 文档目的

本文件用于固定 Phase 4 当前的权限边界、重试语义和错误分类规则，作为 MCP / Skill 产品化的正式约束材料。

## 2. 权限规则

### 2.1 身份要求

所有 `agent/v1` tool 当前统一要求：

- 通过 `AgentRequestAuthentication`
- 必须是已认证 Django 用户或 `IamMiddleware` 注入的 `request.iam`

### 2.2 高风险工具

当前高风险工具：

- `change_run`

附加门禁：

- `approval_status = approved`
- `baseline_ref` 必填

### 2.3 低风险工具

当前低风险或中风险工具：

- `device_facts`
- `inspection_run`
- `security_audit_run`
- `execution_query`

这些工具虽然不要求审批，但仍需要 agent 身份。

## 3. 错误语义分类

当前统一错误码字典字段：

- `http_status`
- `retryable`
- `category`
- `recommended_action`

### 3.1 可重试错误

当前 catalog 中已登记的可重试错误示例：

- `UPSTREAM_TIMEOUT`
- `DEVICE_UNREACHABLE`

语义：

- 请求本身合法
- 后端依赖临时不可用或超时
- agent 可以在受限重试策略下重试

### 3.2 不可重试错误

当前 catalog 中已登记的不可重试错误示例：

- `DEVICE_NOT_FOUND`
- `INVALID_TARGET`
- `EXECUTION_NOT_FOUND`
- `APPROVAL_REQUIRED`
- `BASELINE_REQUIRED`
- `UNAUTHORIZED`
- `INVALID_SERIAL_NUM`
- `CHANGE_TEMPLATE_REQUIRED`
- `UNSUPPORTED_CHANGE_TEMPLATE`
- `INVALID_ANALYSIS_KIND`

语义：

- 请求本身不合法，或当前权限/门禁不满足
- agent 不应盲目重试
- 需要人工补输入、补审批或修正调用身份

### 3.3 人工介入错误

当前主要由变更主链体现：

- verify 失败但未自动 rollback 时，结果进入人工确认语义

当前最小表达方式：

- `status = PARTIAL_SUCCESS`
- `rollback_status = pending_manual_confirmation`

## 4. 限流规则

当前已同时固定 metadata 与运行时 enforcement：

| tool | burst | burst_window_seconds | sustained_per_minute | enforcement |
|---|---:|---:|---:|---|
| `device_facts` | 30 | 10 | 120 | enabled |
| `inspection_run` | 10 | 10 | 30 | enabled |
| `security_audit_run` | 10 | 10 | 20 | enabled |
| `change_run` | 3 | 10 | 10 | enabled |
| `execution_query` | 30 | 10 | 120 | enabled |

超限时统一返回：

- `error_code = RATE_LIMITED`
- `http_status = 429`
- `retryable = true`
- `category = throttle`

## 5. legacy 约束

以下模块不允许作为 tool 的直接能力来源：

- `automation`
- `monitor`
- `support`

规则：

- 不直接包装 legacy 路由为 tool
- 不直接引用 legacy 模型定义 tool 输入输出
- 不用 legacy app 的错误语义充当产品化标准

## 6. 证据引用

- `backend/apps/api/agent_views.py`
- `backend/apps/api/error_codes.py`
- `backend/apps/api/throttles.py`
- `backend/apps/api/tests_agent_v1.py`
