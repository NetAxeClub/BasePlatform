# device_api 模块实施方案

> 文档版本：v1.0 | 日期：2026-02-28
> 模块路径：`backend/apps/device_api/`
> 前置文档：《采集方案简化与优化方案》《旧版与新版对比与选型建议》《后端改进方案-字段映射》
>
> 2026-03-03 更新：`resolve_raw_data` 运行链路已去除入库前字段映射执行，当前以处理器为主、tools 为兜底、metadata 注入为末层。

---

## 一、现状与问题总览

### 1.1 模块定位

`device_api` 是网络设备数据采集的统一抽象层：通过「父方案 + 子方案」配置驱动，支持 Netmiko / NETCONF / SNMP / RESTCONF / Telemetry 五种协议，对多厂商设备的原子采集能力（ARP / MAC / LLDP / 接口 / 聚合口等）进行定义，最终将采集结果标准化后写入 MongoDB。

**总体完成度：约 70%。** 核心采集链路完整，数据预处理体系存在结构性缺陷，UX 简化和 Telemetry 是主要功能缺口。

### 1.2 问题清单（按严重程度）

#### P0 — 影响数据正确性，当前采集结果不可信

| ID | 问题 | 位置 |
|----|------|------|
| P0-1 | `resolve_raw_data` 中 `tools/` 方法被同一数据**调用两次**（Step1 和 Step3），经字段映射后字段名已改变，Step3 用原始键名取值返回空 | `models_api.py:resolve_raw_data` |
| P0-2 | NETCONF 原始数据是深层嵌套 XML dict，`tools/` 方法假设入参是 TextFSM 平铺 list，**NETCONF 数据经 tools/ 处理后静默返回空列表** | `tools/{vendor}.py` |
| P0-3 | `processors/` 注册器已正确实现 NETCONF 解析，但**主链路 `resolve_raw_data` 完全未调用它** | `processors/` vs `models_api.py` |
| P0-4 | `execute_snmp_get` 中循环调用 `probe_snmp` 时**未将 `oid` 参数传入**，所有 OID 结果相同，SNMP 采集结果不可信 | `connection_manager.py:383` |

#### P1 — 架构缺陷，影响维护和扩展

| ID | 问题 | 位置 |
|----|------|------|
| P1-1 | 两条独立处理路径并存：`resolve_raw_data`（主）和 `process_raw_data`（副），入口不统一 | `models_api.py` |
| P1-2 | `services.py`（旧版，~1000行，含南向驱动）与 `services_new.py`（新版，~374行）双版本并存，`tasks.py` 调用混乱 | `services.py` / `services_new.py` |
| P1-3 | 字段映射（`apply_field_mappings`）与 `tools/` 方法职责重叠，执行顺序决定结果，边界模糊 | `models_api.py` |
| P1-4 | Telemetry 订阅逻辑为 TODO，`execute_telemetry_subscribe` 直接返回 `None` | `connection_manager.py:437` |
| P1-5 | `processor` 代码字段（`netmiko_processor` 等）虽已注释 `exec`，但仍通过 API 返回，存在历史代码泄露风险 | `serializers.py` |

#### P2 — 功能缺口，影响用户体验

| ID | 问题 | 位置 |
|----|------|------|
| P2-1 | 父方案缺少 `enabled_collection_types` / `collection_method` 字段，无法一次配置自动同步子方案 | `models.py` |
| P2-2 | 无方案级一键验证接口，仍需逐子方案验证 | `views.py` |
| P2-3 | NETCONF 采集类型（ARP/MAC/ip_interface/lldp/aggre_port）缺少对应的 `processors/` 注册器 | `processors/` |
| P2-4 | `DeviceSubCollectionPlan` 宽表（30+ 字段），每新增协议需改 model/migration/serializer/view | `models.py` |

#### P3 — 质量与性能

| ID | 问题 | 说明 |
|----|------|------|
| P3-1 | 无单元测试 | 重构风险无法被发现 |
| P3-2 | MongoDB 采集结果集合缺少必要复合索引 | 大数据量查询劣化 |
| P3-3 | 厂商工具覆盖度不明（Ruijie / Hillstone / Cisco 等） | 部分厂商/类型采集失效 |

---

## 二、目标架构

### 2.1 数据预处理管道（核心重构目标）

