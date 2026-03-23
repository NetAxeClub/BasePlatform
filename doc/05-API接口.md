# API接口文档

## 1. 接口概述

NetAxe平台提供RESTful API接口，基于Django REST Framework实现。所有API接口统一使用 `/base_platform/` 前缀。

### 1.1 接口规范
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8
- **认证方式**: JWT Token（可选，部分接口需要认证）

### 1.2 响应格式

#### 成功响应
```json
{
  "code": 200,
  "data": {...},
  "msg": "成功"
}
```

#### 错误响应
```json
{
  "code": 400,
  "data": {},
  "msg": "错误信息"
}
```

### 1.3 分页格式
```json
{
  "count": 100,
  "next": "http://example.com/api/?page=2",
  "previous": null,
  "results": [...]
}
```

## 2. 认证接口

### 2.1 用户登录
- **URL**: `/base_platform/login/`
- **方法**: POST
- **请求参数**:
```json
{
  "username": "admin",
  "password": "123456"
}
```
- **响应**:
```json
{
  "code": 200,
  "data": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": {
      "id": 1,
      "username": "admin",
      "nick_name": "管理员"
    }
  },
  "msg": "登录成功"
}
```

### 2.2 刷新Token
- **URL**: `/base_platform/refresh/`
- **方法**: POST
- **请求参数**:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### 2.3 用户登出
- **URL**: `/base_platform/logout/`
- **方法**: POST
- **需要认证**: 是

## 3. 资产管理接口

### 3.1 IDC管理

#### 获取IDC列表
- **URL**: `/base_platform/asset/cmdb_idc/`
- **方法**: GET
- **查询参数**: 
  - `page`: 页码
  - `page_size`: 每页数量
  - `search`: 搜索关键词

#### 创建IDC
- **URL**: `/base_platform/asset/cmdb_idc/`
- **方法**: POST
- **请求参数**:
```json
{
  "name": "北京机房",
  "address": "北京市朝阳区",
  "tel": "010-12345678"
}
```

#### 更新IDC
- **URL**: `/base_platform/asset/cmdb_idc/{id}/`
- **方法**: PUT/PATCH

#### 删除IDC
- **URL**: `/base_platform/asset/cmdb_idc/{id}/`
- **方法**: DELETE

### 3.2 网络设备管理

#### 获取设备列表
- **URL**: `/base_platform/asset/asset_networkdevice/`
- **方法**: GET
- **查询参数**:
  - `page`: 页码
  - `page_size`: 每页数量
  - `search`: 搜索关键词
  - `vendor`: 厂商筛选
  - `status`: 状态筛选

#### 创建设备
- **URL**: `/base_platform/asset/asset_networkdevice/`
- **方法**: POST
- **请求参数**:
```json
{
  "serial_num": "210235A1HMC123456",
  "manage_ip": "192.168.1.1",
  "name": "核心交换机-01",
  "vendor": 1,
  "idc": 1,
  "category": 1,
  "model": 1,
  "soft_version": "7.1.075",
  "role": 1
}
```

#### 更新设备
- **URL**: `/base_platform/asset/asset_networkdevice/{id}/`
- **方法**: PUT/PATCH

#### 删除设备
- **URL**: `/base_platform/asset/asset_networkdevice/{id}/`
- **方法**: DELETE

### 3.3 账户管理

#### 获取账户列表
- **URL**: `/base_platform/asset/cmdb_account/`
- **方法**: GET

#### 创建账户
- **URL**: `/base_platform/asset/cmdb_account/`
- **方法**: POST
- **请求参数**:
```json
{
  "name": "admin账户",
  "username": "admin",
  "password": "password123",
  "protocol": "ssh",
  "port": 22,
  "role": "3"
}
```

### 3.4 服务器管理

#### 获取服务器列表
- **URL**: `/base_platform/asset/asset_server/`
- **方法**: GET

#### 创建服务器
- **URL**: `/base_platform/asset/asset_server/`
- **方法**: POST

## 4. 自动化运维接口

### 4.1 采集方案管理

#### 获取采集方案列表
- **URL**: `/base_platform/automation/api/collection_plan/`
- **方法**: GET

