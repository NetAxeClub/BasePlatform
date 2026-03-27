# Phase 0 附录 A：领域边界与责任矩阵

## 1. 文档目的

本文件用于把 NetClaw-CN 在 NetAxe backend 内的四个领域中心正式定版，作为后续 Phase 1 到 Phase 4 的唯一架构边界依据。

本文件解决三个问题：

- 哪些能力属于未来主链
- 每个领域的输入、输出和依赖是什么
- 哪些现有模块可以复用，哪些只能兼容过渡

## 2. 四个领域中心定义

| 领域中心 | 核心职责 | 典型输入 | 典型输出 | 允许依赖 | 禁止事项 |
|---|---|---|---|---|---|
| `southbound_core` | 设备画像识别、协议矩阵、采集方案映射、原子南向执行、结果标准化入库 | 设备标识、厂商型号、账户信息、采集计划、执行参数 | 设备 facts、capabilities、标准化原始结果、执行元数据 | `asset`、`device_api`、必要的协议驱动与结果落库能力 | 不在本域直接做审批、工单编排、策略审计结论 |
| `ops_execution_center` | 统一执行台账、任务状态机、审批/执行/验证/回滚编排、执行查询合同 | 任务请求、审批信息、执行参数、触发源、执行证据 | `execution_id`、执行状态、步骤明细、审计引用、回滚引用 | `workflow_center`、后续统一任务模型、各领域执行适配器 | 不直接承载设备驱动实现，不直接暴露碎片化内部 app 接口 |
| `network_intelligence_center` | 事实分析、拓扑事实、漂移分析、地址定位、利用率分析、健康诊断 | southbound facts、采集快照、拓扑输入、分析触发参数 | 分析结果、异常摘要、拓扑事实、诊断工件 | `network_analysis`、`topology` 中可复用事实能力、`asset` | 不把旧 `topology` 手工图编辑模型定义为未来主链事实来源 |
| `security_policy_center` | 安全策略审计、高危暴露检测、审计留痕、变更前后安全差异分析 | 设备配置、策略对象、执行上下文、审计参数 | 审计结果、风险级别、整改建议、审计引用 | `dcs_control`、`config_center`、必要的策略解析能力 | 不承担设备采集主链，不绕过统一执行中心直接落高风险变更 |

## 3. 领域输入输出边界

### 3.1 `southbound_core`

输入：

- `serial_num`、`manage_ip`、设备基础画像
- 设备登录凭据和协议能力
- 采集父方案、子方案、执行批次参数

输出：

- 统一 `facts` 数据
- 统一 `capabilities` 数据
- 采集执行元数据，如采集时间、命令、协议、结果工件引用

边界约束：

- 该域只负责“拿到事实”和“标准化执行结果”，不负责审批和审计结论
- 本域允许兼容 legacy 采集能力，但新能力默认落到 `device_api`
- `asset.NetworkDevice.plan -> automation.CollectionPlan` 仅视为 legacy 绑定，不得继续扩散为新主链模型

### 3.2 `ops_execution_center`

输入：

- 巡检、安全审计、变更等统一任务请求
- 审批、执行人、触发源、风险等级、目标范围

输出：

- 统一执行主键
- 执行状态与阶段明细
- 审计留痕、回滚引用、证据引用

边界约束：

- 本域负责统一任务生命周期，不负责厂商协议差异处理
- 任一高风险任务都应通过本域形成可查询的执行台账
- 后续 `execution_query` 以本域为唯一主出处

### 3.3 `network_intelligence_center`

输入：

- 设备 facts
- 拓扑关系原始数据
- 分析任务参数和时间窗口

输出：

- 利用率、地址定位、漂移诊断、拓扑事实与分析摘要

边界约束：

- 本域消费事实，不生成南向驱动
- `topology` 当前可复用的数据能力仅限事实相关部分，旧手工图维护链路不进入未来主链依据

### 3.4 `security_policy_center`

输入：

- 配置快照、策略对象、差异对比对象
- 审计规则、执行上下文、整改策略

输出：

- 审计风险项
- 风险等级和摘要
- 审计结果留痕及整改建议

边界约束：

- 本域产出的是安全审计结论，而不是设备事实
- 本域可消费执行中心提供的上下文，但不应绕过执行中心落高风险执行

## 4. 当前仓库映射

| 现有模块 | 归属领域 | 当前角色 | Phase 0 结论 |
|---|---|---|---|
| `apps/device_api` | `southbound_core` | 默认采集主链 | 继续增强，承接事实与能力主链 |
| `apps/asset` | `southbound_core` | 设备基础事实与画像 | 继续增强，作为设备与能力快照基础底座 |
| `apps/workflow_center` | `ops_execution_center` | 执行编排基础 | 后续演进为统一任务执行中心 |
| `apps/network_analysis` | `network_intelligence_center` | 分析结果底座 | 后续演进为网络智能分析中心 |
| `apps/topology` | `network_intelligence_center` | 现有拓扑能力 | 仅保留可复用事实能力，旧手工图不作为未来主链依据 |
| `apps/dcs_control` | `security_policy_center` | 安全策略相关能力 | 后续抽取安全策略审计中心能力 |
| `apps/config_center` | 横向支撑 | 配置与产品化支撑 | 纳入 phase 设计，但以 NetAxe 产品化为目标 |
| `apps/api` | 横向支撑 | 统一入口与前后端联动支撑 | 纳入统一接口与前端联动设计 |

## 5. 领域协作原则

1. agent 统一 API 只暴露领域级合同，不直接拼接多个内部 app 的原始接口。
2. `southbound_core` 产出事实，`network_intelligence_center` 和 `security_policy_center` 消费事实并生成高层结果。
3. `ops_execution_center` 是需要执行台账的任务统一出口，后续变更、巡检、安全审计都应纳入。
4. `automation`、`monitor`、`support` 不作为任何领域中心的设计依据。

## 6. 已知限制

- 当前仓库仍存在 `asset` 对 `automation.CollectionPlan` 的模型级依赖，Phase 0 仅将其定性为 legacy，不在本阶段拆模。
- 当前 `topology` 仍有旧 Mongo 手工图读写链路，Phase 0 仅冻结其作为未来主链依据的资格。
- 当前安全审计与执行编排尚未统一到单一执行台账模型，Phase 0 只固定目标边界与接口合同。