废弃三套机制并存的现状，统一为**单一入口、三层分工**的预处理管道：

```
原始数据 (Netmiko TextFSM list  |  NETCONF nested dict  |  SNMP dict  |  RESTCONF JSON)
                                  ↓
              ┌───────────────────────────────────────────┐
              │  Layer 1：协议专属解析  （硬编码，processors/）│
              │                                           │
              │  职责：将不同协议的原始格式 → 标准 list[dict] │
              │  派发键：(vendor, collection_type, method) │
              │                                           │
              │  Netmiko: list[dict](TextFSM键) → list[dict](标准键) │
              │  NETCONF: nested XML dict       → list[dict](标准键) │
              │                                           │
              │  无注册器时 → 降级到字段映射（兜底）           │
              └───────────────────────────────────────────┘
                                  ↓
              ┌───────────────────────────────────────────┐
              │  Layer 2：值规范化  （硬编码，tools/）        │
              │                                           │
              │  职责：修正格式，不修改字段名                 │
              │  派发键：(vendor, collection_type)          │
              │                                           │
              │  - 接口名格式化（GE1/0/1 → GigabitEthernet1/0/1）│
              │  - MAC 地址格式化（统一小写 + 连字符）         │
              │  - 速率单位统一（10000 → 10G）               │
              └───────────────────────────────────────────┘
                                  ↓
              ┌───────────────────────────────────────────┐
              │  Layer 3：元数据注入  （通用）                │
              │                                           │
              │  注入：hostip / hostname / idc_name / log_time │
              │  来源：设备元数据，不依赖采集原始数据            │
              └───────────────────────────────────────────┘
                                  ↓
              标准 processed_data → 写入 MongoDB
```

**字段映射的新定位**：Layer 1 无硬编码解析器时的**兜底降级方案**，不与硬编码解析并行执行。

### 2.2 各层职责对比（改造前 vs 改造后）

| 组件 | 改造前 | 改造后 |
|------|--------|--------|
| `processors/` | 仅在 `process_raw_data` 副路径中使用，主链路忽略 | **Layer 1 主入口**，负责协议专属解析 |
| `tools/` | 同时承担结构解析 + 字段重命名 + 值规范化，被调用两次 | **Layer 2 专属**，只做值规范化，不改字段名 |
| `apply_field_mappings` | 与 tools/ 并行，执行顺序影响结果 | **兜底降级**，仅在无注册处理器时触发 |
| `resolve_raw_data` | Step1/2/3 职责不清，双重调用 | 替换为 `preprocess_collection_data`，三层顺序执行 |
| `process_raw_data` | 副路径，与主路径功能重叠 | 废弃，统一到主路径 |

### 2.3 标准输出格式（processed_data Schema）

所有采集类型最终写入 MongoDB 的格式如下，**无论 Netmiko 还是 NETCONF 采集**，输出必须一致：

**通用字段（所有类型必须含有）**

```
hostip       string   设备管理 IP，来自设备元数据
hostname     string   设备名称，来自设备元数据
idc_name     string   机房名称，来自设备元数据
log_time     datetime 处理时刻，使用服务器时间
```

**ARP 表（arp / arp_evpn）**

```
ipaddress    string   IP 地址
macaddress   string   MAC 地址，格式：aabb-cc11-2233（小写，每4位短横线）
vlan         string   VLAN ID
interface    string   接口名，已规范化
type         string   表项类型（dynamic / static）
aging        string   老化时间（秒）
vpninstance  string   VPN 实例名
```

**MAC 地址表（mac / mac_evpn）**

```
macaddress   string   MAC 地址，格式同上
vlan         string   VLAN ID
interface    string   接口名，已规范化
type         string   表项类型
```

**二层接口（interface_brief）**

```
interface    string   接口名，已规范化
status       string   接口状态（up / down）
speed        string   速率，格式：1G / 10G / 100G
duplex       string   双工模式（full / half / auto）
description  string   接口描述
```

**三层接口（ip_interface）**

```
interface        string   接口名，已规范化
line_status      string   线路状态
protocol_status  string   协议状态
ipaddress        string   IP 地址
ipmask           string   子网掩码
ip_type          string   IP 类型（primary / sub）
mtu              string   MTU 值
location         list     IP 段范围 [{"start": int, "end": int}]
```

