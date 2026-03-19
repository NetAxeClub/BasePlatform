# Phase 2 审计留痕字段规范

## 1. 文档目的

本文件用于固定 Phase 2 变更治理主链的审计留痕字段规范，确保 `change_run` 对 agent 可解释，并且 execution ledger 可完整回放审批、执行、验证和回滚过程。

## 2. 字段分类

### 2.1 顶层统一输出字段

| 字段 | 说明 | 当前来源 |
|---|---|---|
| `task_id` | 变更任务标识 | `agent_views.change_run` |
| `execution_id` | execution ledger 主键 | `workflow_center.WorkflowExecution.id` |
| `status` | 变更状态 | `WorkflowExecution.state` + `agent` 状态映射 |
| `severity` | 风险或执行结果等级 | `change_run` 合同摘要 |
| `summary` | 面向 agent 的变更摘要 | `change_summary` |
| `artifacts` | 关键工件引用 | baseline / verify / rollback / execution |
| `audit_ref` | 变更审计引用 | `audit://change/{task_id}` |
| `rollback_ref` | 回滚引用 | `rollback://{task_id}` |

### 2.2 execution ledger 必留字段

| 字段 | 说明 | 当前载体 |
|---|---|---|
| `order_code` | 工单号 | `WorkflowExecution.order_code` |
| `commit_user` | 执行人/触发人 | `WorkflowExecution.commit_user` |
| `origin` | 触发源 | `WorkflowExecution.origin` |
| `remote_ip` | 调用来源 IP | `WorkflowExecution.remote_ip` |
| `task` | 任务模块 | `WorkflowExecution.task` |
| `state` | 流程状态 | `WorkflowExecution.state` |
| `commands` | 执行命令 | `WorkflowExecution.commands` |
| `back_off_commands` | 回滚命令 | `WorkflowExecution.back_off_commands` |
| `kwargs` | 任务上下文 | `WorkflowExecution.kwargs` |
| `task_result` | 结果详情 | `WorkflowExecution.task_result` |

### 2.3 `change_summary` 必留字段

| 字段 | 说明 |
|---|---|
| `task_type` | 固定为 `change_run` |
| `change_template` | 变更模板编码 |
| `approval_status` | 审批状态 |
| `baseline_ref` | 基线引用 |
| `verify_ref` | 验证引用 |
| `rollback_ref` | 回滚引用 |
| `verify_passed` | 验证是否通过 |
| `rollback_status` | 回滚结果，如 `executed` / `pending_manual_confirmation` |
| `result` | 当前结果摘要 |
| `order_code` | 工单号 |
| `risk_level` | 风险等级 |
| `triggered_by` | 触发源 |

## 3. 当前状态映射规范

| Workflow 状态 | Agent 状态 | 说明 |
|---|---|---|
| `Draft` | `PENDING` | 草稿或未执行 |
| `Approved` | `RUNNING` | 已审批待执行 |
| `Published` | `RUNNING` | 执行中 |
| `running` | `RUNNING` | Phase 2 新状态 |
| `verifying` | `VERIFYING` | 验证中 |
| `succeeded` / `Finish` | `SUCCEEDED` | 成功闭环 |
| `partial` | `PARTIAL_SUCCESS` | 部分成功 |
| `failed` / `Failed` | `FAILED` | 执行失败 |
| `rolled_back` | `ROLLED_BACK` | 已回滚 |
| `cancelled` | `CANCELLED` | 已取消 |

## 4. 当前回放链路

### 4.1 正常变更

1. `POST /base_platform/agent/v1/tasks/change/`
2. 写入 `WorkflowExecution`
3. 返回 `baseline_ref` / `verify_ref` / `rollback_ref` / `audit_ref`
4. `GET /base_platform/agent/v1/executions/{id}/` 回查

### 4.2 失败回滚

1. `verify.passed = false`
2. `rollback_requested = true`
3. execution 状态写为 `rolled_back`
4. 回查时 `status = ROLLED_BACK`

## 5. 证据引用

- `backend/apps/api/agent_views.py`
- `backend/apps/workflow_center/models.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
