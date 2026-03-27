# Phase 3 三方对账流程说明

## 1. 文档目的

本文件用于固定 Phase 3 的三方对账流程口径，明确资产事实、采集结果事实、分析归纳事实之间的对账关系和差异归属方式。

## 2. 三方事实定义

### 2.1 资产事实

来源：

- `asset.NetworkDevice` 中的设备主数据

当前使用字段：

- `serial_num`
- `manage_ip`
- `name`
- `category`

用途：

- 作为“平台登记设备集合”的基线
- 不作为拓扑边的唯一真值来源

约束：

- 不读取或依赖 `NetworkDevice.plan`
- 不把 `asset` 中的 legacy 绑定关系当作 Phase 3 主链依据

### 2.2 采集结果事实

来源：

- `plan_lldp`
- `plan_interface_brief`
- `plan_ip_interface`
- `AddressTraceSnapshot`

用途：

- 形成事实图中的设备、接口、邻接、IP、定位结果
- 作为 `topology/reconcile` 的核心事实来源

追溯字段：

- `execute_time`
- `source_task_id`
- `device_set`

### 2.3 分析归纳事实

来源：

- `TopologyReconcileService`
- `DriftAnalysisService`

用途：

- 将资产事实与采集结果事实对比，输出差异归属
- 为 `config_drift`、`route_health`、`device_health`、`topology_reconcile` 提供统一摘要

## 3. 对账流程

### 步骤 1：收集资产事实

从 `asset.NetworkDevice` 读取在管设备集合，形成：

- 已登记设备集合
- 设备标识与管理地址映射

### 步骤 2：收集采集结果事实

从主链采集结果中汇聚：

- LLDP 邻接
- 接口事实
- IP 事实
- 地址定位结果

形成事实图输入：

- 设备节点
- 接口节点
- 邻接边
- IP 关系
- 定位结果

### 步骤 3：执行 reconcile

对账输出以下差异：

- `missing_in_facts`
  - 资产中登记但当前采集事实未观察到的设备
- `unregistered_devices`
  - 采集事实中观察到但资产中未登记的设备
- `unresolved_traces`
  - 地址定位链路未完全闭环的结果
- `conflicts`
  - 同一源接口对应多个邻接对象的冲突结果

### 步骤 4：生成分析归纳事实

当前归纳输出：

- `topology_reconcile`
- `config_drift`
- `route_health`
- `device_health`

统一输出要求：

- `severity`
- `summary`
- `payload`
- `artifacts`

## 4. 差异归属规则

| 差异类型 | 归属说明 | 当前解释方式 |
|---|---|---|
| `missing_in_facts` | 更偏向采集缺口、批次缺口或设备离线 | 资产登记存在，但当前事实图未观察到 |
| `unregistered_devices` | 更偏向资产侧登记缺口 | 事实图中出现，但资产集合里没有 |
| `unresolved_traces` | 更偏向定位链路不完整 | 地址定位只完成部分闭环 |
| `conflicts` | 更偏向事实图冲突或采集异常 | 同一接口存在多邻接候选 |

## 5. 与 legacy 的边界

本流程明确不以以下模块作为设计、实现或验收依据：

- `automation`
- `monitor`
- `support`

旧 `topology` 手工图链路的角色：

- 只作为被替代对象
- 不作为未来事实拓扑主链来源

## 6. 当前证据引用

- `backend/apps/network_analysis/services.py`
- `backend/apps/api/agent_views.py`
- `backend/apps/network_analysis/tests.py`
- `backend/apps/api/tests_agent_v1.py`
