# Phase 2 低风险变更模板清单

## 1. 文档目的

本文件用于定义 Phase 2 当前纳入统一变更主链的低风险模板范围，作为 `change_run` 后续扩展和验收边界的正式依据。

## 2. 当前模板清单

| 模板编码 | 类型 | 当前主承接模块 | 当前状态 | 说明 |
|---|---|---|---|---|
| `sec_policy_low_risk` | 防火墙策略类 | `apps.dcs_control` | 已接入 `change_run` 最小合同 | 当前作为 Phase 2 默认低风险模板 |
| `address_object_low_risk` | 地址对象类 | `apps.dcs_control` | 已接入统一 `change_run` | 复用地址对象执行链语义，统一回放到 `change_run` ledger |
| `service_object_low_risk` | 服务对象类 | `apps.dcs_control` | 已接入统一 `change_run` | 复用服务对象执行链语义，统一回放到 `change_run` ledger |
| `dnat_low_risk` | DNAT 类 | `apps.dcs_control` | 已接入统一 `change_run` | 复用 DNAT 执行链语义，统一回放到 `change_run` ledger |

## 3. 当前已验证模板

### 3.1 已验证模板

当前 4 个低风险模板都已具备：

- 审批门禁
- baseline 引用
- verify 结果合同
- rollback 引用
- execution ledger 回放
- 统一输出字段：`baseline_ref`、`verify_ref`、`rollback_ref`、`rollback_status`、`audit_ref`

当前已覆盖场景：

- verify 成功闭环
- verify 失败后回滚

对应证据：

- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`

## 4. 模板注册元数据

当前统一注册字段：

- `code`
- `display_name`
- `category`
- `workflow_task`
- `risk_level`
- `supports_rollback`

注册代码落点：

- `backend/apps/api/change_templates.py`

## 5. 后续扩展优先级

优先级建议：

1. 保持现有 4 个模板的合同稳定
2. 如需新增模板，优先按注册表方式扩展
3. 继续补齐更贴近真实执行链的模板级审计字段

原因：

- 当前低风险模板覆盖面已满足 Phase 2 豁免关闭条件
- 后续扩展应避免重新引入硬编码模板分支

## 6. 不纳入当前范围的模板

以下类型不纳入当前 Phase 2 最小验收范围：

- 高风险大批量配置模板
- 拓扑/漂移相关变更
- 需要复杂厂商差异适配的路由/接口模板

## 7. 证据引用

- `backend/apps/dcs_control/tasks.py`
- `backend/apps/api/change_templates.py`
- `backend/apps/api/agent_views.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
