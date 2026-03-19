# Phase 1 巡检与安全审计回放证据

## 1. 文档目的

本文件用于整理 Phase 1 当前已经具备的巡检与安全审计回放证据，并明确哪些证据已经具备，哪些仍然不足以关闭 `RID-P1-002`。

## 2. 当前已具备的回放路径

### 2.1 巡检写入与回查链路

当前链路：

1. `POST /base_platform/agent/v1/tasks/inspect/`
2. 写入 `workflow_center.WorkflowExecution`
3. `GET /base_platform/agent/v1/executions/{id}/`
4. 返回 `inspection_payload` / `inspection_summary` / `audit_ref`

对应代码：

- `backend/apps/api/agent_views.py`
- `backend/apps/workflow_center/views.py`
- `backend/apps/workflow_center/serializers.py`

当前已有测试证据：

- `apps.api.tests_agent_v1.AgentApiViewTests.test_inspection_view_supports_partial_success`
- `apps.api.tests_agent_v1.AgentApiViewTests.test_execution_detail_view_returns_standardized_execution_payload`
- `apps.workflow_center.tests.WorkflowCenterExecutionTests.test_write_inspection_result_action_creates_workflow_execution`
- `apps.workflow_center.tests.WorkflowCenterExecutionTests.test_inspection_detail_action_returns_payload`

### 2.2 安全审计写入与回查链路

当前链路：

1. `POST /base_platform/agent/v1/tasks/audit/security-policy/`
2. 写入 `dcs_control.FirewallPolicyAuditRecord`
3. 同步写入 `workflow_center.WorkflowExecution`
4. 通过 `audit_ref` / `execution_id` 进行追溯

对应代码：

- `backend/apps/api/agent_views.py`
- `backend/apps/dcs_control/views.py`
- `backend/apps/dcs_control/models.py`

当前已有测试证据：

- `apps.api.tests_agent_v1.AgentApiViewTests.test_security_audit_view_returns_audit_ref`
- `apps.dcs_control.tests.DcsControlPolicyAuditTests.test_sec_policy_audit_view_filters_vendor_and_returns_payload`
- `apps.dcs_control.tests.DcsControlPolicyAuditTests.test_sec_policy_audit_record_view_creates_record_from_device_snapshot`

## 3. 当前证据的局限性

虽然上述链路已具备“写入 + 回查”的合同级证据，但当前仍有两个不足：

1. 回放主要来自 `SimpleTestCase + patch` 的合同测试，不是基于真实数据库数据的端到端回放。
2. 缺少一份正式的运行截图/录屏/真实请求响应记录，来证明验收所要求的“单设备巡检成功”和“安全审计结果回放”在真实数据上下文里成立。

因此，本文件只能证明：

- 链路设计已打通
- 合同字段已稳定
- 回查路径存在

但还不能单独证明：

- Phase 1 已满足验收要求中的“真实回放证据”

## 4. 当前可作为正式证据引用的测试

建议在复验时引用以下命令：

```bash
python3 backend/manage.py test apps.api.tests_agent_v1 -v 2
python3 backend/manage.py test apps.workflow_center.tests apps.dcs_control.tests -v 2
```

已新增但当前未跑通的数据库级回放测试：

- `backend/apps/api/tests_agent_v1_integration.py`

尝试执行命令：

```bash
python3 backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb
```

当前执行结果：

- 未进入用例断言阶段，先被测试库 schema 漂移阻塞
- 具体错误：`django.db.utils.OperationalError: (1054, "Unknown column 'config_compliance.intent' in 'field list'")`

该结果说明：

- Phase 1 当前仍缺“数据库级真实回放证据”
- 阻塞原因已经从“没有尝试”收敛为“测试底座 schema 不一致”

建议重点引用的测试名称：

- `test_inspection_view_supports_partial_success`
- `test_execution_detail_view_returns_standardized_execution_payload`
- `test_write_inspection_result_action_creates_workflow_execution`
- `test_inspection_detail_action_returns_payload`
- `test_security_audit_view_returns_audit_ref`
- `test_sec_policy_audit_record_view_creates_record_from_device_snapshot`

## 5. 对 RID-P1-002 的结论

当前状态：

- 国产主厂商覆盖清单：已补齐，见 `02b-phase-1-国产主厂商覆盖清单.md`
- 巡检与安全审计回放链路：已补齐合同级证据
- 数据库级真实回放测试：已编写，但受测试底座 schema 漂移阻塞，尚未形成可提交的通过证据
- 真实回放证据：仍缺

因此 `RID-P1-002` 当前只能视为“部分整改”，还不能关闭。

## 6. 证据引用

- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
- `backend/apps/workflow_center/tests.py`
- `backend/apps/dcs_control/tests.py`
- `backend/apps/api/agent_views.py`
- `backend/apps/workflow_center/views.py`
- `backend/apps/dcs_control/views.py`
