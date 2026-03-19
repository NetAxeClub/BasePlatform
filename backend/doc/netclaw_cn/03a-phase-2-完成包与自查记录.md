# Phase 2 完成包与自查记录

## 1. 文档目的

本文件用于记录 Phase 2 当前已完成的最小实现、自查结果和测试证据，作为后续正式 gate 验收的输入材料。

## 2. 代码范围

当前 Phase 2 变更范围：

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
- `backend/apps/workflow_center/models.py`
- `backend/doc/netclaw_cn/03b-phase-2-低风险变更模板清单.md`
- `backend/doc/netclaw_cn/03c-phase-2-审计留痕字段规范.md`

## 3. 已完成需求清单

### 3.1 `change_run` 统一任务合同

已完成：

- `POST /base_platform/agent/v1/tasks/change/`

当前合同字段：

- `task_id`
- `execution_id`
- `status`
- `severity`
- `summary`
- `artifacts`
- `audit_ref`
- `rollback_ref`

### 3.2 execution 状态机最小实现

当前已支持：

- `draft`
- `approved`
- `running`
- `verifying`
- `succeeded`
- `partial`
- `failed`
- `rolled_back`
- `cancelled`

当前 Phase 2 实际已使用的主路径状态：

- `succeeded`
- `rolled_back`

### 3.3 baseline / verify / rollback 引用

当前已具备：

- `baseline_ref`
- `verify_ref`
- `rollback_ref`
- `audit_ref`

### 3.4 审批与门禁

当前已具备硬门禁：

- 无审批不能执行
- 无 baseline 不能执行
- verify 失败时必须 rollback 或人工挂起

### 3.5 低风险模板与审计规范

当前已补齐文档：

- `03b-phase-2-低风险变更模板清单.md`
- `03c-phase-2-审计留痕字段规范.md`

## 4. 测试报告

### 4.1 已执行验证

- `backend/venv/bin/python -m py_compile backend/apps/api/agent_views.py backend/apps/api/agent_urls.py backend/apps/api/tests_agent_v1.py backend/apps/workflow_center/models.py`
- `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
- `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb`

### 4.2 当前已覆盖场景

| 场景 | 覆盖方式 | 结果 |
|---|---|---|
| 无审批禁止执行 | `test_change_view_blocks_execution_without_approval` | 通过 |
| 无 baseline 禁止执行 | `test_change_view_blocks_execution_without_baseline` | 通过 |
| verify 成功时闭环 | `test_change_view_returns_succeeded_when_verify_passes` | 通过 |
| verify 失败时 rollback | `test_change_view_rolls_back_when_verify_fails` | 通过 |
| 正常变更数据库级回放 | `test_change_task_persists_execution_and_verify_success_can_be_replayed` | 通过 |
| 失败变更数据库级回滚回放 | `test_change_task_persists_execution_and_failed_verify_rolls_back` | 通过 |

### 4.3 当前未覆盖项

- 当前数据库级回放测试提示 `automation`、`django_celery_beat`、`django_celery_results`、`network_analysis`、`workflow_center` 存在未生成 migration 的模型变更警告
- 在本次正式验收复核中，`backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb` 因无法连接配置的 MySQL 主机而执行失败，数据库级回放证据未能在当前环境重放成功

## 5. 风险说明

当前对应风险：

- `RISK-P2-001`：审批、baseline、verify、rollback 只具字段不具门禁

当前缓解状态：

- 已从“仅字段存在”推进到“有硬门禁和状态闭环”
- 但数据库级回放与低风险模板清单仍未形成完整验收包

## 6. 自查结论

当前判断：

- Phase 2 已进入 `IN_PROGRESS`
- `change_run` 最小合同、门禁和数据库级回放证据已落地
- 当前尚不满足正式验收条件

主要剩余项：

- gate 自查记录
- 正式验收结论
