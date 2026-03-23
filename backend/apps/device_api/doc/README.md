# device_api 功能介绍

## 1. 模块定位

`device_api` 是 BasePlatform 当前默认的网络设备采集主链，负责把设备采集、标准化、入库、查询和事实回写收敛到统一链路中。

当前模块承担四类职责：

- 采集方案管理：父方案、子方案和设备绑定
- 多协议执行：Netmiko、NETCONF、SNMP、RESTCONF、Telemetry 占位门禁
- 标准结果入库：统一写入 `plan_<collection_type>`
- 运维查询与联动：结果查询、能力查询、事实回写、分析触发

## 2. 主链范围

当前主链入口：

- 默认入口：`plan_collect_device_main`
- 单设备执行：`plan_collect_device`
- fallback 入口：`automation`

当前约束：

- 新增采集能力默认进入 `device_api`
- `automation` 仅保留为回退与应急入口
- `asset` 数据模型不在 `device_api` 内直接改造

## 3. 核心对象

- 父方案：`DeviceCollectionPlans`
- 子方案：`DeviceSubCollectionPlan`
- 设备绑定：`PlansToDevice`
- 标准合同：`backend/apps/device_api/contract.py`
- 执行层：`backend/apps/device_api/services_new.py`
- 协议层：`backend/apps/device_api/connection_manager.py`
- 解析层：`backend/apps/device_api/processors/`

## 4. 当前文档入口

- [当前能力](./当前能力.md)
- [遗留任务](./遗留任务.md)

## 5. 证据文件

验收和灰度证据保留在当前目录的 `*.json` 文件中，用于追溯，不再单独展开为 phase Markdown 文档。


### 5. 生产排障
可以直接查 4 处：
Automation.DeviceApiExecutionLog：批次加载、去重、跳过、下发、子方案开始/结束/异常、设备完成、批次完成。
Automation.SubPlanCollectionCelery：子方案状态、coverage_issue、coverage_reason、raw_result_preview。
Automation.PlanCollectionCelery：设备级汇总，包括失败数、跳过数、覆盖缺口汇总。
Automation.TestDeviceCollection：原始结果、处理结果、错误信息，适合做深度回放。