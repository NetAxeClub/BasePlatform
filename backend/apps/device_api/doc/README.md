# device_api 功能说明

## 1. 模块定位

`device_api` 是当前网络设备采集主链，负责：

- 采集方案管理：父方案 + 子方案
- 多协议执行：Netmiko / NETCONF / SNMP / RESTCONF / Telemetry
- 数据标准化：处理器解析、值规范化、元数据注入
- 结果入库：统一写入 `plan_<collection_type>`
- 设备事实发现与回写

## 2. 当前实现方式

### 2.1 方案模型

- 父方案：`DeviceCollectionPlans`
- 子方案：`DeviceSubCollectionPlan`
- 设备绑定：`PlansToDevice`

父方案负责采集类型和采集方式的聚合配置，子方案负责具体协议细节。

### 2.2 预处理链路

当前运行链路按以下顺序处理采集结果：

1. `processors/`
   - 协议/厂商专属解析
2. `tools/`
   - 值规范化兜底
3. 元数据注入
   - `hostip`
   - `hostname`
   - `idc_name`
   - `log_time`

### 2.3 标准化结果合同

标准结果统一写入：

- `plan_arp`
- `plan_mac`
- `plan_lldp`
- `plan_aggre_port`
- `plan_ip_interface`
- `plan_interface_brief`
- 其它类型继续使用 `plan_<collection_type>`

所有结果必须保留：

- `hostip`
- `hostname`
- `idc_name`
- `log_time`
- `summary_plan_id`
- `plan_id`
- `collection_type`
- `collection_method`
- `execute_time`

## 3. 当前重点能力

### 3.1 采集执行

- 主调度：`backend/apps/device_api/tasks.py`
- 本地执行：`DeviceCollectionService.execute_both_collection_local`
- 南向回调入库：`plan_data_to_mongodb` / `celery_data_mongodb`

### 3.2 结果查询

重点接口：

- `/base_platform/device_api/collection-results/latest/`
- `/base_platform/device_api/devices/{serial_num}/facts/`
- `/base_platform/device_api/devices/{serial_num}/capabilities/`
- `/base_platform/device_api/plans-to-device/`

### 3.3 已合并的重要改进

- 标准化采集合同已冻结
- 接口利用率分析触发链路已统一接入
- 地址定位消费链路已按标准结果对齐

## 4. 关键文件

- `backend/apps/device_api/tasks.py`
- `backend/apps/device_api/services_new.py`
- `backend/apps/device_api/models_api.py`
- `backend/apps/device_api/contract.py`
- `backend/apps/device_api/analysis_hooks.py`
- `backend/apps/device_api/connection_manager.py`
- `backend/apps/device_api/processors/`

## 5. 当前边界

- 新增采集能力应优先进入 `device_api`
- 不应继续在 `apps.automation` 增加采集实现
- `asset` 模型结构不在 `device_api` 内直接改造

## 6. 推荐验证

```bash
backend/venv/bin/python backend/manage.py test \
  apps.device_api.test_collection_contract \
  apps.device_api.test_interface_analysis_hooks -v 2
```

## 7. 后续任务

详细待办见：

- [后续任务](./后续任务.md)
