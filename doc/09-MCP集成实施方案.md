# MCP集成实施方案

## 1. 概述

### 1.1 MCP简介

Model Context Protocol (MCP) 是一个标准化协议，旨在使大语言模型（LLM）和AI应用能够高效地连接外部工具和数据源。MCP提供统一的接口设计，被誉为"AI界的USB-C接口"，允许AI应用通过标准化的方式访问和操作外部资源。

### 1.2 在NetAxe中的应用价值

NetAxe作为NetDevOps平台，集成MCP能力可以带来以下价值：

1. **AI增强运维能力**
   - 通过AI助手进行设备配置分析
   - 智能故障诊断和建议
   - 自动化运维决策支持

2. **统一工具集成接口**
   - 将现有功能（设备采集、配置管理、自动化任务）暴露为MCP工具
   - 支持第三方AI应用调用NetAxe能力
   - 扩展平台的可集成性

3. **数据源标准化访问**
   - 将CMDB、MongoDB采集数据、配置仓库等作为MCP资源
   - 支持AI应用查询和分析网络数据
   - 提供结构化的数据访问接口

4. **提升用户体验**
   - 通过自然语言与平台交互
   - 智能化的运维建议和操作
   - 降低运维人员的技术门槛

### 1.3 应用场景

#### 场景1：智能设备配置分析
- AI助手分析设备配置，识别潜在问题
- 提供配置优化建议
- 自动生成配置变更方案

#### 场景2：故障智能诊断
- 基于采集数据和日志，AI进行故障分析
- 提供诊断报告和解决方案
- 自动生成故障处理工单

#### 场景3：运维知识问答
- 基于平台数据回答运维问题
- 查询设备状态、配置历史等
- 提供运维最佳实践建议

#### 场景4：自动化任务编排
- 通过自然语言描述，自动生成自动化任务
- 智能推荐合适的采集方案
- 优化任务执行策略

## 2. 技术评估

### 2.1 现有技术栈兼容性

#### 优势
- **Python生态支持**: NetAxe基于Django/Python，MCP有完善的Python SDK
- **RESTful架构**: 现有API架构便于封装为MCP工具
- **插件系统**: 已有插件机制，可扩展MCP服务器
- **服务网格**: 已有service_mesh架构，可集成MCP服务
- **异步支持**: Django Channels支持WebSocket，可用于MCP通信

#### 挑战
- **协议学习**: 团队需要学习MCP协议规范
- **架构调整**: 需要设计MCP服务器架构
- **安全考虑**: MCP访问需要权限控制
- **性能影响**: AI调用可能增加系统负载

### 2.2 技术选型

#### MCP Python SDK
- **推荐**: 使用官方 `mcp` Python SDK
- **版本**: 最新稳定版本
- **安装**: `pip install mcp`

#### 通信方式
- **SSE (Server-Sent Events)**: 用于MCP服务器与客户端通信
- **WebSocket**: 可选，用于实时双向通信
- **HTTP**: 作为备选方案

#### 集成方式
- **独立服务**: 创建独立的MCP服务器服务
- **Django集成**: 在Django应用中集成MCP服务器
- **混合模式**: 核心功能独立服务，通过API与Django交互

### 2.3 依赖评估

#### 新增依赖
```python
# requirements.txt 新增
mcp>=0.1.0  # MCP Python SDK
sse-starlette>=1.6.0  # SSE支持（如果使用Starlette）
```

#### 现有依赖利用
- Django REST Framework: 封装现有API为MCP工具
- Django Channels: WebSocket支持
- Celery: 异步任务处理
- Redis: 缓存和消息队列

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    AI客户端 (Claude/ChatGPT等)           │
└────────────────────┬────────────────────────────────────┘
                     │ MCP Protocol
