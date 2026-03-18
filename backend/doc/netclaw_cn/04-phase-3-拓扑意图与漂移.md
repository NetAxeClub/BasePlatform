# Phase 3：拓扑意图与漂移

## 1. 阶段目标

本阶段目标是形成 NetClaw-CN 的事实拓扑、意图对比和漂移诊断能力，使平台从“采集与执行”升级到“发现、比对、诊断”的网络智能域。

## 2. 阶段范围

- topology reconcile 出口
- config drift / route health / device health 分析项
- 事实图模型说明
- 资产 / 事实 / 采集结果三方对账流程

## 3. 非目标

- 不继续扩展旧 `topology` 手工图编辑主链
- 不在本阶段实现所有高级协议诊断场景
- 不在本阶段交付 MCP / Skill 层

## 4. 研发任务拆分

### 4.1 事实拓扑模型

- 定义设备、接口、邻接、IP、定位结果等事实关系
- 明确事实图的数据来源与批次锚点

### 4.2 topology reconcile

- 输出事实拓扑与资产/意图之间的差异结果
- 标注缺失、漂移、冲突、未识别对象

### 4.3 新增分析项

- `config_drift`
- `route_health`
- `device_health`
- 后续可扩展 `topology_reconcile`

### 4.4 三方对账流程

- 资产事实
- 采集结果事实
- 分析归纳事实

## 5. 依赖与前置条件

- Phase 2 已正式通过
- `network_analysis` 的基础分析链已稳定
- facts / inspection / execution / audit 已可追溯

## 6. 交付物

- topology reconcile 出口
- config drift 分析项
- route health 分析项
- device health 分析项
- 事实图模型说明
- 三方对账流程说明
- Phase 3 测试报告
- Phase 3 验收结论

## 7. 接口或模型变更

本阶段必须形成以下稳定能力出口：

- `GET /agent/v1/topology/reconcile`
- `GET /agent/v1/analysis/...`

分析结果必须可追溯到：

- `execute_time`
- `source_task_id`
- `device_set`

## 8. 测试要求

- LLDP 事实来源可进入拓扑事实图
- 接口事实来源可进入拓扑事实图
- IP 事实来源可进入拓扑事实图
- 地址定位结果可纳入事实图或对账链
- 漂移结果可回查源批次和源任务
- route health / device health 至少各有一组有效结果样例

## 9. 验收标准

以下标准全部满足，Phase 3 才能放行：

- 拓扑结果不依赖旧 `topology` 手工图模型
- 漂移结果可回溯到批次和源执行记录
- 至少覆盖 LLDP、接口、IP、地址定位四类事实来源
- 分析结果具备统一 severity / summary / traceability
- 三方对账流程可明确指出差异归属

## 10. 验收流程

1. 研发负责人提交 Phase 3 完成包
2. 提交事实图模型、分析项定义、对账流程、测试报告和风险说明
3. 验收负责人执行拓扑与漂移 gate 审查
4. 必查场景：
   - 多事实来源汇聚
   - topology reconcile 输出
   - config drift 可追溯
   - route health / device health 可回放
5. 输出正式结论并写回文档

## 11. 风险与豁免

本阶段重点风险：

- 事实拓扑仍被旧手工图模型绑架
- 分析结论无法回溯到批次和任务
- 漂移检测只有表面字段比对，没有归因能力

## 12. 阶段完成定义

以下全部满足时，Phase 3 视为完成：

- topology reconcile 出口可用
- 核心分析项可用
- 事实图模型说明完成
- 三方对账流程完成
- 阶段验收结论已写回文档

## 13. 验收结论

- 当前状态：`PLANNED`
- Gate 结论：`未验收`
- 验收负责人：`待填写`
- 验收时间：`待填写`
- 证据引用：`待填写`
