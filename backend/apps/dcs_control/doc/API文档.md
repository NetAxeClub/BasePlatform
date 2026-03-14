# DCS Control 模块 API 文档

> 版本：v1.0 | 更新时间：2026-03-02
> Base URL：`/api/dcs_control/`
> 认证方式：Session / Token（部分接口豁免认证，详见各接口说明）
> 响应格式：`application/json`

---

## 目录

| 功能模块 | 接口路径 | 方法 |
|---------|---------|------|
| [一键封堵](#一键封堵) | `/deny_key/` | GET / POST |
| [地址对象](#地址对象) | `/address_set/` | GET / POST |
| [服务对象](#服务对象) | `/service_set/` | GET / POST |
| [DNAT 公网发布](#dnat-公网发布) | `/dnat/` | GET / POST |
| [安全策略](#安全策略) | `/sec_policy/` | GET / POST |

---

## 公共说明

### 厂商标识（vendor）

所有接口中 `vendor` 字段不区分大小写，系统会自动规范化为首字母大写形式：

| 传入值（示例） | 规范化结果 |
|-------------|---------|
| `hillstone` / `Hillstone` / `HILLSTONE` | `Hillstone` |
| `h3c` / `H3C` | `H3C` |
| `huawei` / `Huawei` / `HUAWEI` | `Huawei` |

### 通用响应结构

```json
{
  "code": 200,
  "message": "OK",
  "data": "..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | integer | `200` 成功，`400` 业务错误 |
| `message` / `msg` | string | 操作结果描述 |
| `data` | any | 返回数据（异步任务时为 Celery Task ID） |

### 异步任务说明

POST 操作（封堵、地址对象变更、DNAT 变更、安全策略变更）均为**异步执行**，响应中 `data` 字段为 Celery Task ID，可用于追踪任务执行状态。

---

## 一键封堵

**路径**：`/deny_key/`
**认证**：需要（仅 POST）

### GET — 查询地址对象策略引用次数

查询指定防火墙设备上某地址对象被安全策略引用的匹配次数。

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识，枚举：`Hillstone` / `H3C` / `Huawei` |
| `hostip` | string | 是 | 设备管理 IP，如 `192.168.1.1` |
| `address_book` | string | 是 | 地址对象名称 |

**成功响应**

```json
{
  "code": 200,
  "data": {
    "hostip": "192.168.1.1",
    "address_book": "block_obj_001",
    "count": 3
  },
  "msg": "ok"
}
```

**失败响应**

```json
{ "code": 400, "msg": "未查询到匹配的数据" }
{ "code": 400, "msg": "vendor 必须是 ['Hillstone', 'H3C', 'Huawei'] 其中一个" }
```

---

### POST — 执行一键封堵 / 解封

对指定设备组下的所有防火墙设备批量下发封堵或解封 IP 的操作，任务并行分发到 Celery。

**请求体（application/json）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `inventory_id` | integer | 是 | 封堵目标设备组 ID |
| `ip_mask` | array[string] | 条件必填 | IP/掩码列表，格式 `["x.x.x.x/xx"]`，与 `range_*` 二选一 |
| `range_start` | string | 条件必填 | IP 范围起始，格式 `x.x.x.x` |
| `range_end` | string | 条件必填 | IP 范围结束，格式 `x.x.x.x` |
| **操作类型**（以下必须且只能传一个） | | | |
| `add_detail_ip` | boolean | 条件必填 | `true`：封堵，按 IP/掩码模式新增，需要 `ip_mask` |
| `add_detail_exclude_ip` | boolean | 条件必填 | `true`：封堵（排除模式），需要 `ip_mask` |
| `add_detail_range` | boolean | 条件必填 | `true`：封堵，按 IP 范围新增，需要 `range_start` + `range_end` |
| `add_detail_exclude_range` | boolean | 条件必填 | `true`：封堵（排除范围模式），需要 `range_start` + `range_end` |
| `del_detail_ip` | boolean | 条件必填 | `true`：解封，按 IP/掩码模式删除，需要 `ip_mask` |
| `del_detail_exclude_ip` | boolean | 条件必填 | `true`：解封（排除模式），需要 `ip_mask` |
| `del_detail_range` | boolean | 条件必填 | `true`：解封，按 IP 范围删除，需要 `range_start` + `range_end` |
| `del_detail_exclude_range` | boolean | 条件必填 | `true`：解封（排除范围模式），需要 `range_start` + `range_end` |

**请求示例（封堵 IP 段）**

```json
{
  "inventory_id": 12,
  "ip_mask": ["10.1.0.0/24", "10.2.0.100/32"],
  "add_detail_ip": true
}
```

**请求示例（按范围解封）**

```json
{
  "inventory_id": 12,
  "range_start": "10.1.0.1",
  "range_end": "10.1.0.254",
  "del_detail_range": true
}
```

**成功响应**

```json
{
  "code": 200,
  "message": "OK",
  "data": "c3d4e5f6-xxxx-xxxx-xxxx-aabbccddeeff"
}
```

**失败响应**

```json
{ "code": 400, "message": "重复的任务参数", "data": [] }
```

---

## 地址对象

**路径**：`/address_set/`
**认证**：豁免（无需认证）

### GET — 查询设备地址对象列表

查询指定防火墙设备上当前已有的地址对象数据。

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [
    { "name": "addr_obj_web", "hostip": "192.168.1.1", "ip": [{"ip": "10.0.0.1/32"}] }
  ],
  "count": 1
}
```

> Hillstone 从 MongoDB 返回；H3C / Huawei 通过 NETCONF 实时采集。

---

### POST — 地址对象操作

支持新建/删除地址对象，以及对对象内条目（成员）的增删。

**请求体（application/json）**

**公共字段（必填）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP，格式 `x.x.x.x` |
| `hostid` | integer | 是 | 设备资产 ID |
| `name` | string | 是 | 地址对象名称（非空字符串） |

**操作类型字段（必须且只能传一个）**

| 字段 | 说明 | 额外必填字段 |
|------|------|-------------|
| `add_object: true` | 新建地址对象（空对象） | — |
| `del_object: true` | 删除整个地址对象 | — |
| `add_detail_ip: true` | 对象内新增 IP/掩码条目 | `ip_mask` |
| `add_detail_exclude_ip: true` | 对象内新增排除 IP/掩码条目 | `ip_mask` |
| `add_detail_hostip: true` | 对象内新增主机 IP（仅 H3C）| `hostipv4addr` |
| `add_detail_hybrid: true` | 对象内混合模式新增（仅 Hillstone）| `hybrid` |
| `add_detail_range: true` | 对象内新增 IP 范围条目 | `range_start` + `range_end` |
| `add_detail_exclude_range: true` | 对象内新增排除 IP 范围条目 | `range_start` + `range_end` |
| `del_detail_ip: true` | 对象内删除 IP/掩码条目 | `ip_mask` |
| `del_detail_exclude_ip: true` | 对象内删除排除 IP 条目 | `ip_mask` |
| `del_detail_hostip: true` | 对象内删除主机 IP（仅 H3C）| `hostipv4addr` |
| `del_detail_range: true` | 对象内删除 IP 范围条目 | `range_start` + `range_end` |
| `del_detail_exclude_range: true` | 对象内删除排除范围条目 | `range_start` + `range_end` |

**数据字段说明**

| 字段 | 类型 | 格式 | 说明 |
|------|------|------|------|
| `ip_mask` | array[string] | `["x.x.x.x/xx"]` | 1~1000 条，元素唯一 |
| `range_start` | string | `x.x.x.x` | IP 范围起始 |
| `range_end` | string | `x.x.x.x` | IP 范围结束 |
| `hostipv4addr` | array[string] | `["x.x.x.x"]` | 主机 IP 列表（仅 H3C）|
| `hybrid` | array[string] | `["x.x.x.x/xx"]` 或 `["x.x.x.x-x.x.x.x"]` | 混合模式（仅 Hillstone）|
| `description` | string | — | 对象描述（可选）|

**另外支持（非 Schema 验证分支）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `update_device: true` | boolean | 触发设备数据同步（目前仅 Hillstone）|

**请求示例（新建地址对象并添加 IP）**

```json
{
  "vendor": "H3C",
  "hostip": "192.168.10.1",
  "hostid": 101,
  "name": "addr_web_servers",
  "add_detail_ip": true,
  "ip_mask": ["10.0.1.0/24", "10.0.2.100/32"]
}
```

**请求示例（删除对象内主机 IP，仅 H3C）**

```json
{
  "vendor": "H3C",
  "hostip": "192.168.10.1",
  "hostid": 101,
  "name": "addr_web_servers",
  "del_detail_hostip": true,
  "hostipv4addr": ["10.0.2.100"]
}
```

**成功响应**

```json
{ "code": 200, "message": "OK", "data": "task-id-xxxx" }
```

---

## 服务对象

**路径**：`/service_set/`
**认证**：豁免（无需认证）

### GET — 查询设备服务对象列表

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |

**成功响应（Hillstone 示例）**

```json
{
  "code": 200,
  "results": [
    {
      "name": "svc_http",
      "hostip": "192.168.1.1",
      "items": [{ "protocol": "TCP", "dst-port-min": "80", "dst-port-max": "80" }]
    }
  ],
  "count": 1
}
```

---

### POST — 服务对象操作

新建、删除或编辑防火墙服务对象及其条目。

**公共字段（必填）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |
| `hostid` | integer | 是 | 设备资产 ID |
| `name` | string | 是 | 服务对象名称（3~30 位，字母/数字/下划线，不以下划线开头结尾）|

**操作类型（必须且只能传一个）**

| 字段 | 说明 | 额外必填字段 |
|------|------|-------------|
| `add_object: true` | 新建服务对象（含条目）| `objects` |
| `del_object: true` | 删除整个服务对象 | — |
| `edit_object: true` | 编辑服务对象条目 | `objects` |

**`objects` 字段结构**

`objects` 为数组（1~40 条，元素唯一），每个元素表示一条协议条目：

| 字段 | 类型 | 说明 |
|------|------|------|
| `add_detail: true` | boolean | 新增该条目 |
| `del_detail: true` | boolean | 删除该条目 |
| `protocol` | string | 协议，枚举：`TCP` / `UDP` / `ICMP` |
| `start_dst_port` | integer | 目的端口起始（0~65535）|
| `end_dst_port` | integer | 目的端口结束（0~65535）|
| `start_src_port` | integer | 源端口起始（0~65535，默认 0）|
| `end_src_port` | integer | 源端口结束（0~65535，默认 65535）|
| `ID` | string | H3C 条目 ID（仅 H3C 删除时使用）|

**请求示例（新建服务对象）**

```json
{
  "vendor": "Hillstone",
  "hostip": "192.168.1.1",
  "hostid": 5,
  "name": "svc_custom_https",
  "description": "custom https",
  "add_object": true,
  "objects": [
    {
      "add_detail": true,
      "protocol": "TCP",
      "start_dst_port": 8443,
      "end_dst_port": 8443
    }
  ]
}
```

**请求示例（删除服务对象）**

```json
{
  "vendor": "H3C",
  "hostip": "192.168.10.1",
  "hostid": 101,
  "name": "svc_old",
  "del_object": true
}
```

**成功响应**

```json
{ "code": 200, "message": "OK", "data": "task-id-xxxx" }
```

---

## DNAT 公网发布

**路径**：`/dnat/`
**认证**：豁免（无需认证）

### GET — 查询设备 DNAT 规则列表

场景一：按厂商实时查询设备 DNAT 规则。

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [
    { "name": "dnat_web", "hostip": "192.168.1.1", "from": "any", "to": "203.x.x.1", "trans_to": "10.0.0.10" }
  ],
  "count": 1
}
```

---

### GET — 查询全局 DNAT 标准化表

场景二：基于标准化后的 `DNAT` Mongo 集合做精确/范围混合查询。

说明：

- 该查询直接使用后端统一数据表 `dnat_mongo`
- `hostip` 为精确匹配防火墙管理 IP
- `global_ip` / `local_ip` 会先转换为十进制，再判断是否落在 `start_int ~ end_int` 区间
- `global_port` / `local_port` 会判断是否落在 `start ~ end` 区间
- 如果同时传了 `vendor` 和 `hostip`，但又带了任一范围筛选字段，后端优先走本标准化查询分支

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `hostip` | string | 是 | 防火墙管理 IP，精确匹配 |
| `global_ip` | string | 否 | 公网 IP，按 `global_ip.start_int ~ end_int` 范围匹配 |
| `global_port` | integer | 否 | 公网端口，按 `global_port.start ~ end` 范围匹配 |
| `local_ip` | string | 否 | 内网 IP，按 `local_ip.start_int ~ end_int` 范围匹配 |
| `local_port` | integer | 否 | 内网端口，按 `local_port.start ~ end` 范围匹配 |
| `vendor` | string | 否 | 可传，但该分支不依赖 `vendor` 做主查询条件 |

**请求示例**

```http
GET /api/dcs_control/dnat/?hostip=172.16.75.1&global_ip=36.7.172.66&global_port=12183&local_ip=172.16.81.43&local_port=12181
```

**成功响应**

```json
{
  "code": 200,
  "msg": "success",
  "count": 1,
  "results": [
    {
      "id": "683_172.16.75.1",
      "rule_id": "683",
      "hostip": "172.16.75.1",
      "global_ip": [
        {
          "start": "36.7.172.66",
          "end": "36.7.172.66",
          "start_int": 604482626,
          "end_int": 604482626,
          "result": "36.7.172.66"
        }
      ],
      "global_port": [
        {
          "start": 12183,
          "end": 12183,
          "protocol": "tcp",
          "result": "12183"
        }
      ],
      "local_ip": [
        {
          "start": "172.16.81.43",
          "end": "172.16.81.43",
          "start_int": 2886750507,
          "end_int": 2886750507,
          "result": "172.16.81.43"
        }
      ],
      "local_port": [
        {
          "start": 12181,
          "end": 12181,
          "protocol": "tcp",
          "result": "12181"
        }
      ]
    }
  ]
}
```

**失败响应**

```json
{
  "code": 400,
  "msg": "参数错误: failed to detect a valid IP address from 'bad-ip'",
  "count": 0,
  "results": []
}
```

---

### POST — DNAT 规则操作

新建、删除、编辑或排序 DNAT 规则。
**备注**：传入 `update_device: true` + `hostip` 时触发设备数据同步（仅 Hillstone）。

**公共字段（DNAT 操作必填）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |
| `hostid` | integer | 是 | 设备资产 ID |
| `name` | string | 是 | 规则名称（字母开头，字母/数字/下划线）|

**操作类型（必须且只能传一个）**

| 字段 | 说明 | 额外必填字段 |
|------|------|-------------|
| `add_object: true` | 新建 DNAT 规则 | `service`, `from`, `to`, `trans_to` |
| `del_object: true` | 删除 DNAT 规则 | `id` |
| `edit_object: true` | 编辑 DNAT 规则 | `id`, `service`, `from`, `to`, `trans_to` |
| `sort_object: true` | 调整规则顺序 | `id`, `insert` |

**字段详细说明**

**`id`**（string）：规则 ID，仅数字，用于删除/编辑/排序。

**`insert`**（string）：排序指令，格式 `before <n>` / `after <n>` / `top`。

**`service`**（object）：服务对象，三选一：

```json
// 方式一：引用已有服务对象名称
{ "name": "svc_http" }

// 方式二：自定义单协议
{ "protocol": "TCP", "start_port": 80, "end_port": 80 }

// 方式三：多协议
{
  "multi": [
    { "protocol": "TCP", "start_port": 80, "end_port": 80 },
    { "protocol": "TCP", "start_port": 443, "end_port": 443 }
  ]
}
```

**`from`**（object）：源地址，三选一：

```json
{ "address_book": "addr_internet" }   // 地址对象引用
{ "ip": "203.x.x.0" }                 // 指定 IP
{ "any": true }                        // 任意
```

**`to`**（object）：公网目的地址，二选一：

```json
{ "object": "addr_public_ip" }   // 地址对象引用
{ "ip": "203.x.x.1" }            // 指定 IP
```

**`trans_to`**（object）：内网转换目标，四选一：

```json
{ "ip": "10.0.0.10" }                            // 指定内网 IP
{ "address_book": "addr_web_servers" }            // 地址对象引用
{ "slb_server_pool": "pool_web" }                 // 已有 SLB 池
{
  "custom_slb": [                                 // 自定义 SLB 池（1~10 条）
    {
      "ip_mask": ["10.0.0.10/32"],
      "protocol": "TCP",
      "port": 8080,
      "weight": 1,
      "max_connection": 65535
    }
  ]
}
```

**可选字段**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `port` | integer | — | 目的端口（0~65535）|
| `track_tcp` | integer | — | TCP 健康检查端口 |
| `track_ping` | boolean | `false` | 是否启用 ICMP 健康检查 |
| `log` | boolean | `false` | 是否记录日志 |
| `load_balance` | boolean | `false` | 是否开启负载均衡 |
| `description` | string | — | 规则描述 |

**请求示例（新建 DNAT 规则）**

```json
{
  "vendor": "Hillstone",
  "hostip": "192.168.1.1",
  "hostid": 5,
  "name": "dnat_web_80",
  "add_object": true,
  "service": { "protocol": "TCP", "start_port": 80, "end_port": 80 },
  "from": { "any": true },
  "to": { "ip": "203.0.113.10" },
  "trans_to": { "ip": "10.10.0.100" },
  "port": 80,
  "log": true
}
```

**请求示例（删除规则）**

```json
{
  "vendor": "H3C",
  "hostip": "192.168.10.1",
  "hostid": 101,
  "name": "dnat_old",
  "id": "42",
  "del_object": true
}
```

**请求示例（规则排序）**

```json
{
  "vendor": "Hillstone",
  "hostip": "192.168.1.1",
  "hostid": 5,
  "name": "dnat_web_80",
  "id": "10",
  "insert": "before 5",
  "sort_object": true
}
```

**成功响应**

```json
{ "code": 200, "message": "OK", "data": "task-id-xxxx" }
```

---

## 安全策略

**路径**：`/sec_policy/`
**认证**：豁免（无需认证）

### GET — 查询安全策略（多场景）

根据传入的查询参数不同，支持以下四类查询场景：

---

#### 场景一：分页查询（含条件过滤）

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | integer | 是 | 页码，从 1 开始 |
| `page_size` | integer | 是 | 每页条数 |
| `query` | string | 是 | JSON 字符串，查询条件（见下方） |

**`query` JSON 结构**（所有字段可选，空值自动忽略）

```json
{
  "hostip": "192.168.1.1",
  "name": "policy_web",
  "id": "5",
  "src_ip": "10.0.0.1",
  "dst_ip": "203.0.113.10"
}
```

> `src_ip` / `dst_ip` 支持精确 IP 查询，后端自动转换为范围匹配。

**成功响应**

```json
{
  "code": 200,
  "msg": "success",
  "count": 128,
  "data": [
    {
      "hostip": "192.168.1.1",
      "id": "5",
      "name": "policy_web",
      "action": "permit",
      "from": { "zone": "untrust" },
      "to": { "zone": "trust" }
    }
  ]
}
```

---

#### 场景二：查询设备全量安全策略

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `get_firewall_sec_policy` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [ { "hostip": "...", "id": "1", "name": "...", "action": "permit" } ],
  "count": 56
}
```

---

#### 场景三：查询策略 ID 与名称列表

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `get_firewall_sec_policy_id` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [
    { "id": "1", "name": "policy_web" },
    { "id": "2", "name": "policy_db" }
  ],
  "count": 2
}
```

---

#### 场景四：查询设备安全域列表

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `get_sec_zone` | string | 是 | 设备管理 IP |

**成功响应（Hillstone）**

```json
{
  "code": 200,
  "data": [
    { "name": "trust", "type": "L3", "hostip": "192.168.1.1" },
    { "name": "untrust", "type": "L3", "hostip": "192.168.1.1" }
  ],
  "count": 2,
  "msg": "成功"
}
```

---

#### 场景五：查询设备地址对象（安全策略上下文）

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `get_address_obj` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [{ "name": "addr_web" }],
  "count": 1
}
```

---

#### 场景六：查询设备服务对象（安全策略上下文）

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `get_service_obj` | string | 是 | 设备管理 IP |

**成功响应（Hillstone，按分组返回）**

```json
{
  "code": 200,
  "data": [
    {
      "label": "自定义服务",
      "options": [
        { "label": "svc_http", "value": "svc_http", "protocol": "TCP:80-80" }
      ]
    },
    {
      "label": "预定义服务",
      "options": [
        { "label": "Any", "value": "Any", "protocol": "" }
      ]
    }
  ],
  "count": 2,
  "msg": "成功"
}
```

---

#### 场景七：查询设备安全策略（vendor+hostip）

**请求参数（Query String）**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |

**成功响应**

```json
{
  "code": 200,
  "results": [{ "id": "1", "name": "policy_web", "action": "permit" }],
  "count": 1
}
```

---

### POST — 查询策略引用的地址/服务详情

用于安全策略详情页面，解析策略中引用的地址对象和服务对象的实际 IP 和端口信息（含寻觅平台数据关联）。

**请求体（application/json）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `vendor` | string | 是 | 厂商标识 |
| `hostip` | string | 是 | 设备管理 IP |
| `name` | string | 是 | 策略名称 |
| `id` | string | 是 | 策略 ID |
| `src_addr` | array | 是 | 源地址列表，每项 `{"object": "addr_name"}` 或 `{"ip": "x.x.x.x"}` |
| `dst_addr` | array | 是 | 目的地址列表，格式同 `src_addr` |
| `service` | array | 是 | 服务列表，每项 `{"object": "svc_name"}` |

**请求示例**

```json
{
  "vendor": "H3C",
  "hostip": "192.168.10.1",
  "name": "policy_web",
  "id": "5",
  "src_addr": [{ "object": "addr_internet" }],
  "dst_addr": [{ "object": "addr_web_servers" }],
  "service": [{ "object": "svc_http" }]
}
```

**成功响应**

```json
{
  "code": 200,
  "msg": "ok",
  "data": {
    "src_addr": [
      { "name": "addr_internet", "ip": "0.0.0.0/0", "xunmi": null }
    ],
    "dst_addr": [
      { "name": "addr_web_servers", "ip": "10.0.0.10/32", "xunmi": { "hostname": "web-server-01" } }
    ],
    "service": [
      { "name": "svc_http", "protocol": "tcp", "port": "80", "type": "default" }
    ]
  }
}
```

> `type` 字段标识风险等级：`default`（正常）/ `warning`（包含高风险端口如 22/23/3306/3389 等）。

---

## 错误码说明

| code | 含义 |
|------|------|
| `200` | 操作成功或任务已提交 |
| `400` | 请求参数不合法 / Schema 校验失败 / 未找到匹配数据 / 重复任务 |

**Schema 校验失败响应示例**

```json
{
  "code": 400,
  "message": "缺少必填字段 ip_mask",
  "data": null
}
```

---

## 支持的厂商功能矩阵

| 功能 | Hillstone | H3C | Huawei |
|------|:---------:|:---:|:------:|
| 查询地址对象 | ✓（MongoDB）| ✓（NETCONF）| ✓（NETCONF）|
| 操作地址对象 | ✓ | ✓ | ✓ |
| 查询服务对象 | ✓（MongoDB）| ✓（NETCONF）| ✓（NETCONF）|
| 操作服务对象 | ✓ | ✓ | ✓ |
| 查询 DNAT | ✓（MongoDB）| ✓（NETCONF）| ✓（NETCONF）|
| 操作 DNAT | ✓ | ✓ | ✓ |
| 查询安全策略 | ✓（MongoDB）| ✓（NETCONF）| ✓（NETCONF）|
| 操作安全策略 | ✓ | ✗ | ✗ |
| 一键封堵 | ✓ | ✓ | ✓ |
| 查询安全域 | ✓ | ✓ | ✓ |


## 启动命令
celery -A netaxe worker -c 2 -Q dev -l info -n dev