#### 创建采集方案
- **URL**: `/base_platform/automation/api/collection_plan/`
- **方法**: POST
- **请求参数**:
```json
{
  "vendor": "H3C",
  "category": "交换机",
  "name": "H3C交换机基础信息采集",
  "commands": "[\"display arp\", \"display mac-address\"]",
  "netconf_method": "[]",
  "memo": "采集ARP和MAC地址表"
}
```

### 4.2 采集规则管理

#### 获取采集规则列表
- **URL**: `/base_platform/automation/api/collection_rule/`
- **方法**: GET

#### 创建采集规则
- **URL**: `/base_platform/automation/api/collection_rule/`
- **方法**: POST

### 4.3 自动化流程管理

#### 获取流程列表
- **URL**: `/base_platform/automation/api/auto_work_flow/`
- **方法**: GET

#### 创建流程
- **URL**: `/base_platform/automation/api/auto_work_flow/`
- **方法**: POST
- **请求参数**:
```json
{
  "device": "192.168.1.1",
  "task": "DNAT",
  "method": "增量",
  "class_method": "DnatProc.add_dnat",
  "kwargs": "{\"source_ip\": \"1.1.1.1\", \"target_ip\": \"2.2.2.2\"}"
}
```

#### 执行流程
- **URL**: `/base_platform/automation/api/auto_work_flow/{id}/execute/`
- **方法**: POST

### 4.4 设备采集

#### 手动触发采集
- **URL**: `/base_platform/automation/api/collection_plan/{id}/collect/`
- **方法**: POST
- **请求参数**:
```json
{
  "device_ids": [1, 2, 3]
}
```

## 5. 配置管理中心接口

### 5.1 配置备份管理

#### 获取备份列表
- **URL**: `/base_platform/config_center/config_backup/`
- **方法**: GET
- **查询参数**:
  - `host`: 设备IP
  - `config_type`: 配置类型（current/startup）
  - `start_date`: 开始日期
  - `end_date`: 结束日期

#### 手动备份配置
- **URL**: `/base_platform/config_center/config_backup/backup/`
- **方法**: POST
- **请求参数**:
```json
{
  "device_ip": "192.168.1.1",
  "config_type": "current"
}
```

#### 获取配置内容
- **URL**: `/base_platform/config_center/config_backup/{id}/content/`
- **方法**: GET

### 5.2 配置模板管理

#### 获取模板列表
- **URL**: `/base_platform/config_center/config_template/`
- **方法**: GET

#### 创建模板
- **URL**: `/base_platform/config_center/config_template/`
- **方法**: POST
- **请求参数**:
```json
{
  "vendor": "H3C",
  "name": "VLAN配置模板",
  "config_yaml": "...",
  "config_jinja2": "{% for vlan in vlans %}vlan {{ vlan }}{% endfor %}",
  "config_text": "vlan 10"
}
```

#### 渲染模板
- **URL**: `/base_platform/config_center/config_template/{id}/render/`
- **方法**: POST
- **请求参数**:
```json
{
  "variables": {
    "vlans": [10, 20, 30]
  }
}
```

### 5.3 配置差异比较

#### 获取配置差异
- **URL**: `/base_platform/config_center/git_config/`
- **方法**: GET
- **查询参数**:
  - `get_hostip`: 获取设备IP列表
  - `get_hostip_file`: 获取设备配置文件列表
  - `get_tree`: 获取配置目录树
  - `get_file`: 获取配置文件内容
  - `get_diff`: 获取配置差异

### 5.4 配置合规性检查

#### 获取合规规则列表
- **URL**: `/base_platform/config_center/config_compliance_rule/`
- **方法**: GET

#### 创建合规规则
- **URL**: `/base_platform/config_center/config_compliance_rule/`
- **方法**: POST
- **请求参数**:
```json
{
  "vendor": "H3C",
  "name": "密码复杂度检查",
  "regex": "password.*encryption",
  "description": "检查是否启用密码加密"
}
```

