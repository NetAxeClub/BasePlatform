# Phase 0 附录 C：统一 Agent API 草案

## 1. 文档目的

本文件定义 NetClaw-CN 首期统一 agent API 合同，使后续工程师可以在不反查内部 app 细节的前提下实施统一入口。

## 2. 设计原则

- 统一入口优先，不直接暴露内部 app 原始接口
- 读写任务分离，事实查询与任务执行合同分开
- 输出字段稳定，便于 OpenClaw / MCP / Skill 统一消费
- 执行类接口统一返回任务与执行台账引用

## 3. 首期接口清单

| 方法 | 路径 | 任务类型 | 说明 |
|---|---|---|---|
| `GET` | `/agent/v1/devices/{serial_num}/facts` | `device_facts` | 查询单设备标准化事实 |
| `GET` | `/agent/v1/devices/{serial_num}/capabilities` | `device_facts` | 查询单设备能力画像与可执行能力 |
| `POST` | `/agent/v1/tasks/inspect` | `inspection_run` | 创建巡检任务 |
| `POST` | `/agent/v1/tasks/audit/security-policy` | `security_audit_run` | 创建安全策略审计任务 |
| `POST` | `/agent/v1/tasks/change` | `change_run` | 创建变更执行任务 |
| `GET` | `/agent/v1/executions/{id}` | `execution_query` | 查询统一执行状态 |

## 4. 任务类型定义

| 任务类型 | 归属领域 | 同步/异步 | 首期语义 |
|---|---|---|---|
| `device_facts` | `southbound_core` | 同步优先 | 获取设备事实与能力，不改变设备状态 |
| `inspection_run` | `ops_execution_center` + `network_intelligence_center` | 异步 | 发起巡检并返回执行引用 |
| `security_audit_run` | `ops_execution_center` + `security_policy_center` | 异步 | 发起安全策略审计并返回执行引用 |
| `change_run` | `ops_execution_center` | 异步 | 发起变更并返回执行引用、审计和回滚引用 |
| `execution_query` | `ops_execution_center` | 同步 | 查询任务执行生命周期与工件摘要 |

## 5. 统一输出字段合同

以下字段作为首期统一输出字段，执行类接口和执行查询接口必须兼容：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | `string` | 是 | agent 任务主键，标识用户请求 |
| `execution_id` | `string` | 否 | 执行台账主键；查询类 facts 可为空 |
| `status` | `string` | 是 | 统一状态，如 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`PARTIAL_SUCCESS` |
| `severity` | `string` | 否 | 风险或结果等级，如 `INFO`、`LOW`、`MEDIUM`、`HIGH`、`CRITICAL` |
| `summary` | `object` | 是 | 面向 agent 的摘要说明 |
| `artifacts` | `array` | 否 | 结果工件列表，如报告、差异、日志引用 |
| `audit_ref` | `string` | 否 | 安全审计或执行审计引用 |
| `rollback_ref` | `string` | 否 | 回滚计划或回滚执行引用 |

## 6. 响应结构建议

### 6.1 `GET /agent/v1/devices/{serial_num}/facts`

```json
{
  "task_id": "facts-20260319-0001",
  "execution_id": null,
  "status": "SUCCEEDED",
  "severity": "INFO",
  "summary": {
    "serial_num": "SN123456",
    "vendor": "h3c",
    "facts_version": "2026-03-19T10:00:00+08:00",
    "collected_from": "device_api"
  },
  "artifacts": [
    {
      "type": "facts_snapshot",
      "ref": "facts://device/SN123456/20260319T100000"
    }
  ],
  "audit_ref": null,
  "rollback_ref": null
}
```

### 6.2 `POST /agent/v1/tasks/inspect`

```json
{
  "task_id": "inspect-20260319-0001",
  "execution_id": "exec-20260319-0001",
  "status": "PENDING",
  "severity": "INFO",
  "summary": {
    "task_type": "inspection_run",
    "target_count": 12,
    "triggered_by": "agent"
  },
  "artifacts": [],
  "audit_ref": "audit://inspection/exec-20260319-0001",
  "rollback_ref": null
}
```

### 6.3 `GET /agent/v1/executions/{id}`

```json
{
  "task_id": "change-20260319-0001",
  "execution_id": "exec-20260319-0008",
  "status": "RUNNING",
  "severity": "MEDIUM",
  "summary": {
    "task_type": "change_run",
    "current_stage": "verify",
    "progress": "3/5"
  },
  "artifacts": [
    {
      "type": "stage_log",
      "ref": "log://execution/exec-20260319-0008/verify"
    }
  ],
  "audit_ref": "audit://change/exec-20260319-0008",
  "rollback_ref": "rollback://change/exec-20260319-0008"
}
```

## 7. 字段约束

1. `summary` 必须是面向 agent 的稳定结构，不能直接透传内部 serializer 原文。
2. `artifacts` 只暴露引用和摘要，不直接内嵌过大原始数据。
3. `audit_ref` 与 `rollback_ref` 即使暂未完全实现，也必须保留合同位置。
4. `execution_query` 必须能兼容巡检、安全审计、变更三类异步任务。

## 8. 错误响应约定

建议统一错误结构：

```json
{
  "task_id": null,
  "execution_id": null,
  "status": "FAILED",
  "severity": "MEDIUM",
  "summary": {
    "error_code": "DEVICE_NOT_FOUND",
    "message": "device serial_num does not exist"
  },
  "artifacts": [],
  "audit_ref": null,
  "rollback_ref": null
}
```

## 9. 与当前仓库现状的一致性说明

- `device_api` 已具备承接 `facts` 与设备能力主链的基础条件。
- `workflow_center` 需要在后续 phase 内补齐统一执行台账模型，但 Phase 0 已固定其目标角色。
- `dcs_control` 与 `network_analysis` 当前尚未通过统一 agent API 暴露；本文件用于约束后续出口，而非描述现状接口。

## 10. 已知限制

- 本草案不定义最终鉴权、分页和批量过滤细节，后续在实现阶段细化。
- 本草案不要求 Phase 0 直接产出完整 DRF 代码，只要求输出足够稳定的实施合同。