┌────────────────────▼────────────────────────────────────┐
│              MCP服务器 (NetAxe MCP Server)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Tools      │  │  Resources  │  │  Prompts     │   │
│  │   (工具)     │  │  (资源)     │  │  (提示词)    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼────┐ ┌─────▼─────┐ ┌───▼────────┐
│  Django    │ │  MongoDB  │ │   Redis    │
│  REST API  │ │  数据源    │ │   缓存     │
└────────────┘ └────────────┘ └────────────┘
```

### 3.2 MCP服务器架构

```
backend/
├── apps/
│   └── mcp_server/              # MCP服务器应用
│       ├── __init__.py
│       ├── apps.py
│       ├── server.py            # MCP服务器主类
│       ├── tools/                # MCP工具实现
│       │   ├── __init__.py
│       │   ├── device_tools.py   # 设备相关工具
│       │   ├── config_tools.py   # 配置相关工具
│       │   ├── automation_tools.py # 自动化工具
│       │   └── analysis_tools.py  # 分析工具
│       ├── resources/            # MCP资源实现
│       │   ├── __init__.py
│       │   ├── device_resources.py
│       │   ├── config_resources.py
│       │   └── data_resources.py
│       ├── prompts/              # MCP提示词
│       │   ├── __init__.py
│       │   └── system_prompts.py
│       ├── models.py             # MCP相关数据模型
│       ├── serializers.py
│       ├── views.py              # MCP管理视图
│       └── urls.py
├── service_mesh/
│   └── mcp_gateway.py           # MCP网关（可选）
└── utils/
    └── mcp/                      # MCP工具类
        ├── __init__.py
        ├── client.py             # MCP客户端（用于调用其他MCP服务器）
        └── helpers.py            # MCP辅助函数
```

### 3.3 核心组件设计

#### 3.3.1 MCP服务器 (server.py)
```python
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from apps.mcp_server.tools import register_tools
from apps.mcp_server.resources import register_resources
from apps.mcp_server.prompts import register_prompts

class NetAxeMCPServer:
    """NetAxe MCP服务器"""
    
    def __init__(self):
        self.server = Server("netaxe-mcp-server")
        self._register_all()
    
    def _register_all(self):
        """注册所有工具、资源和提示词"""
        register_tools(self.server)
        register_resources(self.server)
        register_prompts(self.server)
    
    async def run(self, host="0.0.0.0", port=8002):
        """启动MCP服务器"""
        transport = SseServerTransport(f"http://{host}:{port}/mcp")
        await self.server.run(transport)
```

#### 3.3.2 MCP工具示例 (device_tools.py)
```python
from mcp.server import Server
from mcp.types import Tool, TextContent
from apps.asset.models import NetworkDevice
from apps.asset.serializers import NetworkDeviceSerializer

def register_device_tools(server: Server):
    """注册设备相关工具"""
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="get_device_info",
                description="获取网络设备详细信息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_ip": {
                            "type": "string",
                            "description": "设备管理IP地址"
                        }
                    },
                    "required": ["device_ip"]
                }
            ),
            Tool(
                name="list_devices",
                description="列出所有网络设备",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "vendor": {
                            "type": "string",
                            "description": "厂商筛选（可选）"
                        },
                        "status": {
                            "type": "integer",
                            "description": "状态筛选（可选）"
                        }
                    }
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "get_device_info":
            device_ip = arguments.get("device_ip")
            try:
                device = NetworkDevice.objects.get(manage_ip=device_ip)
                serializer = NetworkDeviceSerializer(device)
                return [TextContent(
                    type="text",
                    text=json.dumps(serializer.data, ensure_ascii=False, indent=2)
                )]
            except NetworkDevice.DoesNotExist:
                return [TextContent(
                    type="text",
                    text=f"设备 {device_ip} 不存在"
                )]
        
        elif name == "list_devices":
            vendor = arguments.get("vendor")
            status = arguments.get("status")
            queryset = NetworkDevice.objects.all()
            if vendor:
                queryset = queryset.filter(vendor__name=vendor)
            if status is not None:
                queryset = queryset.filter(status=status)
            
            devices = NetworkDeviceSerializer(queryset[:50], many=True).data
            return [TextContent(
                type="text",
                text=json.dumps(devices, ensure_ascii=False, indent=2)
            )]
        
        else:
            raise ValueError(f"未知工具: {name}")
```

#### 3.3.3 MCP资源示例 (device_resources.py)
```python
from mcp.server import Server
from mcp.types import Resource, TextContent
from apps.asset.models import NetworkDevice