#### 执行合规检查
- **URL**: `/base_platform/config_center/config_compliance/check/`
- **方法**: POST
- **请求参数**:
```json
{
  "device_ip": "192.168.1.1",
  "rule_ids": [1, 2, 3]
}
```

## 6. 设备API管理接口（新版）

> 以下接口为新架构主入口，面向 `device_api` / `workflow_center` 能力中心。
> `automation` 仅作为 legacy 兼容入口，不再作为新功能的文档主入口。

### 6.0 平台画像与规则管理

#### 获取平台画像列表
- **URL**: `/base_platform/device_api/platform-profiles/`
- **方法**: GET

#### 获取采集规则列表
- **URL**: `/base_platform/device_api/collection-rules/`
- **方法**: GET

#### 获取采集规则匹配项列表
- **URL**: `/base_platform/device_api/collection-match-rules/`
- **方法**: GET

#### 获取规则工具元数据
- **URL**: `/base_platform/device_api/collection-rule-tools/`
- **方法**: GET
- **查询参数**:
  - `get_cmdb_field=1`
  - `get_pulgin_list=1`

### 6.1 父采集方案管理

#### 获取方案列表
- **URL**: `/base_platform/device_api/collection-plans/`
- **方法**: GET

#### 创建方案
- **URL**: `/base_platform/device_api/collection-plans/`
- **方法**: POST
- **请求参数**:
```json
{
  "name": "default-h3c-modern-switch",
  "vendor": "H3C",
  "device_type": "switch",
  "description": "H3C 现代交换机默认模板方案",
  "enabled_collection_types": ["arp", "mac", "lldp", "interface_brief"],
  "collection_method": "both",
  "profile_code": "H3C-modern-netconf",
  "plan_kind": "template",
  "version": 1,
  "is_default": true,
  "is_active": true
}
```

- `enabled_collection_types` 为空数组或不传时，表示使用后端默认的全部采集类型。
- `collection_method` 支持 `netmiko`、`netconf`、`both`，保存父方案时会自动同步到对应子方案的 `netmiko_enabled` / `netconf_enabled`。

### 6.2 子采集方案管理

#### 获取子方案列表
- **URL**: `/base_platform/device_api/sub-collection-plan/`
- **方法**: GET

#### 创建子方案
- **URL**: `/base_platform/device_api/sub-collection-plan/`
- **方法**: POST
- **请求参数**:
```json
{
  "summary_plan_id": 1,
  "name": "default-h3c-modern-switch-arp",
  "collection_type": "arp",
  "description": "profile=H3C-modern-netconf; supported=True; preferred=netconf,netmiko",
  "netmiko_enabled": true,
  "netmiko_method": "display arp",
  "textfsm_template": "hp_comware_display_arp.textfsm",
  "netconf_enabled": false
}
```

#### 获取方案级字段映射
- **URL**: `/base_platform/device_api/collection-plans/{id}/field-mappings/`
- **方法**: GET

#### 更新方案级字段映射
- **URL**: `/base_platform/device_api/collection-plans/{id}/field-mappings/`
- **方法**: PATCH
- **请求参数**:
```json
{
  "arp": {
    "netmiko_path": "data.items[*]",
    "netmiko_field_mappings": {
      "ipaddress": "ip",
      "macaddress": "mac"
    },
    "netconf_path": "top.ARP.ArpTable.ArpEntry",
    "netconf_field_mappings": {
      "ipaddress": "Ipv4Address"
    }
  }
}
```

#### 方案级一键验证
- **URL**: `/base_platform/device_api/collection-plans/{id}/validate/`
- **方法**: POST
- **请求参数**:
```json
{
  "device_ip": "10.0.0.1",
  "use_local": true
}
```

- 南向驱动方式需额外传 `south_driver`；本机直连方式可传 `use_local=true`。
- 返回结果按 `collection_type` 分组，单个类型下保留对应子方案的执行状态与协议返回结果。

### 6.3 采集结果管理

#### 获取采集结果列表
- **URL**: `/base_platform/device_api/collection-results/`
- **方法**: GET
- **查询参数**:
  - `device_ip`: 设备IP
  - `plan_id`: 方案ID
  - `start_date`: 开始日期
  - `end_date`: 结束日期

