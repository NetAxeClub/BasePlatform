# Phase 2：变更治理主链

## 1. 阶段目标

本阶段目标是完成 NetClaw-CN 在 NetAxe backend 侧的统一变更主链，形成审批、执行、验证、回滚和审计留痕的闭环。

## 2. 阶段范围

- `change_run` 统一任务合同
- execution 状态机
- baseline / verify / rollback 引用机制
- 低风险变更模板
- 审计留痕字段规范

## 3. 非目标

- 不在本阶段覆盖所有厂商、所有配置场景
- 不在本阶段交付 MCP 工具层
- 不在本阶段完成拓扑和漂移诊断体系

## 4. 研发任务拆分

### 4.1 execution 状态机

- 统一任务状态：
  - `draft`
  - `approved`
  - `running`
  - `verifying`
  - `succeeded`
  - `partial`
  - `failed`
  - `rolled_back`
  - `cancelled`

### 4.2 变更前基线

- 为变更任务建立 baseline 引用机制
- 明确 baseline 与执行任务、设备集合、批次、变更模板的绑定关系

### 4.3 验证与回滚

- 定义 verify 结果合同
- verify 失败时必须进入 rollback 或人工挂起
- 记录 rollback_ref 和 rollback 结论

### 4.4 低风险变更模板

- 防火墙策略类
- 地址对象 / 服务对象类
- 路由 / 接口类低风险变更

### 4.5 审计留痕

- 统一记录工单号、审批状态、执行人、触发源、风险级别、回滚结果

## 5. 依赖与前置条件

- Phase 1 已正式通过
- inspection 和 execution 的只读合同已稳定
- 统一 execution ledger 设计已确定

## 6. 交付物

- `change_run` 统一任务合同
- execution 状态机定义
- baseline 引用机制
- verify 引用机制
- rollback 引用机制
- 低风险变更模板清单
- 审计留痕字段规范
- Phase 2 测试报告
- Phase 2 验收结论

当前实现索引：

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
- `backend/apps/workflow_center/models.py`
- [03b-phase-2-低风险变更模板清单.md](03b-phase-2-低风险变更模板清单.md)
- [03c-phase-2-审计留痕字段规范.md](03c-phase-2-审计留痕字段规范.md)

## 7. 接口或模型变更

本阶段必须形成以下稳定接口或等价合同：

- `POST /agent/v1/tasks/change`
- `GET /agent/v1/executions/{id}`

变更输出合同必须包含：

- `task_id`
- `execution_id`
- `status`
- `severity`
- `summary`
- `artifacts`
- `audit_ref`
- `rollback_ref`

## 8. 测试要求

- 无审批禁止执行
- 无 baseline 禁止执行
- 执行后必须 verify
- verify 成功时状态正确闭环
- verify 失败时触发 rollback 或挂起待人工确认
- execution ledger 能完整回放审批、执行、验证、回滚过程
- 低风险模板至少覆盖一个真实正向场景和一个失败回滚场景

## 9. 验收标准

以下标准全部满足，Phase 2 才能放行：

- 无审批不能执行
- 无 baseline 不能执行
- 执行后必须 verify
- verify 失败必须 rollback 或挂起待人工确认
- 审计留痕完整记录工单、执行人、触发源、状态、结论
- 变更合同对 agent 可解释，不暴露内部混乱状态

## 10. 验收流程

1. 研发负责人提交 Phase 2 完成包
2. 提交变更模板、状态机、测试报告、回滚证据、风险说明
3. 验收负责人执行变更主链 gate 审查
4. 必查场景：
   - 无审批执行拦截
   - 无 baseline 执行拦截
   - 正常变更 + verify 成功
   - 失败变更 + rollback 或待人工确认
   - execution ledger 完整追溯
5. 输出正式结论并写回文档

## 11. 风险与豁免

本阶段重点风险：

- 审批只是字段存在，没有真实门禁
- verify 只是形式动作，没有可执行标准
- rollback 不可引用、不可追溯、不可验证
- execution ledger 仍分散在多个模块，未真正统一

## 12. 阶段完成定义

以下全部满足时，Phase 2 视为完成：

- `change_run` 合同可用
- execution 状态机可用
- baseline / verify / rollback 引用机制可用
- 低风险模板可落地执行
- 审计留痕完整
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`DONE`
- Phase：`Phase 2`
- Decision：`PASS`
- Summary：`Phase 2 已完成 change_run 合同、审批与 baseline 门禁、verify/rollback 引用、execution ledger 数据库级回放证据和低风险模板扩展，并已完成复核。`
- Blocking Issues：
  - `无`
- Waivers：
  - `无`
- Required Follow-ups：
  - 在后续迭代中继续提升 execution ledger 的统一性和模板可维护性
- Evidence Refs：
  - `backend/apps/api/agent_views.py`
  - `backend/apps/api/tests_agent_v1.py`
  - `backend/apps/api/tests_agent_v1_integration.py`
  - `backend/apps/workflow_center/models.py`
  - `03b-phase-2-低风险变更模板清单.md`
  - `03c-phase-2-审计留痕字段规范.md`
  - `backend/venv/bin/python -m py_compile backend/apps/api/agent_views.py backend/apps/api/agent_urls.py backend/apps/api/tests_agent_v1.py backend/apps/workflow_center/models.py`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb`
- Accepted By：`codex`
- Accepted At：`2026-03-19 20:45:00 CST`

## 14. 整改回写

- 回写时间：`2026-03-20`
- 对应豁免：`WVR-P2-001`
- 当前结论：`CLOSED`
- 整改结果：
  - `change_run` 已改为模板注册表驱动，统一承接 `sec_policy_low_risk`、`address_object_low_risk`、`service_object_low_risk`、`dnat_low_risk` 四类低风险模板。
  - 四个模板均已补齐成功闭环与 verify 失败后 rollback 证据，统一输出 `baseline_ref`、`verify_ref`、`rollback_ref`、`rollback_status`、`audit_ref`。
  - execution ledger 仍统一落在 `Tasks.CHANGE` 主链，避免回放链路再次分散到 legacy 任务模型。
- Evidence Refs：
  - `backend/apps/api/change_templates.py`
  - `backend/apps/api/agent_views.py`
  - `backend/apps/api/tests_agent_v1.py`
  - `backend/apps/api/tests_agent_v1_integration.py`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb`