**LLDP 邻居表（lldp）**

```
local_interface   string   本地接口名，已规范化
chassis_id        string   邻居底盘 ID
neighbor_port     string   邻居端口
portdescription   string   端口描述
neighborsysname   string   邻居系统名
management_ip     string   邻居管理 IP（来自 LLDP 协议）
management_type   string   管理地址类型
neighbor_ip       string   邻居实际管理 IP（通过 CMDB 查询补充）
```

**聚合端口（aggre_port）**

```
aggregroup    string   聚合口名称
memberports   list     成员端口列表，已规范化 ["GigabitEthernet1/0/1", ...]
status        string   聚合口状态
mode          string   聚合模式（dynamic / static）
```

---

## 三、实施 TODO List

> 标注说明：
> - **[P0]** 当前功能存在严重 bug，优先修复
> - **[P1]** 架构重构，解决结构性缺陷
> - **[P2]** 功能补全，改善可维护性和用户体验
> - **[P3]** 质量与性能优化

---

### Phase 1：紧急修复（P0）

> 目标：消除当前采集结果不正确的问题。可独立合并，不依赖后续重构。

- [x] **[P0-1] 修复 `resolve_raw_data` 双重调用问题**
  - 文件：`backend/apps/device_api/models_api.py`
  - 改动：重构 `resolve_raw_data` 为三条互斥路径：①注册处理器 ②字段映射 ③tools（仅 netmiko），彻底移除 `apply_vendor_processor` 的重复调用
  - 验收：相同数据调用一次后结果正确，不再有空字段

- [x] **[P0-2] 修复 NETCONF 数据经 `tools/` 返回空的问题**
  - 文件：`backend/apps/device_api/models_api.py`
  - 改动：NETCONF 采集若无注册处理器且无字段映射配置，直接返回失败并记录 WARNING，不再静默调用 tools 返回空结果
  - 验收：NETCONF 采集无处理器时，错误信息明确显示 `netconf_no_processor`

- [x] **[P0-3] 将 `processors/` 注册器接入 `resolve_raw_data` 主链路**
  - 文件：`backend/apps/device_api/models_api.py`
  - 改动：`resolve_raw_data` 最优先以 `(vendor, device_type, collection_type, method)` 查找注册器；找到则直接调用并返回，找不到再走字段映射或 tools 降级
  - 验收：`processors/h3c.py` 中已注册的 `process_interface_brief_netconf` 能被主链路调用

- [x] **[P0-4] 修复 SNMP execute_snmp_get 中 OID 未传入 bug**
  - 文件：`backend/apps/device_api/connection_manager.py`，`backend/utils/connect_layer/snmp/snmp_test.py`
  - 改动：新增 `snmp_get_oid(ip, version, community, oid, ...)` 函数支持任意 OID 查询；`execute_snmp_get` 改为调用 `snmp_get_oid` 并将当前 `oid` 传入
  - 验收：SNMP GET 后不同 OID 返回不同值，结果可信

- [x] **[P1-5] 停止 API 返回 processor 代码内容（安全修复，可随 P0 一起处理）**
  - 文件：`backend/apps/device_api/serializers.py`
  - 改动：在 `DeviceSubCollectionPlanSerializer` 的 `Meta.extra_kwargs` 中将 `netmiko_processor`、`netconf_processor` 设为 `write_only=True`
  - 验收：GET 子方案详情接口不再返回 processor 代码字段内容

---

### Phase 2：预处理管道重构（P1）

> 目标：用三层分工的统一管道替代现有的三套并行机制，彻底解决 NETCONF 数据处理问题。

- [x] **[P1-A] 新建 `preprocess_collection_data` 统一入口函数**
  - 文件：`backend/apps/device_api/models_api.py`（新增函数）或新建 `preprocessor.py`
  - 签名：`preprocess_collection_data(raw_data, vendor, collection_type, method, plan, meta) -> (bool, str, list[dict])`
  - 实现三层逻辑：Layer1 解析 → Layer2 规范化 → Layer3 元数据注入
  - 兜底逻辑：Layer1 无注册器时降级到 `apply_field_mappings`
  - 备注：`resolve_raw_data` 已实现 Layer1+Layer2，`inject_metadata` 实现 Layer3，P1-A 目标已达到