#### 获取设备最新标准化结果
- **URL**: `/base_platform/device_api/collection-results/latest/`
- **方法**: GET
- **查询参数**:
  - `serial_num`: 设备序列号
  - `manage_ip`: 设备管理IP
  - `collection_type`: 采集类型，可选

### 6.4 方案设备关联

#### 关联方案到设备
- **URL**: `/base_platform/device_api/plans-to-device/`
- **方法**: POST
- **请求参数**:
```json
{
  "plan": 1,
  "device_serial_num": "SER-001",
  "manage_ip": "10.0.0.1",
  "profile_code": "Huawei-CE",
  "binding_source": "manual",
  "use_local": true,
  "execute_node": ""
}
```

#### 自动绑定设备到默认方案
- **URL**: `/base_platform/device_api/plans-to-device/auto_bind/`
- **方法**: POST
- **请求参数**:
```json
{
  "manage_ip": "10.0.0.1"
}
```

#### 获取设备事实
- **URL**: `/base_platform/device_api/devices/{serial_num}/facts/`
- **方法**: GET

#### 获取设备能力画像与绑定关系
- **URL**: `/base_platform/device_api/devices/{serial_num}/capabilities/`
- **方法**: GET

### 6.5 工作流中心接口

#### 获取工作流执行列表
- **URL**: `/base_platform/workflow_center/executions/`
- **方法**: GET

#### 写入巡检结果
- **URL**: `/base_platform/workflow_center/executions/write_inspection_result/`
- **方法**: POST

#### 获取工作流库存列表
- **URL**: `/base_platform/workflow_center/inventories/`
- **方法**: GET

#### 创建工作流库存
- **URL**: `/base_platform/workflow_center/inventories/`
- **方法**: POST
- **请求参数**:
```json
{
  "name": "core-switch-inventory",
  "variables": "{\"site\": \"dc1\"}",
  "description": "核心交换机库存",
  "task": "巡检",
  "hosts": [
    {"id": 1},
    {"id": 2}
  ]
}
```

#### 获取工作流主机变量列表
- **URL**: `/base_platform/workflow_center/host-vars/`
- **方法**: GET

#### 创建工作流主机变量
- **URL**: `/base_platform/workflow_center/host-vars/`
- **方法**: POST
- **请求参数**:
```json
{
  "name": "border-fw-01",
  "host": "10.0.0.10",
  "variables": "{\"region\": \"cn-east\"}",
  "object_name": "firewall",
  "description": "边界防火墙",
  "task": "安全策略"
}
```

#### 版本化别名
- **URL 前缀**:
  - `/base_platform/device_api/v1/`
  - `/base_platform/workflow_center/v1/`
- **说明**:
  - 与当前主接口行为一致，用于外部系统稳定接入。

## 6.6 网络分析中心接口

#### 获取分析运行记录
- **URL**: `/base_platform/network_analysis/analysis-runs/`
- **方法**: GET

#### 统一重建分析结果
- **URL**: `/base_platform/network_analysis/analysis-runs/rebuild_all/`
- **方法**: POST
- **请求参数**:
```json
{
  "manage_ip": "10.0.0.1",
  "ip_address": "10.1.1.1",
  "triggered_by": "api"
}
```

#### 获取接口利用率快照
- **URL**: `/base_platform/network_analysis/interface-utilization/`
- **方法**: GET
- **查询参数**:
  - `manage_ip`
  - `device_serial_num`
  - `component_scope`

#### 重建接口利用率快照
- **URL**: `/base_platform/network_analysis/interface-utilization/rebuild/`
- **方法**: POST
- **请求参数**:
```json
{
  "manage_ip": "10.0.0.1"
}
```

#### 获取接口利用率总览
- **URL**: `/base_platform/network_analysis/interface-utilization/overview/`
- **方法**: GET

#### 获取接口利用率质量指标
- **URL**: `/base_platform/network_analysis/interface-utilization/quality/`
- **方法**: GET

#### 获取地址定位快照
- **URL**: `/base_platform/network_analysis/address-traces/`
- **方法**: GET
- **查询参数**:
  - `ip_address`
  - `manage_ip`
  - `trace_status`

