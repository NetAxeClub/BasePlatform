# Phase 1 完成包与自查记录

## 1. 文档目的

本文件用于整理 Phase 1 当前实现的完成包输入项，并给出研发侧 gate 自查结论，供正式验收直接使用。

本文件不是最终验收结论，最终放行仍以验收负责人回写的阶段结论为准。

## 2. 代码范围

本轮 Phase 1 新增或修改的核心范围如下：

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/netaxe/urls.py`

文档同步范围：

- `backend/doc/netclaw_cn/02-phase-1-巡检与事实主链.md`
- `backend/doc/netclaw_cn/02b-phase-1-国产主厂商覆盖清单.md`
- `backend/doc/netclaw_cn/02c-phase-1-巡检与安全审计回放证据.md`
- `backend/doc/netclaw_cn/README.md`
- `backend/doc/netclaw_cn/07-风险台账与豁免记录.md`

## 3. 已完成需求清单

### 3.1 设备 facts / capabilities 统一出口

已完成：

- `GET /base_platform/agent/v1/devices/{serial_num}/facts/`
- `GET /base_platform/agent/v1/devices/{serial_num}/capabilities/`

实现要点：

- facts 输出统一 `task_id`、`status`、`severity`、`summary`、`artifacts`
- capabilities 输出统一阻塞原因 `blocking_reasons`
- 未覆盖画像设备返回可解释阻塞原因，如 `profile_not_matched`

### 3.2 inspection 统一任务合同

已完成：

- `POST /base_platform/agent/v1/tasks/inspect/`
- `GET /base_platform/agent/v1/executions/{id}/`

实现要点：

- inspection 结果统一写入 `workflow_center.WorkflowExecution`
- 支持批量目标的 `PARTIAL_SUCCESS`
- execution 详情可回查 `summary`、inspection payload 和 `audit_ref`

### 3.3 network analysis 聚合出口

已完成：

- `GET /base_platform/agent/v1/analysis/?kind=interface_utilization`
- `GET /base_platform/agent/v1/analysis/?kind=address_tracking`

实现要点：

- 对外暴露统一 analysis 视图
- 聚合 `InterfaceUtilizationSnapshot` / `AddressTraceSnapshot`
- 结果工件中保留 `analysis_run` 和 `source_execute_time` 引用

### 3.4 security audit 统一出口

已完成：

- `POST /base_platform/agent/v1/tasks/audit/security-policy/`

实现要点：

- 统一安全策略审计输出
- 自动写入 `FirewallPolicyAuditRecord`
- 自动写入 `WorkflowExecution` 形成 execution / audit 最小闭环

## 4. 接口清单与示例响应摘要

### 4.1 facts

路径：

- `GET /base_platform/agent/v1/devices/{serial_num}/facts/`

摘要字段：

- `summary.serial_num`
- `summary.vendor`
- `summary.profile_code`
- `payload.legacy_plan_name`

### 4.2 capabilities

路径：

- `GET /base_platform/agent/v1/devices/{serial_num}/capabilities/`

摘要字段：

- `summary.supported_collection_types`
- `payload.blocking_reasons`
- `payload.is_ready`

### 4.3 inspect

路径：

- `POST /base_platform/agent/v1/tasks/inspect/`

摘要字段：

- `execution_id`
- `status`
- `summary.ready_count`
- `summary.blocked_count`
- `payload.results`

### 4.4 analysis

路径：

- `GET /base_platform/agent/v1/analysis/?kind=interface_utilization`
- `GET /base_platform/agent/v1/analysis/?kind=address_tracking`

摘要字段：

- `summary.analysis_kind`
- `summary.count`
- `artifacts[].ref`

### 4.5 security audit

路径：

- `POST /base_platform/agent/v1/tasks/audit/security-policy/`

摘要字段：

- `execution_id`
- `audit_ref`
- `summary.permit_any_any_count`
- `summary.high_risk_service_rule_count`

## 5. 测试报告

### 5.1 已执行验证

- `python3 -m py_compile backend/apps/api/agent_views.py backend/apps/api/agent_urls.py backend/apps/api/tests_agent_v1.py backend/netaxe/urls.py`
- `python3 backend/manage.py test apps.api.tests_agent_v1 apps.workflow_center.test_netclaw_boundary -v 2`

### 5.2 已覆盖场景

| 场景 | 覆盖方式 | 结果 |
|---|---|---|
| 单设备 facts 查询 | `apps.api.tests_agent_v1.AgentApiViewTests.test_device_facts_view_returns_standard_contract` | 通过 |
| 单设备 capabilities 查询 | `apps.api.tests_agent_v1.AgentApiViewTests.test_device_capabilities_view_returns_blocking_reasons` | 通过 |
| 批量巡检 partial | `apps.api.tests_agent_v1.AgentApiViewTests.test_inspection_view_supports_partial_success` | 通过 |
| execution ledger 回查 | `apps.api.tests_agent_v1.AgentApiViewTests.test_execution_detail_view_returns_standardized_execution_payload` | 通过 |
| analysis 聚合出口 | `apps.api.tests_agent_v1.AgentApiViewTests.test_analysis_view_returns_unified_payload` | 通过 |
| security audit 统一出口 | `apps.api.tests_agent_v1.AgentApiViewTests.test_security_audit_view_returns_audit_ref` | 通过 |
| agent 路由稳定性 | `apps.api.tests_agent_v1.AgentApiRouteTests.test_agent_v1_routes_resolve_to_expected_views` | 通过 |
| 匿名访问拒绝 | `apps.api.tests_agent_v1.AgentApiViewTests.test_device_facts_view_rejects_anonymous_request` / `test_security_audit_view_rejects_anonymous_request` | 通过 |
| IAM 身份访问通过 | `apps.api.tests_agent_v1.AgentApiViewTests.test_device_facts_view_accepts_iam_identity` | 通过 |

### 5.3 当前未覆盖项

- 未执行真实数据库集成场景下的单设备巡检成功回放
- 未执行基于真实 `AnalysisRun` / `FirewallPolicyAuditRecord` 数据的端到端回放

当前已知阻塞：

- 已新增 `backend/apps/api/tests_agent_v1_integration.py` 用于数据库级回放验证
- 执行 `python3 backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb` 时，被测试库 schema 漂移阻塞，错误为 `Unknown column 'config_compliance.intent' in 'field list'`

以上未覆盖项当前不影响“开发完成”，但会影响正式 gate 验收是否可直接 `PASS`。

## 6. 风险说明

### 6.1 已登记风险

- `RISK-P1-001`：统一只读出口仅是薄包装，底层耦合仍暴露

### 6.2 当前残余问题

- `agent/v1` 入口已补齐最小认证链，但当前统一出口大量复用了既有模块模型和服务，架构上仍属于聚合层，不等于底层已完全解耦。
- inspection / audit / analysis 的实现目前以最小闭环为目标，尚未完成更强的真实回放证据。
- 国产主厂商基线覆盖清单已补齐，但 ZTE / Centec 当前仅能证明“画像已定义”，尚无本轮线上样本覆盖证据。

## 7. 回滚方案

- 本轮新增的是聚合只读入口与测试，不改变现有内部 app 历史出口。
- 如需回滚，可直接移除：
  - `backend/apps/api/agent_views.py`
  - `backend/apps/api/agent_urls.py`
  - `backend/apps/api/tests_agent_v1.py`
  - `backend/netaxe/urls.py` 中 `base_platform/agent/v1/` 路由

## 8. 遗留问题

- 需要补真实数据或更强集成测试，验证单设备巡检成功和安全审计回放。
- 需要先修复测试底座 schema 漂移，才能让数据库级回放测试产出正式证据。
- 需要在正式 gate 审查时确认统一出口是否已经足够避免 agent 侧继续拼接内部多个只读接口。

## 9. 验收标准逐条自查

| 验收标准 | 当前判断 | 说明 |
|---|---|---|
| 权限与审计链完整 | 部分完成 | `agent/v1` 已补齐认证与匿名拒绝测试，但仍需结合真实回放证据一并复验 |
| 单设备巡检成功 | 部分完成 | 合同和 execution ledger 已打通，但当前证据主要来自合同级测试，缺少真实回放证据 |
| 批量巡检支持 `partial` | 通过 | 已有统一合同测试覆盖 |
| 结果可追溯到 execution、audit、artifacts | 通过 | inspection 和 security audit 都返回 execution / audit / artifacts 引用 |
| facts / capabilities 输出合同稳定 | 通过 | 已有统一合同和路由测试 |
| 安全审计输出合同稳定 | 通过 | 已有统一合同测试 |
| 国产主厂商画像与默认绑定结果可解释 | 通过 | 已补覆盖清单，见 `02b-phase-1-国产主厂商覆盖清单.md` |
| agent 不再需要直接拼接内部多个只读接口 | 通过 | 已新增 `/base_platform/agent/v1` 聚合入口承接主场景 |

## 10. 研发侧建议结论

- 建议状态：`IN_REVIEW`
- 建议 gate 结论：`PASS_WITH_WAIVER`

建议原因：

- 核心只读主链与统一合同已经落地并通过定向测试
- 当前剩余问题主要集中在更强集成证据和厂商覆盖清单，属于可登记、可限界的残余风险
- 在未补强这些证据前，不建议直接给 `PASS`

## 11. 证据引用

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/netaxe/urls.py`
- `python3 backend/manage.py test apps.api.tests_agent_v1 apps.workflow_center.test_netclaw_boundary -v 2`
- `02b-phase-1-国产主厂商覆盖清单.md`
- `02c-phase-1-巡检与安全审计回放证据.md`
