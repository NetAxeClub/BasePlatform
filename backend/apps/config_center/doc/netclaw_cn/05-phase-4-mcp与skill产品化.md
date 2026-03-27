# Phase 4：MCP 与 Skill 产品化

## 1. 阶段目标

本阶段目标是把 NetAxe backend 的统一 REST 能力包装成 NetClaw-CN 可以稳定消费的 MCP / Skill 边界，使后续 agent 能通过标准工具接口调用，而不是直接访问内部模块。

## 2. 阶段范围

- MCP tool schema
- 权限与限流策略
- 错误码与可解释语义
- OpenClaw / Skill 接入约束

## 3. 非目标

- 不在本阶段继续扩展底层业务域功能
- 不以 `automation`、`monitor`、`support` 作为 MCP / Skill 产品化的能力来源或接口依据
- 不允许为了接入速度绕过统一后端，直接把 legacy app 包装成 tool
- 不在本阶段重构全部现有 OpenClaw Skill 实现细节

## 4. 研发任务拆分

### 4.1 MCP 工具边界

- 将统一 REST 能力映射为稳定 tool
- 为 facts、inspection、security audit、change、execution query 定义 tool schema

### 4.2 权限与限流

- 设计 agent service account 权限边界
- 定义高风险变更调用门禁
- 设计速率限制、幂等和重试策略

### 4.3 错误码与解释语义

- 统一错误分类
- 明确可重试、不可重试、人工介入三类错误
- 输出适合 Skill 消费的结构化错误

### 4.4 接入约束

- 明确 OpenClaw / Skill 不应直接拼接内部接口
- 明确后续集成必须消费 MCP / REST 统一合同

### 4.5 legacy app 禁止事项

- `automation`、`monitor`、`support` 不允许作为 tool schema、权限模型、错误语义或验收样例的直接来源
- 若历史能力仍在线，只允许通过主链模块暴露统一合同，不允许直接包装 legacy app 路由或模型
- 所有产品化接入都必须以 Phase 0 到 Phase 3 已确认的主链模块为唯一后端依据

## 5. 依赖与前置条件

- Phase 3 已正式通过
- 统一 REST 主链已稳定
- execution、audit、analysis 等领域结果合同已稳定

## 6. 交付物

- MCP tool schema
- 权限控制规则
- 限流与幂等策略
- 错误码与解释语义规范
- OpenClaw / Skill 接入约束文档
- Phase 4 测试报告
- Phase 4 验收结论

当前实现索引：

- `backend/apps/api/agent_views.py`
- `backend/apps/api/agent_urls.py`
- `backend/apps/api/tests_agent_v1.py`
- [05a-phase-4-完成包与产品化约束.md](05a-phase-4-完成包与产品化约束.md)
- [05b-phase-4-错误语义与权限规则.md](05b-phase-4-错误语义与权限规则.md)

## 7. 接口或模型变更

本阶段必须明确：

- tool 输入参数合同
- tool 输出结构合同
- agent 身份与权限约束
- 高风险操作的强制门禁

## 8. 测试要求

- facts tool 正常调用
- inspection tool 正常调用
- security audit tool 正常调用
- change tool 权限与审批门禁正常
- execution query tool 可稳定回放结果
- 可重试错误与不可重试错误能明确区分

## 9. 验收标准

以下标准全部满足，Phase 4 才能放行：

- agent 不直接拼接零散内部接口
- tool 不直接消费 `automation`、`monitor`、`support` 等 legacy app
- REST / MCP 合同稳定
- tool metadata 足以支撑调用、出错、重试和审计
- 权限边界清晰，agent service account 不等同普通用户
- 高风险变更门禁有效

## 10. 验收流程

1. 研发负责人提交 Phase 4 完成包
2. 提交 MCP schema、权限规则、限流策略、测试报告和风险说明
3. 验收负责人执行产品化 gate 审查
4. 必查场景：
   - facts / inspection / audit / change / execution_query 五类 tool
   - 权限与限流
   - 错误码可解释
   - 审计链完整
5. 输出正式结论并写回文档

## 11. 风险与豁免

本阶段重点风险：

- tool schema 只是 REST 透传，缺少稳定语义
- 为了快速接入而直接包装 `automation`、`monitor`、`support`，导致 legacy 能力重新暴露给 agent
- agent 权限边界不清，高风险操作可能越权
- 错误码设计不完整，导致 Skill 侧无法正确处理

## 12. 阶段完成定义

以下全部满足时，Phase 4 视为完成：

- MCP / Skill 边界定义完成
- 权限和限流策略完成
- 错误语义规范完成
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`DONE`
- Phase：`Phase 4`
- Decision：`PASS`
- Summary：`Phase 4 已完成 MCP/Skill 产品化边界基线，主链 tool schema、权限边界、错误语义、限流 enforcement 和 legacy 禁止事项已固定并通过复核。`
- Blocking Issues：
  - `无`
- Waivers：
  - `无`
- Required Follow-ups：
  - 在后续产品化阶段继续完善 MCP server 实现细节和更丰富的错误语义
- Evidence Refs：
  - `backend/apps/api/agent_views.py`
  - `backend/apps/api/agent_urls.py`
  - `backend/apps/api/tests_agent_v1.py`
  - `05a-phase-4-完成包与产品化约束.md`
  - `05b-phase-4-错误语义与权限规则.md`
  - `backend/apps/api/error_codes.py`
  - `backend/apps/api/throttles.py`
  - `backend/apps/api/tests_agent_v1_integration.py`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 apps.api.tests_agent_v1_integration -v 2 --keepdb`
- Accepted By：`codex`
- Accepted At：`2026-03-20 00:20:00 CST`

## 14. 整改回写

- 回写时间：`2026-03-20`
- 对应豁免：`WVR-P4-001`
- 当前结论：`CLOSED`
- 整改结果：
  - 已新增统一错误码字典，固定 `http_status`、`retryable`、`category`、`recommended_action`，并复用于 tool catalog 与接口错误返回。
  - 已新增运行时 throttle，实现 `device_facts`、`inspection_run`、`security_audit_run`、`change_run`、`execution_query` 的 burst / sustained enforcement。
  - 已补齐限流测试与错误码一致性测试，确认 tool metadata 不再只是静态说明。
- Evidence Refs：
  - `backend/apps/api/error_codes.py`
  - `backend/apps/api/throttles.py`
  - `backend/apps/api/agent_views.py`
  - `backend/apps/api/tests_agent_v1.py`
  - `backend/apps/api/tests_agent_v1_integration.py`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
  - `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb`