def register_device_resources(server: Server):
    """注册设备相关资源"""
    
    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="netaxe://device/list",
                name="设备列表",
                description="所有网络设备列表",
                mimeType="application/json"
            ),
            Resource(
                uri="netaxe://device/{device_ip}",
                name="设备详情",
                description="指定设备的详细信息",
                mimeType="application/json"
            )
        ]
    
    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "netaxe://device/list":
            devices = NetworkDevice.objects.all()[:100]
            data = [{
                "id": d.id,
                "name": d.name,
                "manage_ip": d.manage_ip,
                "vendor": d.vendor.name if d.vendor else None,
                "status": d.status
            } for d in devices]
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        elif uri.startswith("netaxe://device/"):
            device_ip = uri.split("/")[-1]
            try:
                device = NetworkDevice.objects.get(manage_ip=device_ip)
                serializer = NetworkDeviceSerializer(device)
                return json.dumps(serializer.data, ensure_ascii=False, indent=2)
            except NetworkDevice.DoesNotExist:
                raise ValueError(f"设备 {device_ip} 不存在")
        
        else:
            raise ValueError(f"未知资源: {uri}")
```

## 4. 实施计划

### 4.1 第一阶段：MVP验证（2-3周）

#### 目标
验证MCP在NetAxe中的可行性，实现基础功能。

#### 任务清单
1. **环境准备**（3天）
   - 安装MCP Python SDK
   - 搭建MCP服务器基础框架
   - 配置开发环境

2. **核心功能开发**（10天）
   - 实现MCP服务器基础类
   - 开发3-5个核心工具（设备查询、配置查询等）
   - 实现2-3个核心资源（设备列表、配置数据等）
   - 添加基础权限控制

3. **测试验证**（5天）
   - 单元测试
   - 集成测试
   - 与AI客户端（Claude Desktop等）联调

4. **文档编写**（2天）
   - API文档
   - 使用指南
   - 开发文档

#### 交付物
- 可运行的MCP服务器
- 基础工具和资源
- 测试报告
- 技术文档

### 4.2 第二阶段：功能扩展（4-6周）

#### 目标
扩展MCP功能，覆盖主要业务场景。

#### 任务清单
1. **工具扩展**（3周）
   - 设备管理工具（创建、更新、删除）
   - 配置管理工具（备份、比较、合规检查）
   - 自动化任务工具（创建任务、查询状态）
   - 数据分析工具（接口利用率、故障分析）

2. **资源扩展**（2周）
   - 配置历史资源
   - 采集数据资源
   - 任务执行结果资源
   - 拓扑图资源

3. **提示词优化**（1周）
   - 系统提示词设计
   - 上下文管理
   - 错误处理提示

4. **安全增强**（1周）
   - 权限细化
   - 访问审计
   - 速率限制

#### 交付物
- 完整的工具集（15+工具）
- 丰富的资源库（10+资源）
- 安全机制
- 性能优化

### 4.3 第三阶段：生产就绪（4-6周）

#### 目标
完善功能，优化性能，准备生产部署。

#### 任务清单
1. **性能优化**（2周）
   - 缓存机制
   - 异步处理
   - 连接池优化
   - 负载测试

2. **监控和日志**（1周）
   - 监控指标
   - 日志记录
   - 告警机制

3. **文档完善**（1周）
   - 用户手册
   - 运维手册
   - API参考

4. **生产部署**（2周）
   - 部署脚本
   - 配置管理
   - 回滚方案
   - 上线验证

#### 交付物
- 生产级MCP服务器
- 完整文档
- 部署方案
- 运维工具

## 5. 详细实施步骤

### 5.1 环境搭建

#### 5.1.1 安装依赖
```bash
cd backend
pip install mcp sse-starlette
# 或使用requirements.txt
echo "mcp>=0.1.0" >> requirements.txt
echo "sse-starlette>=1.6.0" >> requirements.txt
pip install -r requirements.txt
```

#### 5.1.2 创建Django应用
```bash
python manage.py startapp mcp_server
```

#### 5.1.3 配置Django
在 `settings.py` 中添加：
```python
INSTALLED_APPS = [
    # ... 其他应用
    'apps.mcp_server',
]
```

### 5.2 核心代码实现

#### 5.2.1 MCP服务器主类
创建 `apps/mcp_server/server.py`:
```python
import asyncio
import logging
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from django.conf import settings

