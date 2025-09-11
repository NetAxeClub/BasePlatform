# Device API 应用

## 📋 目录
- [概述](#概述)
- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [API接口文档](#api接口文档)
- [使用示例](#使用示例)
- [数据模型](#数据模型)
- [采集流程](#采集流程)
- [日志管理](#日志管理)
- [部署指南](#部署指南)
- [故障排除](#故障排除)

## 📖 概述

Device API 是一个基于Django的网络设备数据采集和管理系统，提供灵活的设备信息采集、数据处理和存储功能。系统支持多种采集协议（NETCONF、Netmiko CLI）和智能数据处理，适用于大规模网络设备管理场景。

### 🎯 主要功能
- **多协议采集**: 支持NETCONF和Netmiko两种采集方式
- **智能数据处理**: 支持自定义Python代码处理采集数据
- **灵活配置**: 支持字段映射、TextFSM解析等高级功能
- **批量操作**: 支持批量执行多个采集方案
- **详细日志**: 完整的执行日志记录和查询功能

## ✨ 核心特性

### 🔧 多协议采集支持
- **NETCONF协议**: 基于XML的配置和状态查询
- **Netmiko CLI**: 基于SSH的命令行接口采集
- **TextFSM解析**: 自动解析CLI输出为结构化数据
- **双重采集**: 支持同时执行NETCONF和Netmiko采集

### 🧠 智能数据处理
- **动态数据处理**: 支持自定义Python代码处理采集数据
- **字段映射**: 灵活的JSONPath风格数据提取
- **类型转换**: 自动数据类型转换和格式化
- **错误处理**: 完善的异常处理和状态管理

### 📊 数据管理
- **MongoDB存储**: 高性能文档数据库存储
- **分层架构**: 汇总方案 → 采集方案 → 采集结果
- **状态跟踪**: 完整的采集和处理状态管理
- **数据版本**: 支持数据历史记录和回滚

## 🏗️ 系统架构

### 数据模型层次

```
DeviceSummaryPlans (采集汇总方案)
├── vendor: 设备厂商 (H3C, Huawei, Cisco, Hillstone, Ruijie, Mellanox, Centec)
├── device_type: 设备类型 (switch, router, firewall, load_balancer, server)
└── collect_plans: 关联的采集方案列表
    └── DeviceCollectionPlan (设备采集方案)
        ├── netmiko_enabled: 是否启用Netmiko采集
        ├── netconf_enabled: 是否启用NETCONF采集
        ├── textfsm_enabled: 是否启用TextFSM解析
        ├── data_processor_enabled: 是否启用数据处理
        └── xml_templates: 关联的XML模板列表
            └── NetconfXMLTemplate (NETCONF XML模板)
```

### 核心组件

#### DeviceCollectionService
主要的业务逻辑服务类，负责：
- 设备采集执行
- 数据格式转换
- 结果存储管理
- 错误处理

**主要方法**:
- `execute_both_collection(plan, device)` - 同时执行NETCONF和Netmiko采集
- `execute_netmiko_collection(plan, device)` - 执行Netmiko采集并保存
- `execute_netconf_collection(plan, device)` - 执行NETCONF采集并保存
- `execute_netmiko_collection_only(plan, device)` - 仅执行Netmiko采集
- `execute_netconf_collection_only(plan, device)` - 仅执行NETCONF采集

#### DeviceSummaryPlansViewSet
采集汇总方案管理，提供：
- 汇总方案CRUD操作
- 厂商和设备类型管理
- 关联采集方案查询
- 批量执行所有子采集方案

#### DeviceCollectionPlanViewSet
采集方案管理，提供：
- 采集方案配置
- 字段映射管理
- 数据处理配置
- 单独和双重采集执行

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Django 3.2+
- MongoDB 4.4+
- Redis 6.0+

### 安装步骤

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置数据库**
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'device_api',
        # ... 其他配置
    }
}

# MongoDB配置
MONGODB_URI = 'mongodb://localhost:27017/'
COLLECTION_RESULTS_DB = 'device_collection_results'
```

3. **运行迁移**
```bash
python manage.py makemigrations device_api
python manage.py migrate
```

4. **启动服务**
```bash
python manage.py runserver
```

## 📚 数据模型

### DeviceSummaryPlans (采集汇总方案)

```python
class DeviceSummaryPlans(models.Model):
    name = models.CharField(max_length=100, verbose_name='采集汇总名称')
    vendor = models.CharField(max_length=30, choices=VENDOR_CHOICES)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**支持的厂商**: H3C, Huawei, Cisco, Hillstone, Ruijie, Mellanox, Centec
**设备类型**: switch, router, firewall, load_balancer, server

### DeviceCollectionPlan (设备采集方案)

```python
class DeviceCollectionPlan(models.Model):
    summary_plan = models.ForeignKey(DeviceSummaryPlans, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, verbose_name='采集方案名称')
    
    # Netmiko配置
    netmiko_enabled = models.BooleanField(default=True)
    netmiko_method = models.CharField(max_length=100, default='')
    netmiko_field_mappings = models.JSONField(default=dict)
    
    # NETCONF配置
    netconf_enabled = models.BooleanField(default=False)
    netconf_method = models.CharField(max_length=100, default='')
    netconf_field_mappings = models.JSONField(default=dict)
    
    # TextFSM配置
    textfsm_enabled = models.BooleanField(default=False)
    textfsm_template = models.CharField(max_length=100, default='')
    
    # 数据处理配置
    data_processor_enabled = models.BooleanField(default=False)
    data_processor = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
```

### NetconfXMLTemplate (NETCONF XML模板)

```python
class NetconfXMLTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name='模板名称')
    xml_template = models.TextField(verbose_name='XML模板内容')
    description = models.TextField(blank=True, null=True)
    collection_plan = models.ForeignKey(DeviceCollectionPlan, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
```

## 🔄 采集流程

### 1. 双重采集流程

```python
# 同时执行NETCONF和Netmiko采集
result = DeviceCollectionService.execute_both_collection(plan, device)

if result['success']:
    # 采集成功，数据已自动保存到MongoDB
    # 注意：只要有一种采集方式成功就算成功
    netconf_result = result['netconf_result']
    netmiko_result = result['netmiko_result']
    message = result['message']  # 例如："NETCONF采集成功; Netmiko采集成功"
else:
    # 采集失败 - 所有可用的采集方式都失败了
    error = result['error']
```

### 2. 单独采集流程

```python
# Netmiko采集
success, message = DeviceCollectionService.execute_netmiko_collection(plan, device)

# NETCONF采集  
success, message = DeviceCollectionService.execute_netconf_collection(plan, device)
```

### 3. 批量采集流程

```python
# 执行汇总方案下所有启用的采集方案
# 通过API: POST /api/device-api/summary-plans/{id}/execute_all_collections/
{
    "device_ip": "192.168.1.1"
}
```

### 4. 验证规则

- **单独采集**: 必须启用对应采集方式且设备配置相应账户
- **双重采集**: 至少启用一种采集方式且设备配置相应账户（只要有一种配置正确即可执行）

## 📝 字段映射配置

### 配置格式

字段映射支持复杂的JSONPath风格表达式：

```json
{
  "interface_name": {
    "value": "interfaces[*].name",
    "sort": 0,
    "type": "string"
  },
  "interface_status": {
    "value": "interfaces[*].status",
    "sort": 1,
    "type": "string"
  },
  "interface_speed": {
    "value": "interfaces[*].speed",
    "sort": 2,
    "type": "int"
  },
  "vlan_info": {
    "value": ["vlans[*].id", "vlans[*].name"],
    "sort": 3,
    "type": "string"
  }
}
```

### 支持的路径表达式

- **简单路径**: `interfaces.name`
- **数组索引**: `interfaces.0.name`
- **通配符**: `interfaces[*].name`
- **多路径**: `["path1", "path2"]`

### 数据类型支持

- `string`: 字符串（默认）
- `int`: 整数
- `float`: 浮点数
- `bool`: 布尔值
- `datetime`: 日期时间

## 🧠 数据处理功能

### 数据处理函数规范

```python
def process_data(raw_data):
    """
    数据处理函数
    
    Args:
        raw_data: 原始采集数据
        
    Returns:
        处理后的数据 (dict/list/str)
    """
    try:
        # 处理逻辑
        result = {
            'device_info': {
                'hostname': raw_data.get('hostname', 'Unknown'),
                'vendor': 'H3C',
                'model': raw_data.get('model', 'Unknown')
            },
            'interfaces': [],
            'summary': {}
        }
        
        # 处理接口信息
        if 'interfaces' in raw_data:
            for interface in raw_data['interfaces']:
                interface_info = {
                    'name': interface.get('name'),
                    'status': interface.get('status'),
                    'ip_address': interface.get('ip_address', 'N/A')
                }
                result['interfaces'].append(interface_info)
        
        return result
        
    except Exception as e:
        return {'error': f'Processing failed: {str(e)}'}
```

## 📡 API接口文档

### 1. 采集汇总方案 (DeviceSummaryPlans)

#### 基础CRUD操作
- `GET /api/device-api/summary-plans/` - 获取汇总方案列表
- `POST /api/device-api/summary-plans/` - 创建新的汇总方案
- `GET /api/device-api/summary-plans/{id}/` - 获取指定汇总方案详情
- `PUT /api/device-api/summary-plans/{id}/` - 更新指定汇总方案
- `DELETE /api/device-api/summary-plans/{id}/` - 删除指定汇总方案

#### 自定义动作
- `GET /api/device-api/summary-plans/{id}/collect_plans/` - 获取指定汇总方案下的所有采集方案
- `POST /api/device-api/summary-plans/{id}/create_collect_plan/` - 在指定汇总方案下创建采集方案
- `POST /api/device-api/summary-plans/{id}/execute_all_collections/` - 执行汇总方案下所有启用的采集方案

#### 筛选和排序
- 支持按 `vendor` 和 `device_type` 筛选
- 支持按 `name` 和 `description` 搜索
- 支持按 `id`, `name`, `vendor`, `device_type`, `created_at`, `updated_at` 排序

### 2. 设备采集方案 (DeviceCollectionPlan)

#### 基础CRUD操作
- `GET /api/device-api/collection-plan/` - 获取采集方案列表
- `POST /api/device-api/collection-plan/` - 创建新的采集方案
- `GET /api/device-api/collection-plan/{id}/` - 获取指定采集方案详情
- `PUT /api/device-api/collection-plan/{id}/` - 更新指定采集方案
- `DELETE /api/device-api/collection-plan/{id}/` - 删除指定采集方案

#### 自定义动作
- `POST /api/device-api/collection-plan/{id}/execute_netmiko/` - 执行Netmiko采集
- `POST /api/device-api/collection-plan/{id}/execute_netconf/` - 执行NETCONF采集
- `POST /api/device-api/collection-plan/{id}/execute_both_collection/` - 同时执行NETCONF和Netmiko采集
- `POST /api/device-api/collection-plan/{id}/execute_data_processor/` - 执行数据处理

#### 筛选和排序
- 支持按 `summary_plan__vendor` 和 `summary_plan__device_type` 筛选
- 支持按 `netmiko_enabled`, `netconf_enabled`, `is_active` 筛选
- 支持按 `name`, `description`, `summary_plan__name` 搜索

### 3. NETCONF XML模板 (NetconfXMLTemplate)

#### 基础CRUD操作
- `GET /api/device-api/xml-templates/` - 获取XML模板列表
- `POST /api/device-api/xml-templates/` - 创建新的XML模板
- `GET /api/device-api/xml-templates/{id}/` - 获取指定XML模板详情
- `PUT /api/device-api/xml-templates/{id}/` - 更新指定XML模板
- `DELETE /api/device-api/xml-templates/{id}/` - 删除指定XML模板

#### 自定义动作
- `POST /api/device-api/xml-templates/{id}/duplicate/` - 复制XML模板
- `GET /api/device-api/xml-templates/by_collection_plan/` - 根据采集方案获取XML模板

### 4. 采集日志 (CollectionLog)

#### 基础操作
- `GET /api/device-api/collection-logs/` - 获取采集日志列表

#### 筛选和查询
- 支持按设备IP、汇总方案、采集方案、采集类型、状态等条件筛选
- 支持分页和排序

## 💡 使用示例

### 创建采集汇总方案

```bash
curl -X POST "http://localhost:8000/api/device-api/summary-plans/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "H3C交换机采集方案",
    "vendor": "H3C",
    "device_type": "switch",
    "description": "用于采集H3C交换机信息的汇总方案"
  }'
```

### 在汇总方案下创建采集方案

```bash
curl -X POST "http://localhost:8000/api/device-api/summary-plans/1/create_collect_plan/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "接口信息采集",
    "description": "采集交换机接口信息",
    "netmiko_enabled": true,
    "netmiko_method": "get_interfaces",
    "netconf_enabled": false,
    "netmiko_field_mappings": {
      "interface_name": {
        "value": "interfaces[*].name",
        "sort": 0,
        "type": "string"
      },
      "interface_status": {
        "value": "interfaces[*].status",
        "sort": 1,
        "type": "string"
      }
    }
  }'
```

### 执行汇总方案下所有采集方案

```bash
curl -X POST "http://localhost:8000/api/device-api/summary-plans/1/execute_all_collections/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "device_ip": "192.168.1.1"
  }'
```

**响应示例**:
```json
{
  "code": 200,
  "message": "部分采集方案执行成功 (2/3)",
  "data": {
    "summary_plan_id": 1,
    "summary_plan_name": "H3C交换机采集方案",
    "device_ip": "192.168.1.1",
    "total_plans": 3,
    "success_count": 2,
    "failed_count": 1,
    "results": [
      {
        "plan_id": 1,
        "plan_name": "接口信息采集",
        "status": "success",
        "message": "NETCONF采集成功; Netmiko采集成功",
        "netconf_result": "采集并保存成功",
        "netmiko_result": "采集并保存成功"
      },
      {
        "plan_id": 2,
        "plan_name": "VLAN信息采集",
        "status": "success",
        "message": "Netmiko采集成功",
        "netconf_result": null,
        "netmiko_result": "采集并保存成功"
      },
      {
        "plan_id": 3,
        "plan_name": "配置备份",
        "status": "skipped",
        "message": "采集方案不可用（未配置相应账户）"
      }
    ]
  }
}
```

### 执行双重采集

```bash
curl -X POST "http://localhost:8000/api/device-api/collection-plan/1/execute_both_collection/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "device_ip": "192.168.1.1"
  }'
```

### 执行数据处理

```bash
curl -X POST "http://localhost:8000/api/device-api/collection-plan/1/execute_data_processor/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "result_id": "507f1f77bcf86cd799439011"
  }'
```

## 📊 日志管理

### 查询采集日志

```bash
# 获取指定设备的采集日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?device_ip=192.168.1.1&limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取指定汇总方案的失败日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?summary_plan_id=1&status=failed" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取指定采集方案的NETCONF日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?plan_id=1&collection_type=netconf" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取时间范围内的日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 分页查询日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?offset=100&limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**响应示例**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "total": 150,
    "count": 50,
    "offset": 0,
    "limit": 50,
    "logs": [...]
  }
}
```

## 💾 MongoDB数据结构

### 采集结果文档

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "plan_id": 1,
  "plan_name": "H3C交换机配置采集",
  "device_ip": "192.168.1.1",
  "collection_method": "netmiko",
  "method_name": "get_interfaces",
  "raw_data": {
    "interfaces": [
      {
        "name": "GigabitEthernet1/0/1",
        "status": "up",
        "ip_address": "192.168.1.1"
      }
    ]
  },
  "processed_data": null,
  "collected_at": "2024-01-01T10:00:00",
  "status": "success"
}
```

### 处理后的文档

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "plan_id": 1,
  "plan_name": "H3C交换机配置采集",
  "device_ip": "192.168.1.1",
  "collection_method": "netmiko",
  "method_name": "get_interfaces",
  "raw_data": {...},
  "processed_data": {
    "device_info": {
      "hostname": "SW-CORE-01",
      "vendor": "H3C",
      "model": "S6800-54QF"
    },
    "interfaces": [
      {
        "name": "GigabitEthernet1/0/1",
        "status": "up",
        "ip_address": "192.168.1.1"
      }
    ],
    "summary": {
      "total_interfaces": 1,
      "up_interfaces": 1
    }
  },
  "collected_at": "2024-01-01T10:00:00",
  "status": "processed",
  "processing_time": 0.125,
  "processed_at": "2024-01-01T10:01:00"
}
```

### 采集日志文档

```json
{
  "_id": "507f1f77bcf86cd799439012",
  "summary_plan_id": 1,
  "summary_plan_name": "H3C交换机采集方案",
  "plan_id": 1,
  "plan_name": "接口信息采集",
  "device_ip": "192.168.1.1",
  "device_name": "SW-CORE-01",
  "collection_type": "netmiko",
  "method_name": "get_interfaces",
  "status": "success",
  "message": "采集成功",
  "details": {
    "collection_success": true,
    "textfsm_parsed": true
  },
  "executed_at": "2024-01-01T10:00:00"
}
```

## 🔧 部署指南

### 环境配置

1. **数据库配置**
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'device_api',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# MongoDB配置
MONGODB_URI = 'mongodb://localhost:27017/'
```

2. **Redis配置**
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### 生产环境部署

1. **使用Docker**
```bash
docker-compose up -d
```

2. **使用Gunicorn**
```bash
gunicorn --bind 0.0.0.0:8000 netaxe.wsgi:application
```

3. **配置Nginx**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🐛 故障排除

### 常见问题

#### 1. 采集失败
**问题**: 设备采集失败
**解决方案**:
- 检查设备连接配置
- 验证采集方案配置
- 查看日志文件
- 确认设备账户权限

#### 2. 数据处理错误
**问题**: 数据处理失败
**解决方案**:
- 检查数据处理代码语法
- 验证输入数据格式
- 查看处理日志
- 检查数据类型转换

#### 3. 性能问题
**问题**: 系统性能下降
**解决方案**:
- 优化数据库查询
- 调整并发设置
- 监控资源使用
- 增加缓存层

### 日志分析

#### 采集日志查询
```bash
# 查看失败日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?status=failed&limit=100"

# 查看特定设备日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?device_ip=192.168.1.1"

# 查看时间范围日志
curl -X GET "http://localhost:8000/api/device-api/collection-logs/?start_time=2024-01-01T00:00:00&end_time=2024-01-02T00:00:00"
```

#### 错误码说明
- `400`: 参数错误
- `401`: 认证失败
- `403`: 权限不足
- `404`: 资源不存在
- `500`: 服务器内部错误

## 📈 性能优化

### 数据处理优化
- 支持异步处理大量数据
- 内存使用优化
- 处理超时控制
- 错误重试机制

### 数据库优化
- MongoDB索引优化
- 数据分片存储
- 定期清理机制
- 连接池管理

## 🔒 安全特性

### 代码执行安全
- 数据处理代码沙箱执行
- 输入数据验证
- 执行时间限制
- 内存使用限制

### 数据安全
- 数据加密存储
- 访问权限控制
- 操作日志记录
- 敏感信息脱敏

## 🧪 测试

### 单元测试
```bash
python manage.py test apps.device_api.tests
```

### 集成测试
```bash
python manage.py test apps.device_api.tests.test_integration
```

### API测试
```bash
# 使用curl测试API
curl -X GET "http://localhost:8000/api/device-api/summary-plans/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。在提交代码前，请确保：

1. 代码符合PEP 8规范
2. 添加适当的测试用例
3. 更新相关文档
4. 通过所有测试检查

### 开发环境设置
```bash
# 克隆项目
git clone https://github.com/your-repo/device-api.git

# 安装依赖
pip install -r requirements.txt

# 运行测试
python manage.py test
```

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 📝 更新日志

### v2.1.0 (2024-01-15)
- 新增批量执行功能
- 优化日志记录系统
- 增强错误处理机制
- 完善API文档

### v2.0.0 (2024-01-01)
- 重构数据模型架构
- 新增数据处理功能
- 优化API接口设计
- 增强错误处理机制

### v1.0.0 (2023-12-01)
- 初始版本发布
- 支持NETCONF和Netmiko采集
- 基础字段映射功能
- MongoDB数据存储

---

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- **邮箱**: support@example.com
- **Issues**: [GitHub Issues](https://github.com/your-repo/device-api/issues)
- **文档**: [在线文档](https://docs.example.com/device-api)

---

*最后更新时间: 2024-01-15* 