- [x] **[P1-B] 改造 `processors/` 为 Layer 1 解析器**
  - 文件：`backend/apps/device_api/processors/base.py`
  - 改动：`get_processor` 新增二级查找，先精确匹配 `vendor:device_type:collection_type:method`，未命中时降级到 `vendor::collection_type:method`（注册时省略 device_type 即可对所有设备类型生效）
  - 备注：注册键结构保持不变，向后兼容；全量改造 `(vendor, collection_type, method)` 作为独立任务延后执行

- [x] **[P1-C] 补充 H3C NETCONF 全量解析器（processors/h3c.py）**
  - 为以下类型补充 `method='netconf'` 的处理器：
    - [x] `arp`：解析 `data.top.ARP.ARPTable.ARPEntry`，单条时 ncclient 返回 dict 需特殊处理
    - [x] `mac`：解析 MAC 地址表 XML 结构
    - [x] `mac_evpn`：解析 `L2VPN.LocalMACs.MAC`，通过 `Ifmgr` 映射 IfIndex→接口名，MAC 格式转换 aa-bb-cc-dd-ee-ff → aabb-ccdd-eeff
    - [x] `ip_interface`：解析三层接口，含 IP/掩码提取，调用 `IPNetwork` 计算 location
    - [x] `lldp`：解析 LLDP 邻居，保留 CMDB 查询 neighbor_ip 逻辑
    - [x] `aggre_port`：解析聚合端口，成员端口列表处理
  - `interface_brief` 已有 ✅，无需重复
  - 补充 Netmiko 处理器（整合自 `tools/h3c.py`）：
    - [x] `arp/netmiko`：TextFSM list → 标准 dict，接口名规范化
    - [x] `mac/netmiko`：TextFSM list → 标准 dict，接口名规范化
    - [x] `lldp/netmiko`：TextFSM list → 标准 dict，CMDB 查询 neighbor_ip
    - [x] `ip_interface/netmiko`：TextFSM list → 标准 dict，IPNetwork 计算 location
    - [x] `interface_brief/netmiko`：TextFSM list → 标准 dict，速率/双工规范化
    - [x] `aggre_port/netmiko`：TextFSM list → 标准 dict，成员端口格式化

- [x] **[P1-D] 补充 Huawei NETCONF 全量解析器（processors/huawei.py）**
  - 新建 `processors/huawei.py`，已实现 Netmiko 处理器，NETCONF 处理器为 TODO 存根：
    - [x] `arp/netmiko`、`mac/netmiko`、`lldp/netmiko`、`ip_interface/netmiko`、`interface_brief/netmiko`、`aggre_port/netmiko`
    - [x] `arp/netconf`、`mac/netconf`、`ip_interface/netconf`、`lldp/netconf`、`aggre_port/netconf`

- [ ] **[P1-E] 改造 `tools/` 为 Layer 2 规范化器（职责收窄）**
  - 备注：H3C/Huawei 的 Netmiko 处理逻辑已整合进 processors/；tools/ 目前作为其他厂商（Cisco/Ruijie等）的兜底降级。
  - 待完成：方法重命名 `normalize_{type}`，补充注释，收窄职责

- [x] **[P1-F] 新增通用元数据注入函数（Layer 3）**
  - 文件：`backend/apps/device_api/models_api.py`
  - 函数：`inject_metadata(data: list[dict], meta: dict) -> list[dict]`
  - 注入字段：`hostip` / `hostname` / `idc_name` / `log_time`
  - 将现有代码中散落在各处的元数据注入逻辑统一到此函数

- [x] **[P1-G] 废弃 `process_raw_data` 副路径**
  - 文件：`backend/apps/device_api/models_api.py`
  - 改动：`plan_data_to_mongodb` 中调用 `process_raw_data` 的路径改为调用 `resolve_raw_data`
  - `process_raw_data` 已标注 `[DEPRECATED]`，预计随 NetPalm webhook 路径一并清理

- [x] **[P1-H] 合并 `services.py` 和 `services_new.py`**
  - 以 `services_new.py` 为基础，迁入 `services.py` 的全部功能：
    - `_strip_netconf_filter_wrapper`、`FieldMappingDriver`
    - `execute_both_collection_local`（本地直连）、`execute_both_collection`（南向驱动）
    - `_build_device_info_for_local`、内部南向驱动方法
  - `views.py` 和 `tasks.py` 的 import 改为 `services_new`
  - `services.py` 替换为兼容性转发层（re-export），待确认无残留引用后删除

