# NetClaw-CN 总实施与验收文档

## 1. 文档定位

本目录是 NetClaw-CN 改造在 NetAxe backend 侧的唯一总控文档目录，用于统一管理：

- 改造目标与治理机制
- 分阶段研发目标与交付物
- 分阶段验收标准与验收流程
- 风险、豁免、复验与最终结论

本目录不是临时设计草稿区。后续研发推进、阶段签收、质量追责均以本目录内容为准。

## 2. 项目目标

本次改造目标是把 NetAxe backend 演进为 NetClaw-CN 的统一后端控制面，统一承接：

- 设备事实与能力暴露
- 巡检、诊断、安全审计
- 变更审批、执行、验证、回滚
- 分析结果、执行留痕、审计结论
- 面向 OpenClaw / MCP / Skill 的统一 API 边界

## 3. 当前边界

当前改造采用以下原则：

- 主链保留并增强：`device_api`、`asset`、`config_center`、`api`、`topology`、`workflow_center`、`network_analysis`、`dcs_control`
- 遗留冻结：`automation`
- 非依据模块：`monitor`、`support`
- 南向策略：国产设备优先走 NetAxe 原生能力
- 产品化目标：`device_api`、`asset`、`config_center`、`api`、`topology`、`dcs_control` 的 phase 设计必须以 NetAxe 自身产品化为目标，并联动前端页面重构
- 交付方式：分阶段 gate 验收，不通过不得进入下一阶段

## 4. 阶段总览

| 阶段 | 文档 | 目标 | 当前状态 | 验收结论 |
|---|---|---|---|---|
| Phase 0 | [01-phase-0-架构定版与遗留切割.md](01-phase-0-架构定版与遗留切割.md) | 架构定版、边界切割、遗留冻结 | DONE | PASS |
| Phase 1 | [02-phase-1-巡检与事实主链.md](02-phase-1-巡检与事实主链.md) | facts/capabilities/inspection/security audit 统一只读主链 | DONE | PASS |
| Phase 2 | [03-phase-2-变更治理主链.md](03-phase-2-变更治理主链.md) | 审批、执行、验证、回滚闭环 | DONE | PASS |
| Phase 3 | [04-phase-3-拓扑意图与漂移.md](04-phase-3-拓扑意图与漂移.md) | 事实拓扑、意图对比、漂移诊断 | DONE | PASS |
| Phase 4 | [05-phase-4-mcp与skill产品化.md](05-phase-4-mcp与skill产品化.md) | MCP / Skill 产品化边界 | DONE | PASS |

## 5. 文档入口

- [00-总控说明与治理机制.md](00-总控说明与治理机制.md)
- [06-统一验收流程与结论模板.md](06-统一验收流程与结论模板.md)
- [07-风险台账与豁免记录.md](07-风险台账与豁免记录.md)

## 6. 使用规则

- 每个阶段启动前，先更新对应 phase 文档中的研发任务与依赖。
- 每个阶段结束后，必须补齐证据、测试结果、风险状态和验收结论。
- 所有豁免必须登记到风险台账，且必须有截止时间与复核条件。
- 未在本目录登记的阶段结论、风险和例外，不视为正式有效。

## 7. 总体验收结论

- Decision：`PASS`
- Summary：`NetClaw-CN 在 NetAxe backend 侧的 Phase 0 到 Phase 4 已全部完成阶段验收与豁免复核，统一后端控制面、只读主链、变更治理主链、拓扑与漂移能力、MCP/Skill 产品化边界均已形成可用且已正式签收的基线。`
- Overall Checks：
  - `device_facts`、`inspection`、`security_audit`、`change_run`、`execution_query` 主链能力已具备统一合同
  - 审批、baseline、verify、rollback 与审计留痕闭环已形成最小可用实现
  - `automation` 不再承接新功能，`monitor`、`support` 不作为设计、实施、验收依据
  - OpenClaw / MCP / Skill 已以统一 REST / tool schema 为唯一产品化后端依据
- Active Waivers：
  - `无`
- Required Follow-ups：
  - 在后续产品化和发布阶段继续收缩 legacy 运行影响范围，禁止主链能力回流
- Accepted By：`codex`
- Accepted At：`2026-03-20 01:47:14 CST`