logger = logging.getLogger(__name__)

class NetAxeMCPServer:
    """NetAxe MCP服务器"""
    
    def __init__(self):
        self.server = Server("netaxe-mcp-server")
        self._register_components()
    
    def _register_components(self):
        """注册所有组件"""
        from apps.mcp_server.tools import register_all_tools
        from apps.mcp_server.resources import register_all_resources
        from apps.mcp_server.prompts import register_all_prompts
        
        register_all_tools(self.server)
        register_all_resources(self.server)
        register_all_prompts(self.server)
    
    async def run(self):
        """运行MCP服务器"""
        host = getattr(settings, 'MCP_SERVER_HOST', '0.0.0.0')
        port = getattr(settings, 'MCP_SERVER_PORT', 8002)
        
        transport = SseServerTransport(f"http://{host}:{port}/mcp")
        logger.info(f"启动MCP服务器: http://{host}:{port}/mcp")
        
        await self.server.run(transport)
```

#### 5.2.2 工具注册器
创建 `apps/mcp_server/tools/__init__.py`:
```python
from mcp.server import Server
from .device_tools import register_device_tools
from .config_tools import register_config_tools
from .automation_tools import register_automation_tools

def register_all_tools(server: Server):
    """注册所有工具"""
    register_device_tools(server)
    register_config_tools(server)
    register_automation_tools(server)
```

#### 5.2.3 管理命令
创建 `apps/mcp_server/management/commands/run_mcp_server.py`:
```python
from django.core.management.base import BaseCommand
import asyncio
from apps.mcp_server.server import NetAxeMCPServer

class Command(BaseCommand):
    help = '启动MCP服务器'

    def handle(self, *args, **options):
        server = NetAxeMCPServer()
        asyncio.run(server.run())
```

### 5.3 权限控制

#### 5.3.1 权限装饰器
创建 `apps/mcp_server/utils/auth.py`:
```python
from functools import wraps
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated

def mcp_permission_required(permission_name):
    """MCP工具权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从上下文获取用户信息
            # 检查权限
            # 如果无权限，抛出异常
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

#### 5.3.2 权限模型
在 `apps/mcp_server/models.py` 中定义：
```python
from django.db import models
from django.contrib.auth.models import User

class MCPToolPermission(models.Model):
    """MCP工具权限"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool_name = models.CharField(max_length=100)
    allowed = models.BooleanField(default=True)
    
    class Meta:
        unique_together = [['user', 'tool_name']]
```

### 5.4 配置管理

#### 5.4.1 配置文件
在 `config/config.json` 中添加：
```json
{
  "mcp_server": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8002,
    "auth_required": true,
    "rate_limit": {
      "enabled": true,
      "requests_per_minute": 60
    }
  }
}
```

#### 5.4.2 Django设置
在 `settings.py` 中添加：
```python
# MCP服务器配置
MCP_SERVER_ENABLED = config.mcp_server.get('enabled', False)
MCP_SERVER_HOST = config.mcp_server.get('host', '0.0.0.0')
MCP_SERVER_PORT = config.mcp_server.get('port', 8002)
MCP_AUTH_REQUIRED = config.mcp_server.get('auth_required', True)
```

## 6. 工具和资源清单

### 6.1 工具清单

#### 设备管理工具
- `get_device_info`: 获取设备详细信息
- `list_devices`: 列出设备
- `search_devices`: 搜索设备
- `get_device_status`: 获取设备状态
- `get_device_interfaces`: 获取设备接口信息

#### 配置管理工具
- `get_config`: 获取设备配置
- `compare_configs`: 比较配置差异
- `backup_config`: 备份配置
- `check_compliance`: 合规性检查
- `apply_config_template`: 应用配置模板

#### 自动化工具
- `create_collection_task`: 创建采集任务
- `get_task_status`: 获取任务状态
- `execute_automation_flow`: 执行自动化流程
- `get_collection_result`: 获取采集结果

#### 分析工具
- `analyze_interface_utilization`: 分析接口利用率
- `diagnose_network_issue`: 网络故障诊断
- `suggest_config_optimization`: 配置优化建议

### 6.2 资源清单

#### 设备资源
- `netaxe://device/list`: 设备列表
- `netaxe://device/{ip}`: 设备详情
- `netaxe://device/{ip}/interfaces`: 设备接口