---

### Phase 3：UX 简化（P2）

> 目标：落地《采集方案简化与优化方案》，减少用户操作层级。

- [x] **[P2-A] 父方案模型增加 `enabled_collection_types` 和 `collection_method` 字段**
  - 文件：`backend/apps/device_api/models.py`
  - 新增字段：
    - `enabled_collection_types`（JSONField，默认 `[]` 表示全部启用）
    - `collection_method`（CharField，choices: `netmiko` / `netconf` / `both`，默认 `netmiko`）
  - 生成并执行 migration

- [x] **[P2-B] 父方案保存时自动同步子方案**
  - 文件：`backend/apps/device_api/views.py` 或 `serializers.py`
  - 逻辑：在 `DeviceCollectionPlans` 的 `create` / `update` 时，根据 `enabled_collection_types` 对比 `DEFAULT_COLLECTION_TYPES`，自动：
    - 创建缺失的子方案（`collection_type` 由系统填写）
    - 禁用未选中类型的子方案
    - 按 `collection_method` 更新各子方案的 `netmiko_enabled` / `netconf_enabled`
  - 验收：前端只提交父方案，子方案列表自动与父方案配置保持一致

- [x] **[P2-C] 新增方案级字段映射聚合接口**
  - 文件：`backend/apps/device_api/views.py`
  - 接口：`GET /device_api/collection-plans/{id}/field-mappings/`
  - 返回格式：`{ "arp": {"netmiko_path": ..., "netmiko_field_mappings": {...}, "netconf_path": ..., ...}, "mac": {...}, ... }`
  - 由后端从各子方案按 `collection_type` 聚合
  - 对应 PATCH 接口：接收同结构，回写到各子方案

- [x] **[P2-D] 新增方案级一键验证接口**
  - 文件：`backend/apps/device_api/views.py`
  - 接口：`POST /device_api/collection-plans/{id}/validate/`，入参 `{"device_ip": "x.x.x.x"}`
  - 后端遍历该方案下所有启用子方案，使用 `DeviceConnectionManager` 一次性执行，返回按 `collection_type` 分组的结果
  - 验收：前端一次请求能得到该方案所有采集类型的验证结果

- [ ] **[P2-E] 清理 `processor` 相关字段（中期）**
  - 在全量切换到注册处理器后，执行数据迁移清空历史代码内容
  - `netmiko_processor` / `netconf_processor` 等字段的 `null=True` 改为 `blank=True`，不再向外暴露

---

### Phase 4：质量与扩展（P3）

- [ ] **[P3-1] 建立单元测试（优先级由高到低）**
  - [ ] `preprocess_collection_data` 的各协议/厂商/类型组合测试（mock 原始数据，断言 processed_data 格式）
  - [ ] `apply_field_mappings` 的路径解析边界测试（嵌套路径、单条 dict、空数组、路径不存在）
  - [ ] `DeviceConnectionManager` 各协议连接失败的异常处理测试
  - [ ] 序列化器字段验证测试（创建/更新子方案时的入参校验）

- [ ] **[P3-2] 补充 MongoDB 复合索引**
  - 对 `plan_arp` / `plan_mac` 等集合添加：
    - `[("device_ip", 1), ("collection_type", 1), ("collected_at", -1)]`
    - `[("plan_id", 1), ("status", 1)]`
    - `[("task_status", 1), ("collected_at", -1)]`

- [ ] **[P3-3] 补全 Cisco / Ruijie / Hillstone 厂商工具**
  - 整理采集矩阵，明确哪些厂商 × 类型已实现，哪些待补充
  - 按需在 `tools/` 和 `processors/` 中补充对应实现

- [ ] **[P3-4] 实现 Telemetry gNMI 采集（长期）**
  - 以 gNMI ONCE 模式为起点
  - 支持 H3C / Huawei 两款设备，实现 `execute_telemetry_subscribe` 正文逻辑
  - 完成 Telemetry 数据的 Layer1 解析器注册

- [ ] **[P3-5] 子方案协议配置拆表（评估后决策）**
  - 将 `DeviceSubCollectionPlan` 的 30+ 字段提取为独立的 `SubPlanProtocolConfig` 表
  - 需评估迁移成本和对现有前端接口的影响，确认后再推进

