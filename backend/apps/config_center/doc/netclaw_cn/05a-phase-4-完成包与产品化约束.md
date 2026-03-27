# Phase 4 完成包与产品化约束

## 1. 文档目的

本文件用于整理 Phase 4 当前已落地的主链产品化能力、tool schema 入口和接入约束，作为后续正式验收的输入材料。

## 2. 代码范围

当前 Phase 4 相关代码范围：

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`

## 3. 已完成需求清单

### 3.1 MCP tool schema 出口

已完成：

- `GET /base_platform/agent/v1/tools/catalog/`

当前提供的工具元数据：

- `device_facts`
- `inspection_run`
- `security_audit_run`
- `change_run`
- `execution_query`

### 3.2 权限边界

当前已具备：

- 所有 `agent/v1` tool 均要求 agent 身份
- `change_run` 明确标记为高风险工具
- `change_run` 在执行层要求 `approval_status` 和 `baseline_ref`

### 3.3 限流与幂等

当前已具备：

- tool catalog 中已明确每类工具的 `burst` / `sustained_per_minute`
- `device_facts`、`inspection_run`、`security_audit_run`、`change_run`、`execution_query` 已下沉为运行时 enforcement
- 运行时同时返回统一 `RATE_LIMITED` 错误语义，供 MCP / Skill 侧机器消费
- `change_run`、`inspection_run` 继续依赖 `task_id` / execution ledger 做幂等追踪

### 3.4 错误语义

当前已具备：

- tool catalog 区分 `retryable_errors` 与 `non_retryable_errors`
- 已落地统一错误码字典，并复用于 catalog 与接口错误返回
- 高风险变更门禁错误已显式映射为 `APPROVAL_REQUIRED` / `BASELINE_REQUIRED`

## 4. 接入约束

当前固定约束：

1. agent / MCP / Skill 不直接拼接内部 app 接口。
2. `automation`、`monitor`、`support` 不允许作为 tool schema、权限模型、错误语义或验收样例来源。
3. tool 只能消费主链模块暴露的统一合同。
4. 高风险变更必须经过 `change_run` 的审批和 baseline 门禁。

## 5. 当前输出入口

| 入口 | 用途 |
|---|---|
| `/base_platform/agent/v1/tools/catalog/` | tool schema / metadata 目录 |
| `/base_platform/agent/v1/devices/{serial_num}/facts/` | facts tool |
| `/base_platform/agent/v1/tasks/inspect/` | inspection tool |
| `/base_platform/agent/v1/tasks/audit/security-policy/` | security audit tool |
| `/base_platform/agent/v1/tasks/change/` | change tool |
| `/base_platform/agent/v1/executions/{id}/` | execution query tool |

## 6. 当前未覆盖项

- 当前尚未直接产出 MCP server 代码，只完成了 Phase 4 所需的产品化边界与 tool schema 基线
- 未认证请求当前仍依赖 DRF 默认拒绝结构，尚未统一转换为自定义错误体
- 限流当前落在 `agent/v1` 视图层，而非独立网关或中间件层

## 7. 证据引用

- `backend/apps/api/agent_views.py`
- `backend/apps/api/error_codes.py`
- `backend/apps/api/throttles.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