#### 配置资源
- `netaxe://config/{ip}/current`: 当前配置
- `netaxe://config/{ip}/history`: 配置历史
- `netaxe://config/templates`: 配置模板

#### 数据资源
- `netaxe://data/arp/{ip}`: ARP表数据
- `netaxe://data/mac/{ip}`: MAC地址表
- `netaxe://data/lldp/{ip}`: LLDP邻居信息
- `netaxe://data/interface/{ip}`: 接口数据

#### 任务资源
- `netaxe://task/{task_id}`: 任务详情
- `netaxe://task/{task_id}/result`: 任务结果

## 7. 安全考虑

### 7.1 认证和授权

#### 认证方式
- **API Key认证**: 为MCP客户端分配API Key
- **Token认证**: 使用JWT Token
- **OAuth 2.0**: 支持标准OAuth流程

#### 权限控制
- 基于角色的访问控制（RBAC）
- 工具级权限控制
- 资源级权限控制
- 操作审计日志

### 7.2 数据安全

#### 敏感数据保护
- 密码字段不暴露
- 敏感配置信息脱敏
- 访问日志记录

#### 传输安全
- 使用HTTPS
- TLS加密
- 证书验证

### 7.3 速率限制

#### 限制策略
- 请求频率限制（每分钟请求数）
- 并发连接限制
- 资源访问限制

#### 实现方式
```python
from django.core.cache import cache
from functools import wraps

def rate_limit(max_requests=60, window=60):
    """速率限制装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 实现速率限制逻辑
            pass
        return wrapper
    return decorator
```

## 8. 监控和运维

### 8.1 监控指标

#### 性能指标
- 请求响应时间
- 并发连接数
- 工具调用次数
- 错误率

#### 业务指标
- 工具使用统计
- 资源访问统计
- 用户活跃度
- 热门工具排行

### 8.2 日志记录

#### 日志内容
- 所有工具调用
- 资源访问记录
- 错误和异常
- 性能数据

#### 日志格式
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "service": "mcp-server",
  "tool": "get_device_info",
  "user": "admin",
  "arguments": {"device_ip": "192.168.1.1"},
  "duration_ms": 150,
  "status": "success"
}
```

### 8.3 告警机制

#### 告警条件
- 错误率超过阈值
- 响应时间过长
- 服务不可用
- 异常流量

#### 告警方式
- 邮件通知
- 短信通知
- 企业微信/钉钉
- 集成到现有告警系统

## 9. 测试策略

### 9.1 单元测试

#### 测试范围
- 工具函数
- 资源读取
- 权限检查
- 错误处理

#### 测试示例
```python
import pytest
from apps.mcp_server.tools.device_tools import get_device_info

@pytest.mark.django_db
async def test_get_device_info():
    result = await get_device_info({"device_ip": "192.168.1.1"})
    assert result is not None
    assert "device_ip" in result
```

### 9.2 集成测试

#### 测试场景
- MCP服务器启动
- 工具调用流程
- 资源访问流程
- 权限验证流程

### 9.3 端到端测试

#### 测试工具
- 使用MCP客户端SDK
- 模拟AI客户端调用
- 验证完整流程

## 10. 部署方案

### 10.1 Docker部署

#### Dockerfile
```dockerfile
FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "manage.py", "run_mcp_server"]
```

#### docker-compose配置
```yaml
mcp-server:
  build: .
  ports:
    - "8002:8002"
  environment:
    - MCP_SERVER_HOST=0.0.0.0
    - MCP_SERVER_PORT=8002
  depends_on:
    - redis
    - mysql
  networks:
    - netaxe_network