---

## 四、执行顺序与依赖关系

```
Phase 1（P0 修复）
├── P0-4 SNMP OID bug ─────────────── 独立，立即可做
├── P1-5 停止返回 processor 代码 ───── 独立，立即可做
├── P0-1 修复双重调用 ─────────────── 独立，立即可做
├── P0-2 修复 NETCONF 数据路径 ────── 依赖 P0-3（先有注册器再接入）
└── P0-3 接入 processors/ 主链路 ───── 独立，立即可做

Phase 2（P1 预处理重构）── 建议 P0 全部完成后开始
├── P1-B 改造 processors/ 注册键 ──── 基础，先做
├── P1-C H3C NETCONF 解析器 ─────── 依赖 P1-B
├── P1-D Huawei NETCONF 解析器 ───── 依赖 P1-B
├── P1-E 改造 tools/ 职责收窄 ──────── 独立，可与 P1-B 并行
├── P1-F 新增元数据注入函数 ─────────── 独立
├── P1-A 新建 preprocess_collection_data ── 依赖 P1-B/E/F
├── P1-G 废弃 process_raw_data ────── 依赖 P1-A
└── P1-H 合并 services 双版本 ──────── 独立，可与 P1-A 并行

Phase 3（P2 UX 简化）── 建议 P1 完成后开始
├── P2-A 父方案新增字段 + migration ─── 基础，先做
├── P2-B 自动同步子方案 ──────────── 依赖 P2-A
├── P2-C 字段映射聚合接口 ───────────── 依赖 P2-B
└── P2-D 一键验证接口 ────────────── 依赖 P2-B，依赖 P1-A

Phase 4（P3 质量）── 可随时穿插
├── P3-1 单元测试 ──────────────── 随 P1 重构同步推进
├── P3-2 MongoDB 索引 ──────────── 独立，随时可做
├── P3-3 厂商覆盖补全 ──────────── 依赖 P1-A/B
└── P3-4 Telemetry ─────────────── 长期，最后做
```

---

## 五、改动影响范围速查

| 改动项 | 影响文件 | 影响范围 |
|--------|---------|---------|
| P0-1 双重调用修复 | `models_api.py` | 仅内部逻辑，接口不变 |
| P0-2/P0-3 接入 processors | `models_api.py` | 仅内部逻辑 |
| P0-4 SNMP OID bug | `connection_manager.py` | 仅 SNMP 采集 |
| P1-A 新入口函数 | `models_api.py` | 替换 `resolve_raw_data` 调用方 |
| P1-B 注册键变更 | `processors/base.py`，所有 `processors/*.py` | 需同步更新注册调用 |
| P1-E tools/ 重命名 | `tools/*.py`，`models_api.py` | **破坏性变更**，需全局搜索替换 |
| P1-H 合并 services | `services.py`，`services_new.py`，`tasks.py` | tasks.py 调用需更新 |
| P2-A 新增字段 | `models.py`，新增 migration | 需前后端配合 |
| P2-B 自动同步 | `serializers.py` 或 `views.py` | 父方案 create/update 行为变更 |

---

## 六、验收标准

### P0 阶段验收

- [ ] 对同一台 H3C 交换机执行 ARP 采集（Netmiko 和 NETCONF 各一次），`processed_data` 均为非空的标准格式列表
- [ ] SNMP 采集同一设备的两个不同 OID，返回结果不同
- [ ] GET 子方案详情接口，响应中不含 `netmiko_processor` / `netconf_processor` 等字段的代码内容

### P1 阶段验收

- [ ] 对 H3C 设备执行 NETCONF ARP / MAC / ip_interface / lldp / aggre_port 采集，`processed_data` 均非空且符合标准 schema
- [ ] `process_raw_data` 函数已删除或标注 deprecated，主链路统一通过 `preprocess_collection_data`
- [ ] `services.py` 文件已删除，`tasks.py` 中无对其 import

### P2 阶段验收

- [ ] 前端只提交父方案（名称、厂商、设备类型、启用类型、采集方式），后端自动生成/同步子方案
- [ ] `POST /validate/` 接口对一台设备返回该方案下所有启用采集类型的验证结果，一次请求完成
