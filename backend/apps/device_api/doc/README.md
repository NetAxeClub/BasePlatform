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
- 同一设备若同时存在 active `manual` 与 active `auto` 绑定，执行链路只采纳 `manual`
- `auto` 绑定在这种场景下保留为分析证据，不再参与本轮采集下发
- 下发前会过滤 `netmiko / netconf / snmp / restconf / telemetry` 全部未启用的不可执行子方案
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
- 执行追踪聚合：`/device_api/collection-results/device_traceability/`
- 执行总览列表：`/device_api/collection-results/parent_collection_list/`

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

`/device_api/plans-to-device/batch-auto-bind/` 当前用于批量异步画像重绑：

- 通过 Celery 批任务异步执行，适合处理大批量 `binding_plan_mismatch` 设备
- 支持按 `manage_ip / serial_num / vendor_aliases / target_blockers / limit` 筛选候选设备
- 任务内部会先做画像覆盖审计，再并发执行 capability discovery 和自动重绑
- 若命中 active `manual` 绑定且与目标方案冲突，任务会跳过该设备并返回 `manual_binding_conflict`，避免误覆盖手工绑定
- 任务提交后可通过 `/device_api/plans-to-device/task-status/?task_id=<task_id>` 查询进度

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

`GET /device_api/collection-results/analysis_checklist/` 当前支持的关键筛选参数：

- `execute_time`：批次时间锚点；不传时默认取最新批次
- `manage_ip`：按设备 IP 筛选
- `recommendation_code`：按建议编码筛选
- `task_status`：按设备任务状态筛选
- `summary_plan_id`：按父方案筛选（映射到分析清单中的 `plan_id`）
- `plan_id`：按方案 ID 精确筛选（优先级高于 `summary_plan_id`）
- `only_with_recommendations`：仅返回有建议记录

`GET /device_api/collection-results/parent_collection_list/` 当前每条记录会补充：

- `issue_code`：建议编码摘要（来自分析清单）
- `recommendation`：建议文案摘要（来自分析清单）
- `error`：错误摘要（优先子方案错误，其次执行日志失败原因）

## 9. tasks.py 任务职责

`backend/apps/device_api/tasks.py` 当前主要承担“异步任务入口 + 采集编排 + 运行态留痕”职责，核心方法可分为 6 组：

### 9.1 运行态任务快照与事件留痕

- `get_runtime_task_snapshot`
- `_store_runtime_task_snapshot`
- `_build_runtime_task_snapshot`
- `_record_execution_event`

说明：

- 负责缓存异步任务进度、推送 websocket 事件、写入批次 / 设备 / 子方案级运行态执行日志

### 9.2 方案验证与单子方案调试

- `_validate_plan_for_device`
- `run_summary_plan_validation_task`
- `run_sub_plan_execute_task`

说明：

- 用于前端或人工验证“某父方案 / 某子方案在某台设备上是否具备执行条件并能否跑通”
- 这里校验的是协议启用、账号准备、执行模式匹配，不直接做平台画像绑定决策

### 9.3 设备 onboarding 与画像绑定编排

- `_load_onboarding_device`
- `_validate_onboarding_device`
- `onboard_network_device`

说明：

- 负责新纳管设备的首轮编排
- 典型链路是：设备准入校验 -> 首轮自动绑定 -> 首轮采集 -> 二次自动收敛
- 这是 `tasks.py` 中最接近“设备画像校验 / 自动绑定”的任务入口

### 9.4 全量采集批次调度

- `should_clear_history_before_batch`
- `should_clear_plan_data_before_batch`
- `split_runtime_control_kwargs`
- `_binding_source_priority`
- `_host_identity`
- `_has_executable_sub_plans`
- `_host_preference_key`
- `dedupe_batch_hosts`
- `plan_collect_device_main`

说明：

- 负责批次前清理、加载待采设备、按设备去重、处理 `manual` 优先、跳过无可执行子方案设备、批量下发 Celery 采集任务

### 9.5 单设备采集执行与结果处理

- `datas_to_cache`
- `clear_his_collect_res`
- `_get_collection_db`
- `_should_replace_snapshot_rows`
- `_build_snapshot_replace_filter`
- `_replace_snapshot_rows`
- `plan_collect_device`
- `_classify_temporary_netmiko_string_result`
- `_process_and_save_result`

说明：

- 负责单设备维度的父方案执行、子方案协议调用、结果解析、Mongo 落库、覆盖缺口分类、设备事实回填
- 当前“netmiko 返回字符串时区分无配置与模板解析失败”的临时策略也在这一层

### 9.6 采集后分析与辅助批量任务

- `analyze_collection_plan_bindings`
- `batch_update_device_name_by_snmp`

说明：

- `analyze_collection_plan_bindings` 现在仅保留 Celery 薄入口，具体绑定分析逻辑已迁到 `backend/apps/device_api/binding_analysis_service.py`
- `batch_update_device_name_by_snmp` 是独立的 SNMP 批量探测更新设备名称任务

### 9.7 两条核心调用链

全量采集主链：

- `plan_collect_device_main`
- `get_auto_device`
- `dedupe_batch_hosts`
- `plan_collect_device`
- `_process_and_save_result`
- `DeviceFactService.update_from_processed_data`

新设备纳管主链：

- `onboard_network_device`
- `PlatformProfileService.auto_bind_device_by_connection_priority`
- `get_auto_device`
- `plan_collect_device`
- `PlatformProfileService.auto_bind_devices`

职责边界：

- `tasks.py` 更偏向“什么时候跑、如何编排、如何留痕”
- `platform_profiles.py` 更偏向“如何匹配画像、如何自动绑定、如何审计覆盖”
- 后续若继续重构，优先把方案可执行性校验、批次去重规则、结果处理规则逐步下沉到独立 service


## 10. 当前文档入口

- [当前能力](./当前能力.md)
- [遗留任务](./遗留任务.md)
- [前端页面需求](./前端页面需求.md)
- [2026-03-30 全量采集结果分析与整改验收](./2026-03-30_全量采集结果分析与整改验收.md)

## 11. 证据文件

验收和灰度证据保留在当前目录的 `*.json` 文件中，用于追溯，不再单独展开为 phase Markdown 文档。