#### 重建地址定位快照
- **URL**: `/base_platform/network_analysis/address-traces/rebuild/`
- **方法**: POST
- **请求参数**:
```json
{
  "ip_address": "10.1.1.1"
}
```

#### 获取地址定位总览
- **URL**: `/base_platform/network_analysis/address-traces/overview/`
- **方法**: GET

#### 获取地址定位质量指标
- **URL**: `/base_platform/network_analysis/address-traces/quality/`
- **方法**: GET

## 7. 系统管理接口

## 6.7 兼容查询接口

### 6.7.1 接口利用率兼容入口

#### 获取接口利用率列表
- **推荐 URL**: `/base_platform/network_analysis/interfaceused/`
- **兼容 URL**: `/base_platform/int_utilization/interfaceused/`
- **方法**: GET
- **说明**:
  - 推荐改用 `network_analysis` 命名空间，旧 `int_utilization` 入口保留为兼容路径
  - 两个入口当前都读取 `network_analysis.InterfaceUtilizationSnapshot`
  - 返回结构尽量保持 legacy 兼容，但真实数据来源为新分析快照

#### 获取设备接口视图
- **URL**: `/base_platform/int_utilization/interface/`
- **方法**: GET
- **说明**:
  - 当前底层已切换为 `plan_interface_brief` / `plan_ip_interface`
  - 不再依赖 legacy `layer2interface` / `layer3interface` 作为主来源

### 7.1 菜单管理

#### 获取菜单列表
- **URL**: `/base_platform/system/menu/`
- **方法**: GET

### 7.2 角色管理

#### 获取角色列表
- **URL**: `/base_platform/system/role/`
- **方法**: GET

#### 创建角色
- **URL**: `/base_platform/system/role/`
- **方法**: POST

### 7.3 部门管理

#### 获取部门树
- **URL**: `/base_platform/system/dept_lazy_tree/`
- **方法**: GET

### 7.4 操作日志

#### 获取操作日志
- **URL**: `/base_platform/system/operation_log/`
- **方法**: GET
- **查询参数**:
  - `user`: 用户ID
  - `start_date`: 开始日期
  - `end_date`: 结束日期

### 7.5 登录日志

#### 获取登录日志
- **URL**: `/base_platform/system/login_log/`
- **方法**: GET

## 8. 用户管理接口

### 8.1 用户列表

#### 获取用户列表
- **URL**: `/base_platform/users/`
- **方法**: GET

#### 创建用户
- **URL**: `/base_platform/users/`
- **方法**: POST
- **请求参数**:
```json
{
  "username": "testuser",
  "password": "password123",
  "nick_name": "测试用户",
  "email": "test@example.com"
}
```

### 8.2 用户详情

#### 获取用户详情
- **URL**: `/base_platform/users/{id}/`
- **方法**: GET

#### 更新用户
- **URL**: `/base_platform/users/{id}/`
- **方法**: PUT/PATCH

#### 删除用户
- **URL**: `/base_platform/users/{id}/`
- **方法**: DELETE

## 9. WebSocket接口

### 9.1 WebSSH

#### 连接WebSSH
- **URL**: `ws://host/base_platform/ws/ssh/{device_id}/`
- **协议**: WebSocket
- **认证**: 通过URL参数传递Token

### 9.2 服务器SSH

#### 连接服务器SSH
- **URL**: `ws://host/base_platform/ws/server_ssh/{server_id}/`
- **协议**: WebSocket

## 10. 错误码说明

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 11. 接口调用示例

### 11.1 Python示例

```python
import requests

# 登录获取Token
response = requests.post('http://localhost:8000/base_platform/login/', json={
    'username': 'admin',
    'password': '123456'
})
token = response.json()['data']['token']

# 使用Token调用接口
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8000/base_platform/asset/asset_networkdevice/', headers=headers)
devices = response.json()['data']
```

### 11.2 curl示例

```bash
# 登录
curl -X POST http://localhost:8000/base_platform/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'

# 获取设备列表
curl -X GET http://localhost:8000/base_platform/asset/asset_networkdevice/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```
