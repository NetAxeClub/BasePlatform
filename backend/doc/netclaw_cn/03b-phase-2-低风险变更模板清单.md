# Phase 2 低风险变更模板清单

## 1. 文档目的

本文件用于定义 Phase 2 当前纳入统一变更主链的低风险模板范围，作为 `change_run` 后续扩展和验收边界的正式依据。

## 2. 当前模板清单

| 模板编码 | 类型 | 当前主承接模块 | 当前状态 | 说明 |
|---|---|---|---|---|
| `sec_policy_low_risk` | 防火墙策略类 | `apps.dcs_control` | 已接入 `change_run` 最小合同 | 当前作为 Phase 2 默认低风险模板 |
| `address_object_low_risk` | 地址对象类 | `apps.dcs_control` | 现有执行链存在，待下一轮接入统一 `change_run` | 可复用 `address_set` 执行链 |
| `service_object_low_risk` | 服务对象类 | `apps.dcs_control` | 现有执行链存在，待下一轮接入统一 `change_run` | 可复用 `service_set` 执行链 |
| `dnat_low_risk` | DNAT 类 | `apps.dcs_control` | 现有执行链存在，待下一轮接入统一 `change_run` | 可复用 `config_dnat` / `DestAddTranslate` |

## 3. 当前已验证模板

### 3.1 `sec_policy_low_risk`

当前已具备：

- 审批门禁
- baseline 引用
- verify 结果合同
- rollback 引用
- execution ledger 回放

当前已覆盖场景：

- verify 成功闭环
- verify 失败后回滚

对应证据：

- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`

## 4. 后续扩展优先级

优先级建议：

1. `address_object_low_risk`
2. `service_object_low_risk`
3. `dnat_low_risk`

原因：

- 三者都已有 `dcs_control` 执行链，可优先接入统一变更合同
- 它们与防火墙策略类共享较多审计字段和执行闭环结构

## 5. 不纳入当前范围的模板

以下类型不纳入当前 Phase 2 最小验收范围：

- 高风险大批量配置模板
- 拓扑/漂移相关变更
- 需要复杂厂商差异适配的路由/接口模板

## 6. 证据引用

- `backend/apps/dcs_control/tasks.py`
- `backend/apps/api/agent_views.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
