# Phase 1：巡检与事实主链

## 1. 阶段目标

本阶段目标是打通 NetClaw-CN 的统一只读主链，使 agent 能通过 NetAxe backend 完成设备 facts、capabilities、巡检、安全审计和分析查询，而不再直接拼接多个内部模块。

## 2. 阶段范围

- 设备 facts / capabilities 统一出口
- inspection 统一任务合同
- network analysis 聚合出口
- security audit 统一出口
- severity / summary / report 合同
- execution 与审计引用的最小闭环

## 3. 非目标

- 不在本阶段实现完整变更审批和回滚闭环
- 不在本阶段交付拓扑漂移全能力
- 不在本阶段交付 MCP / Skill 产品化

## 4. 研发任务拆分

### 4.1 设备事实与能力统一出口

- 统一 facts 出口，暴露设备基础事实、画像、绑定、协议能力
- 统一 capabilities 出口，暴露支持采集类型、首选协议、回退协议

### 4.2 inspection 统一任务合同

- 设计 inspection 输入输出合同
- 将巡检结果统一写入 execution ledger
- 统一 severity、summary、artifacts、audit_ref 输出

### 4.3 network analysis 聚合出口

- 将接口利用率、地址定位纳入统一分析查询
- 对外暴露统一 analysis 视图，而不是直接暴露底层模型细节

### 4.4 security audit 统一出口

- 统一安全策略审计输出
- 将 findings、summary、payload、audit record 统一引用

### 4.5 国产主厂商巡检基线

- 明确 Huawei、H3C、Ruijie、Hillstone、ZTE、Maipu、Centec 的主巡检模板覆盖状态
- 对未覆盖能力返回明确可解释阻塞原因

## 5. 依赖与前置条件

- Phase 0 已正式通过
- 统一 agent API 草案已定版
- `device_api`、`workflow_center`、`network_analysis`、`dcs_control` 的职责边界已确认

## 6. 交付物

- 设备 facts 统一出口
- 设备 capabilities 统一出口
- `inspection_run` 任务合同
- network analysis 聚合出口
- security audit 统一出口
- severity / report / summary 合同
- Phase 1 测试报告
- Phase 1 验收结论

## 7. 接口或模型变更

本阶段必须形成可直接消费的只读接口：

- `GET /agent/v1/devices/{serial_num}/facts`
- `GET /agent/v1/devices/{serial_num}/capabilities`
- `POST /agent/v1/tasks/inspect`
- `GET /agent/v1/analysis/...`
- `POST /agent/v1/tasks/audit/security-policy`

返回合同至少必须包含：

- `task_id`
- `execution_id`
- `status`
- `severity`
- `summary`
- `artifacts`
- `audit_ref`

## 8. 测试要求

- 单设备 facts 查询
- 单设备 capabilities 查询
- 单设备巡检成功
- 批量巡检部分成功
- 巡检结果能回查 execution ledger
- 安全审计结果能独立查询和回放
- analysis 结果可回溯到源批次或源任务
- 未覆盖画像设备返回明确阻塞原因

## 9. 验收标准

以下标准全部满足，Phase 1 才能放行：

- 单设备巡检成功
- 批量巡检支持 `partial`
- 结果可追溯到 execution、audit、artifacts
- facts / capabilities 输出合同稳定
- 安全审计输出合同稳定
- 国产主厂商画像与默认绑定结果可解释
- agent 不再需要直接拼接内部多个只读接口

## 10. 验收流程

1. 研发负责人提交 Phase 1 完成包
2. 提交接口清单、测试报告、示例响应、遗留能力清单、风险说明
3. 验收负责人执行只读主链 gate 审查
4. 必查场景：
   - 设备画像与自动绑定
   - 单设备巡检
   - 批量巡检 partial
   - 安全审计结果回放
   - analysis 结果追溯
5. 输出正式结论并写回文档

## 11. 风险与豁免

本阶段重点风险：

- 统一出口只是薄包装，底层模块仍强耦合暴露
- 巡检合同不稳定，导致 agent 侧提示不可预测
- 国产主厂商巡检模板覆盖不完整，但未明确返回阻塞原因

## 12. 阶段完成定义

以下全部满足时，Phase 1 视为完成：

- 只读统一出口可用
- inspection 合同稳定
- security audit 合同稳定
- analysis 聚合出口可用
- 测试与证据完整
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`PLANNED`
- Gate 结论：`未验收`
- 验收负责人：`待填写`
- 验收时间：`待填写`
- 证据引用：`待填写`
