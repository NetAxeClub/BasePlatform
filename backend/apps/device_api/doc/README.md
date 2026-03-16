# device_api 模块文档

**更新时间：2026-03-16**

## 📋 模块概述

`device_api` 是网络设备数据采集的统一抽象层，负责：
- 多协议支持：Netmiko / NETCONF / SNMP / RESTCONF / Telemetry
- 方案管理：父方案 + 子方案配置驱动
- 数据处理：协议解析 → 值规范化 → 元数据注入 → MongoDB 入库
- 采集类型：ARP / MAC / LLDP / 接口信息 / 聚合端口等

---

## 📚 文档索引

### 最新归档

- [工作区开发归档（2026-03-16）](../../../../doc/20-device_api开发归档-2026-03-16.md)
  - 记录当前工作区未提交进度、已完成能力、验证结果和下次恢复建议

### 核心文档（建议优先阅读）

#### 1. [模块评估报告.md](./模块评估报告.md)
**功能**：模块现状评估与能力盘点
- 已实现能力：采集执行链路、数据预处理管道、标准字段约束
- 当前缺口：部分 NETCONF 处理器待补齐、厂商覆盖不足
- 风险提示：处理器缺失时的降级策略

#### 2. [数据预处理评估与设计方案.md](./数据预处理评估与设计方案.md)
**功能**：数据预处理三层架构设计
- **Layer 1**：协议专属解析（processors/）
- **Layer 2**：厂商兜底规范化（tools/）
- **Layer 3**：元数据注入（hostip/hostname/idc_name/log_time）
- **关键变更**：运行时已移除入库前字段映射执行，改为处理器优先策略

#### 3. [实施方案与TODO.md](./实施方案与TODO.md)
**功能**：分阶段实施任务清单与验收标准
- **Phase 1**：P0 紧急修复（已完成 ✅）
- **Phase 2**：P1 预处理管道重构（进行中 🚧）
- **Phase 3**：P2 UX 简化（待启动）
- **Phase 4**：P3 质量与扩展（长期）

#### 4. [采集方案简化与优化方案.md](./采集方案简化与优化方案.md)
**功能**：前后端配置体验简化方向
- 目标：父方案主导，子方案由后端自动维护
- 优化：采集类型多选、采集方式统一、一键验证
- 实施：分阶段落地，最小化用户操作步骤

---

### 历史参考文档

#### 5. [后端改进方案-字段映射.md](./后端改进方案-字段映射.md)
**说明**：早期"字段映射为主"的后端协同方案
⚠️ **注意**：当前运行链路已调整为"处理器优先 + 标准字段补齐"，不再在入库前执行字段映射转换

#### 6. [采集方案-旧版与新版对比与选型建议.md](./采集方案-旧版与新版对比与选型建议.md)
**说明**：automation 与 device_api 的架构对比和选型说明

---

## 🎯 当前进度

### ✅ 已完成（Phase 1）
- [x] 修复 `resolve_raw_data` 双重调用问题
- [x] 修复 NETCONF 数据处理空结果问题
- [x] 将 `processors/` 注册器接入主链路
- [x] 修复 SNMP OID 未传入 bug
- [x] 停止 API 返回 processor 代码内容（安全修复）
- [x] 新增元数据注入函数（Layer 3）
- [x] 废弃 `process_raw_data` 副路径
- [x] 合并 `services.py` 和 `services_new.py`

### 🚧 进行中（Phase 2）
- [x] H3C Netmiko 处理器全量补齐（arp/mac/lldp/ip_interface/interface_brief/aggre_port）
- [x] H3C NETCONF 处理器：arp/mac/ip_interface/lldp/aggre_port/mac_evpn 已实现
- [x] Huawei Netmiko 处理器全量补齐
- [x] Huawei NETCONF 处理器：arp/mac/ip_interface/lldp/aggre_port 已实现
- [ ] 改造 `tools/` 为 Layer 2 规范化器（职责收窄）

### ✅ 已完成（Phase 3 - UX 简化）
- [x] 父方案模型增加 `enabled_collection_types` 和 `collection_method` 字段
- [x] 父方案保存时自动同步子方案（含 `sync_collect_plans`）
- [x] 新增方案级字段映射聚合接口
- [x] 新增方案级一键验证接口

### 🔮 持续推进（Phase 4）
- [x] 预处理链路回归测试：`resolve_raw_data` 处理器优先、`NotImplementedError` 降级、NETCONF 缺处理器分支
- [x] 字段映射路径测试：嵌套数组路径、`path_config`、缺失数组分支
- [x] `DeviceConnectionManager` 异常处理测试：SSH 缺账号、SNMP v3 用户名透传、RESTCONF token、Telemetry 缺依赖
- [x] 本地执行链路测试：本地结果落库、`plan_*` 集合写入、部分成功聚合
- [x] 南向驱动执行链路测试：Netmiko/NETCONF payload 拼装、`get/get_config` 分支、无 XML 模板错误返回
- [x] 序列化器与执行入口边界测试：SNMP/NETCONF/Telemetry 必填项、`execute_sub_plan` 本地入口、`validate_execution_params` 本地/南向分流
- [x] 补充 MongoDB 复合索引：`indexes.py` + `ensure_device_api_indexes` 管理命令 + `AppConfig.ready()` best-effort 启动
- [ ] 补全 Cisco / Ruijie / Hillstone 厂商工具
- [ ] 实现 Telemetry gNMI 采集

---

## 🔑 关键入口

运行时行为以代码为准，关键文件：
- **主调度**：`apps/device_api/tasks.py` → `plan_collect_device_main`
- **数据预处理**：`apps/device_api/models_api.py` → `resolve_raw_data`
- **协议处理器**：`apps/device_api/processors/` → 按厂商/协议/类型注册
- **标准字段定义**：`apps/device_api/fields_mapping.py` → `field_mapping`
- **连接管理**：`apps/device_api/connection_manager.py` → `DeviceConnectionManager`

---

## 📊 架构图示

```
原始数据 (Netmiko/NETCONF/SNMP/RESTCONF)
           ↓
┌─────────────────────────────────┐
│ Layer 1: 协议专属解析 (processors/) │
│  - 派发键: vendor + type + method  │
│  - 无注册器时降级到字段映射          │
└─────────────────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Layer 2: 值规范化 (tools/)        │
│  - 接口名/MAC/速率格式统一          │
│  - 不修改字段名                    │
└─────────────────────────────────┘
           ↓
┌─────────────────────────────────┐
│ Layer 3: 元数据注入               │
│  - hostip/hostname/idc_name      │
│  - log_time                      │
└─────────────────────────────────┘
           ↓
    MongoDB (按类型分集合)
```

---

## 🚀 下一步行动

1. **优先级 P1**：继续收窄 `tools/` 的职责，明确只保留 Layer 2 规范化
2. **优先级 P2**：补结果查询与列表接口的性能/边界测试
3. **优先级 P3**：补剩余厂商覆盖与 Telemetry 真执行

---

## 📝 文档维护说明

- 本 README 作为文档导航索引，不包含详细技术方案
- 各专题文档独立维护，保持内容聚焦
- 运行时行为以代码为准，文档仅作设计参考
- 历史方案文档保留用于追溯决策背景，但不代表当前实现