```

### 10.2 Supervisor部署

#### Supervisor配置
```ini
[program:netaxe-mcp-server]
command=/path/to/venv/bin/python manage.py run_mcp_server
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/netaxe/mcp-server.log
stderr_logfile=/var/log/netaxe/mcp-server-error.log
```

### 10.3 系统服务部署

#### systemd服务文件
```ini
[Unit]
Description=NetAxe MCP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/venv/bin/python manage.py run_mcp_server
Restart=always

[Install]
WantedBy=multi-user.target
```

## 11. 风险评估和 mitigation

### 11.1 技术风险

#### 风险1: MCP协议变更
- **风险**: MCP协议还在演进，可能有breaking changes
- **影响**: 高
- **缓解**: 
  - 锁定SDK版本
  - 关注MCP官方更新
  - 设计抽象层隔离协议细节

#### 风险2: 性能问题
- **风险**: AI调用可能带来高负载
- **影响**: 中
- **缓解**:
  - 实现缓存机制
  - 异步处理
  - 速率限制
  - 负载测试

#### 风险3: 安全漏洞
- **风险**: MCP接口可能被滥用
- **影响**: 高
- **缓解**:
  - 严格的权限控制
  - 输入验证
  - 审计日志
  - 安全测试

### 11.2 业务风险

#### 风险1: 用户接受度
- **风险**: 用户可能不习惯AI交互方式
- **影响**: 中
- **缓解**:
  - 提供传统接口作为备选
  - 用户培训
  - 逐步推广

#### 风险2: 数据准确性
- **风险**: AI可能给出错误建议
- **影响**: 高
- **缓解**:
  - 重要操作需要人工确认
  - 提供置信度评分
  - 记录所有AI建议

### 11.3 运维风险

#### 风险1: 服务可用性
- **风险**: MCP服务器故障影响AI功能
- **影响**: 中
- **缓解**:
  - 高可用部署
  - 健康检查
  - 自动恢复
  - 降级方案

## 12. 成功标准

### 12.1 功能标准
- ✅ 实现20+个MCP工具
- ✅ 实现10+个MCP资源
- ✅ 支持主流AI客户端（Claude Desktop、ChatGPT等）
- ✅ 响应时间 < 2秒（95%请求）
- ✅ 可用性 > 99.5%

### 12.2 质量标准
- ✅ 代码覆盖率 > 80%
- ✅ 无严重安全漏洞
- ✅ 完整的文档
- ✅ 通过性能测试

### 12.3 业务标准
- ✅ 至少3个实际应用场景
- ✅ 用户满意度 > 80%
- ✅ 工具调用成功率 > 95%

## 13. 后续规划

### 13.1 功能扩展
- 支持更多AI模型
- 增加更多工具和资源
- 支持自定义工具开发
- 工具市场/插件生态

### 13.2 性能优化
- 缓存策略优化
- 并发处理优化
- 数据库查询优化

### 13.3 生态建设
- 开发者文档
- SDK和示例代码
- 社区支持
- 最佳实践分享

## 14. 参考资料

### 14.1 MCP官方资源
- MCP规范: https://modelcontextprotocol.io/
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- 示例代码: https://github.com/modelcontextprotocol/servers

### 14.2 相关文档
- NetAxe项目文档: `doc/` 目录
- Django文档: https://docs.djangoproject.com/
- Django Channels文档: https://channels.readthedocs.io/

### 14.3 社区资源
- MCP社区讨论
- 相关技术博客
- 最佳实践案例

## 15. 附录

### 15.1 术语表
- **MCP**: Model Context Protocol，模型上下文协议
- **Tool**: MCP工具，可被AI调用的功能
- **Resource**: MCP资源，可被AI访问的数据源
- **Prompt**: MCP提示词，系统提示信息
- **SSE**: Server-Sent Events，服务器推送事件

### 15.2 配置示例
见各章节中的代码示例。

### 15.3 常见问题
- Q: MCP服务器如何与现有Django应用集成？
  A: 可以作为独立服务运行，通过API与Django交互，也可以集成到Django应用中。

- Q: 是否需要修改现有代码？
  A: 不需要，MCP服务器是新增功能，通过调用现有API实现。

- Q: 如何控制AI的访问权限？
  A: 通过权限系统控制，可以为不同用户分配不同的工具和资源访问权限。
