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
- agent 权限边界不清，高风险操作可能越权
- 错误码设计不完整，导致 Skill 侧无法正确处理

## 12. 阶段完成定义

以下全部满足时，Phase 4 视为完成：

- MCP / Skill 边界定义完成
- 权限和限流策略完成
- 错误语义规范完成
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`PLANNED`
- Gate 结论：`未验收`
- 验收负责人：`待填写`
- 验收时间：`待填写`
- 证据引用：`待填写`
