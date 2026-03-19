# Phase 0：架构定版与遗留切割

## 1. 阶段目标

本阶段目标是完成 NetClaw-CN 在 NetAxe backend 的统一架构定版，明确新主链、遗留边界、领域职责和对外统一接口的总体轮廓。

本阶段不交付最终业务能力，但必须交付一个后续工程可以直接照着实施的架构与治理基线。

## 2. 阶段范围

- 定义四个领域中心的职责边界
- 确认主链模块与遗留模块的处理原则
- 明确 agent 统一 API 的任务分类和输出合同
- 明确 `asset`、`device_api`、`config_center`、`api`、`topology`、`workflow_center`、`network_analysis`、`dcs_control` 的演进方向
- 明确 `automation`、`monitor`、`support` 的排除策略

## 3. 非目标

- 不在本阶段实现完整巡检或变更功能
- 不在本阶段重构所有 legacy 代码
- 不在本阶段交付 MCP Server
- 不在本阶段改造前端

## 4. 研发任务拆分

### 4.1 领域边界定版

- 输出 `southbound_core`、`ops_execution_center`、`network_intelligence_center`、`security_policy_center` 定义
- 明确每个领域的输入、输出、依赖和责任边界

### 4.2 主链与遗留切割

- 定义哪些能力必须进入新主链
- 定义哪些模块只读保留、兼容保留或完全冻结
- 明确 `NetworkDevice.plan -> automation` 的遗留属性

### 4.3 统一 agent API 草案

- 定义首期任务类型：
  - `device_facts`
  - `inspection_run`
  - `security_audit_run`
  - `change_run`
  - `execution_query`
- 定义统一输出字段：
  - `task_id`
  - `execution_id`
  - `status`
  - `severity`
  - `summary`
  - `artifacts`
  - `audit_ref`
  - `rollback_ref`

### 4.4 模块迁移清单

- 列出每个主链模块后续要承接的能力
- 列出遗留模块被替代、只读或保留的部分

## 5. 依赖与前置条件

- 现有模块职责梳理结论已确认
- `device_api` 作为默认采集主链的状态已确认
- 遗留模块不再承接新需求的原则已确认
- 已确认：`device_api`、`asset`、`config_center`、`api`、`topology`、`dcs_control` 的 phase 设计必须以 NetAxe 自身产品化为目标，并联动前端页面重构

## 6. 交付物

- 四个领域中心的正式定义
- 新主链与遗留链责任切割表
- 统一 agent API 草案
- 模块迁移清单
- `automation/topology/monitor` 处理原则清单
- `device_api/asset/config_center/api/topology/dcs_control` 产品化与前端联动原则清单
- Phase 0 验收结论

当前交付物索引：

- [01a-phase-0-领域边界与责任矩阵.md](./01a-phase-0-%E9%A2%86%E5%9F%9F%E8%BE%B9%E7%95%8C%E4%B8%8E%E8%B4%A3%E4%BB%BB%E7%9F%A9%E9%98%B5.md)
- [01b-phase-0-主链与遗留切割清单.md](./01b-phase-0-%E4%B8%BB%E9%93%BE%E4%B8%8E%E9%81%97%E7%95%99%E5%88%87%E5%89%B2%E6%B8%85%E5%8D%95.md)
- [01c-phase-0-统一-agent-api-草案.md](./01c-phase-0-%E7%BB%9F%E4%B8%80-agent-api-%E8%8D%89%E6%A1%88.md)
- [01d-phase-0-模块迁移清单.md](./01d-phase-0-%E6%A8%A1%E5%9D%97%E8%BF%81%E7%A7%BB%E6%B8%85%E5%8D%95.md)
- [01e-phase-0-gate-自查记录.md](./01e-phase-0-gate-%E8%87%AA%E6%9F%A5%E8%AE%B0%E5%BD%95.md)

## 7. 接口或模型变更

本阶段主要交付架构合同，不要求代码落地，但必须把后续实现边界写死：

- `GET /agent/v1/devices/{serial_num}/facts`
- `GET /agent/v1/devices/{serial_num}/capabilities`
- `POST /agent/v1/tasks/inspect`
- `POST /agent/v1/tasks/audit/security-policy`
- `POST /agent/v1/tasks/change`
- `GET /agent/v1/executions/{id}`

## 8. 测试要求

本阶段以设计验收和可实施性审查为主，必须提供：

- 领域模型与模块边界复核
- API 合同审查
- 依赖链和遗留链检查
- 与当前仓库现状的一致性说明

当前证据基线：

- `backend/apps/asset/models.py` 中 `NetworkDevice.plan` 仍依赖 `automation.CollectionPlan`
- `backend/apps/topology/views.py` 中仍存在旧 Mongo 手工图读写链路
- `backend/apps/device_api` 已具备父方案/子方案主链模型，可作为默认采集主链依据

## 9. 验收标准

以下标准全部满足，Phase 0 才能放行：

- 新主链和遗留链职责没有重叠歧义
- `automation` 被正式定义为遗留，不再承接新需求
- `monitor`、`support` 被正式定义为非依据模块，不进入设计、实施、验收依据
- `NetworkDevice.plan -> automation` 被明确标注为 legacy 依赖
- `device_api`、`asset`、`config_center`、`api`、`topology`、`dcs_control` 的 phase 设计已明确以 NetAxe 产品化和前端联动为目标
- 统一 agent API 草案足够另一个工程师直接实施
- 每个领域中心的输入、输出和边界清晰
- `automation`、`monitor`、`support` 未被错误作为本轮依据

## 10. 验收流程

1. 研发负责人提交 Phase 0 完成包
2. 提交边界定义、迁移清单、统一 API 草案、遗留处理原则
3. 验收负责人执行架构闸门审查
4. 输出 `PASS` / `PASS_WITH_WAIVER` / `REJECT`
5. 将结论写入本文件和风险台账

## 11. 风险与豁免

本阶段重点风险：

- 边界定义不清，后续阶段出现职责重叠
- 遗留冻结不彻底，研发继续回流 `automation`
- agent API 草案过于抽象，后续实现无法落地

## 12. 阶段完成定义

以下全部满足时，Phase 0 视为完成：

- 边界定义文档完成
- 遗留切割策略完成
- 统一接口草案完成
- 风险与冻结原则登记完成
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`DONE`
- Phase：`Phase 0`
- Decision：`PASS`
- Summary：`Phase 0 所需的领域边界、主链/legacy 切割、统一 agent API 草案和模块迁移清单已完成，并与当前仓库现状保持一致，可作为后续 phase 的正式实施依据。`
- Blocking Issues：
  - `无`
- Waivers：
  - `无`
- Required Follow-ups：
  - `Phase 1` 设计与实施不得新增对 `automation`、`monitor`、`support` 的设计级依赖
  - `Phase 2` 必须将 `workflow_center` 收敛为统一执行台账主链，补齐审批、执行、验证、回滚闭环
  - `Phase 3` 必须完成事实拓扑对旧 `topology` 手工图主链的替代
- Evidence Refs：
  - `01a-phase-0-领域边界与责任矩阵.md`
  - `01b-phase-0-主链与遗留切割清单.md`
  - `01c-phase-0-统一-agent-api-草案.md`
  - `01d-phase-0-模块迁移清单.md`
  - `01e-phase-0-gate-自查记录.md`
  - `backend/apps/asset/models.py:431`
  - `backend/apps/topology/views.py:22`
- Accepted By：`codex`
- Accepted At：`2026-03-19 10:41:40 CST`
