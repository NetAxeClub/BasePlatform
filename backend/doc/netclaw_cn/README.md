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
| Phase 0 | [01-phase-0-架构定版与遗留切割.md](./01-phase-0-%E6%9E%B6%E6%9E%84%E5%AE%9A%E7%89%88%E4%B8%8E%E9%81%97%E7%95%99%E5%88%87%E5%89%B2.md) | 架构定版、边界切割、遗留冻结 | PLANNED | 未验收 |
| Phase 1 | [02-phase-1-巡检与事实主链.md](./02-phase-1-%E5%B7%A1%E6%A3%80%E4%B8%8E%E4%BA%8B%E5%AE%9E%E4%B8%BB%E9%93%BE.md) | facts/capabilities/inspection/security audit 统一只读主链 | PLANNED | 未验收 |
| Phase 2 | [03-phase-2-变更治理主链.md](./03-phase-2-%E5%8F%98%E6%9B%B4%E6%B2%BB%E7%90%86%E4%B8%BB%E9%93%BE.md) | 审批、执行、验证、回滚闭环 | PLANNED | 未验收 |
| Phase 3 | [04-phase-3-拓扑意图与漂移.md](./04-phase-3-%E6%8B%93%E6%89%91%E6%84%8F%E5%9B%BE%E4%B8%8E%E6%BC%82%E7%A7%BB.md) | 事实拓扑、意图对比、漂移诊断 | PLANNED | 未验收 |
| Phase 4 | [05-phase-4-mcp与skill产品化.md](./05-phase-4-mcp%E4%B8%8Eskill%E4%BA%A7%E5%93%81%E5%8C%96.md) | MCP / Skill 产品化边界 | PLANNED | 未验收 |

## 5. 文档入口

- [00-总控说明与治理机制.md](./00-%E6%80%BB%E6%8E%A7%E8%AF%B4%E6%98%8E%E4%B8%8E%E6%B2%BB%E7%90%86%E6%9C%BA%E5%88%B6.md)
- [06-统一验收流程与结论模板.md](./06-%E7%BB%9F%E4%B8%80%E9%AA%8C%E6%94%B6%E6%B5%81%E7%A8%8B%E4%B8%8E%E7%BB%93%E8%AE%BA%E6%A8%A1%E6%9D%BF.md)
- [07-风险台账与豁免记录.md](./07-%E9%A3%8E%E9%99%A9%E5%8F%B0%E8%B4%A6%E4%B8%8E%E8%B1%81%E5%85%8D%E8%AE%B0%E5%BD%95.md)

## 6. 使用规则

- 每个阶段启动前，先更新对应 phase 文档中的研发任务与依赖。
- 每个阶段结束后，必须补齐证据、测试结果、风险状态和验收结论。
- 所有豁免必须登记到风险台账，且必须有截止时间与复核条件。
- 未在本目录登记的阶段结论、风险和例外，不视为正式有效。
