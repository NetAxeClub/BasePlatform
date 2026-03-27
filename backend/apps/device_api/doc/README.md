# device_api 功能定位

## 1. 模块定位

`device_api` 不是单纯的“设备数据采集模块”，它在 BasePlatform 中的定位是：

`网络设备原子能力中心`

它负责把网络设备相关的原子能力做统一封装，对上提供统一接口，对下屏蔽厂商、型号、协议、命令和数据结构差异。

这里说的“原子能力”，包括但不限于：

- 设备能力识别：识别设备支持什么协议、什么采集方式、什么能力项
- 原子采集执行：按父方案、子方案和设备绑定执行单项能力
- 协议适配屏蔽：屏蔽 Netmiko、NETCONF、SNMP、RESTCONF 等差异
- 结果标准化：把不同厂商、不同协议输出统一成标准字段
- 设备事实回填：把经采集才能获得的真实事实回写到设备事实域
- 执行留痕与分析：记录运行态证据，生成批次分析和处理建议

所以，数据采集只是 `device_api` 的一个核心功能，但不是它的全部。

## 2. 主要职责

围绕这个定位，`device_api` 当前主要承担 6 类职责：

### 2.1 原子能力建模

- 通过父方案 `DeviceCollectionPlans` 和子方案 `DeviceSubCollectionPlan` 建模设备原子能力
- 通过 `PlansToDevice` 明确“设备当前应该执行什么方案”
- 通过 `PlatformProfile`、默认方案和能力画像描述设备能力边界

### 2.2 协议执行统一封装

- 统一封装 Netmiko、NETCONF、SNMP、RESTCONF、Telemetry 等执行入口
- 对上暴露一致的调用方式
- 对下屏蔽不同协议的连接、重试、超时、命令和 XML 差异

### 2.3 结果解析与标准化

- 把 CLI、XML、结构化返回统一送入标准处理器
- 通过 processors、field mappings、contract 输出统一结构
- 统一落到 `plan_<collection_type>` 标准集合

### 2.4 设备事实与能力服务

- 对外提供设备 facts / capabilities 查询
- 回填设备名称、软件版本、补丁版本、HA 状态、槽位等真实事实
- 不改资产录入主数据中的用户决策项，例如设备类型

### 2.5 运行态证据与排障

- 记录批次、设备、子方案、原始结果、处理结果等运行态证据
- 为生产排障、回放、覆盖率评估、模板问题定位提供依据

### 2.6 结果分析与建议

- 基于上一轮运行态结果，识别协议不匹配、账号缺失、模板失配、覆盖缺口
- 输出独立 checklist，供人工评估是否调整绑定、补账号或修模板
- 分析只给建议，不在采集执行链路中自动改写绑定

## 3. 设计边界

`device_api` 的边界需要明确，不然会和 `asset`、`automation` 混在一起。

### 3.1 device_api 负责

- 原子能力模型
- 采集执行
- 协议适配
- 标准化处理
- 设备事实回填
- 运行态证据
- 结果分析建议

### 3.2 asset 负责

- 用户维护的设备主数据
- 例如：IP、设备类型、序列号、账号关联、资产属性

### 3.3 automation 负责

- 调度历史兼容入口和兜底链路
- 不再作为新能力的默认承接方

## 4. 主链原则

当前主链遵循以下原则：

- `plan_collect_device_main` / `plan_collect_device` 严格以 `PlansToDevice` 为执行依据
- 采集任务只负责执行、留痕、入库，不在执行时自动改写绑定
- 如果设备与当前绑定方案不匹配，异常和覆盖缺口统一保留到运行态集合
- 绑定是否调整，由独立分析任务给出建议，再由人工或显式操作执行

## 5. 核心对象

- 父方案：`DeviceCollectionPlans`
- 子方案：`DeviceSubCollectionPlan`
- 设备绑定：`PlansToDevice`
- 平台画像：`PlatformProfile`
- 协议执行层：`backend/apps/device_api/connection_manager.py`
- 执行服务层：`backend/apps/device_api/services_new.py`
- 结果处理层：`backend/apps/device_api/processors/`
- 标准合同：`backend/apps/device_api/contract.py`

## 6. 对外能力接口

当前对外主要提供以下能力接口：

- 设备事实：`/device_api/devices/<serial_num>/facts/`
- 设备能力：`/device_api/devices/<serial_num>/capabilities/`
- 采集方案管理：`/device_api/collection-plans/`
- 子方案管理：`/device_api/sub-collection-plan/`
- 设备绑定管理：`/device_api/plans-to-device/`
- 结果查询：`/device_api/collection-results/`
- 分析清单：`/device_api/collection-results/analysis_checklist/`

`/device_api/plans-to-device/` 当前默认只返回 `is_active=true` 的当前有效绑定：

- 未显式传 `is_active` 且未传 `include_inactive=true` 时，接口会自动过滤历史失效绑定
- 若需查询历史无效绑定，可显式传 `is_active=false`
- 若需同时查看当前与历史绑定，可传 `include_inactive=true`
- 每条绑定记录会额外返回 `binding_status / is_binding_conflict / active_bindings_count / other_active_bindings`
- 这些附加字段只基于“当前 active 绑定”计算，不会把历史 inactive 绑定计入冲突

`/device_api/plans-to-device/auto_bind/` 当前用于单设备自动重绑定：

- 输入以 `manage_ip` 为必填，`category_name` 可显式传入设备类型；若未传则回退资产中的设备类型
- 优先按账户入口验证 NETCONF 连通性；连通成功后先锁定同 `vendor + category` 的 NETCONF 候选方案集合，再用 `netconf_capability` 能力画像在该集合内细分具体方案
- 若 NETCONF 不通且 SSH 可用，则回退匹配 `cli` 语义方案
- 自动绑定只会收敛 `binding_source=auto` 的关系，不覆盖手工绑定

## 7. 运行态排障入口

生产排障优先看 4 处：

- `Automation.DeviceApiExecutionLog`：批次加载、去重、跳过、下发、子方案开始/结束/异常、设备完成、批次完成
- `Automation.SubPlanCollectionCelery`：子方案状态、`coverage_issue`、`coverage_reason`、`raw_result_preview`
- `Automation.PlanCollectionCelery`：设备级汇总，包括失败数、跳过数、覆盖缺口汇总
- `Automation.TestDeviceCollection`：原始结果、处理结果、错误信息，适合做深度回放

默认行为：

- `plan_collect_device_main(clear_history=True)` 会在全局采集开始前清空以上 4 个运行态集合
- `clear_history=False` 可用于灰度对比或回放

## 8. 结果分析清单

独立结果分析任务：

- `analyze_collection_plan_bindings(execute_time=...)`

任务会：

- 基于 `PlanCollectionCelery / SubPlanCollectionCelery / DeviceApiExecutionLog / TestDeviceCollection`
- 生成设备级建议清单
- 持久化到 `Automation.DevicePlanBindingAnalysisChecklist`

前端可直接调用：

- `GET /device_api/collection-results/analysis_checklist/`
- `POST /device_api/collection-results/refresh_analysis_checklist/`


## 10. 当前文档入口

- [当前能力](./当前能力.md)
- [遗留任务](./遗留任务.md)
- [前端页面需求](./前端页面需求.md)

## 11. 证据文件

验收和灰度证据保留在当前目录的 `*.json` 文件中，用于追溯，不再单独展开为 phase Markdown 文档。
