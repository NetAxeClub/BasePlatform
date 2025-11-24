# 设备采集方案定时任务逻辑文档

## 一、以前方案（automation/tasks.py）定时任务采集逻辑

### 1.1 整体架构

```
collect_device_main (主调度任务)
    ↓
collect_device (单个设备采集任务)
    ↓
厂商处理类 (H3cProc/HuaweiProc等)
    ↓
BaseConn.collection_run() (基础采集方法)
    ↓
CLI采集 (Netmiko) + NETCONF采集
    ↓
数据解析 (TextFSM/XML解析)
    ↓
写入MongoDB
```

### 1.2 主调度任务 `collect_device_main(**kwargs)`

**执行流程：**

1. **数据缓存更新** (`datas_to_cache()`)
   - 将ARP、MAC、LLDP、聚合端口、三层接口等表数据写入Redis缓存
   - 缓存键格式：`arp_{ip}`, `mac_{idc}_{mac}`, `lldp_{hostip}_{interface}` 等
   - 用途：用于地址定位、拓扑发现等功能

2. **CMDB同步** (`MainIn.cmdb_to_mongo()`)
   - 将Django ORM中的设备信息同步到MongoDB
   - 同步字段：name, idc__name, serial_num, manage_ip, status, chassis, slot等
   - 存储位置：MongoDB `Automation.networkdevice` 集合

3. **获取设备列表** (`get_device_info_v2(**kwargs)`)
   - 查询条件：`status=0, auto_enable=True, vendor__alias in support_vendor`
   - 返回设备信息包含：
     - 基本信息：manage_ip, name, vendor__alias, plan_id等
     - 账号信息：ssh账号（username, password, port）、netconf账号
     - 协议信息：支持的协议列表（ssh/telnet/netconf）

4. **清空历史数据** (`clear_his_collect_res()`)
   - 清空MongoDB中的历史采集数据：
     - `collect_textfsm_info` - TextFSM解析记录
     - `netconf_failed` - NETCONF失败记录
     - `NETCONF` 数据库下的所有表
   - 目的：避免旧数据干扰新采集结果

5. **批量下发任务**
   - 遍历所有设备，为每个设备创建 `collect_device` 异步任务
   - 任务队列：`queue='config'`
   - 支持重试：`retry=True`

### 1.3 单个设备采集任务 `collect_device(**kwargs)`

**执行流程：**

1. **设备验证**
   - 检查IP有效性（不能为0.0.0.0）
   - 检查是否关联采集方案（plan_id）
   - 检查是否启用自动化（auto_enable）

2. **厂商处理类选择**
   ```python
   CLASS_MAP = {
       'H3C': H3cProc,
       'Huawei': HuaweiProc,
       'Hillstone': HillstoneProc,
       'Mellanox': MellanoxProc,
       'centec': CentecProc,
       'Ruijie': RuijieProc,
       'Maipu': MaipuProc,
       'Cisco': CiscoProc,
       'ZTE': ZteProc,
   }
   ```

3. **实例化处理类**
   - 传入设备信息（包含plan_id、账号密码等）
   - 处理类初始化时会：
     - 从 `CollectionPlan` 获取采集方案配置
     - 构建Netmiko连接参数
     - 构建NETCONF连接参数（如果支持）

4. **执行采集** (`class_instance.collection_run()`)

### 1.4 厂商处理类 `collection_run()` 方法

**以H3cProc为例：**

#### 1.4.1 父类方法 `BaseConn.collection_run()`

**CLI采集流程：**

1. **获取命令列表**
   ```python
   cmds = json.loads(self.plan['commands'])
   # 例如：["display arp", "display mac-address", "display interface brief"]
   ```

2. **执行命令**
   - 使用Netmiko连接设备
   - 遍历执行每个命令
   - 将命令输出保存到文件：`automation/{hostip}/{cmd}.txt`
   - 例如：`automation/10.254.1.1/display_arp.txt`

3. **数据解析**
   - 调用 `_collection_analysis(paths)` 方法
   - 使用TextFSM模板解析命令输出
   - 调用 `StandardFSMAnalysis` 类的方法处理数据：
     - `layer_2_interface()` - 二层接口解析
     - `layer_3_interface()` - 三层接口解析
     - `mac_address_proc()` - MAC地址解析
     - `arp_table_proc()` - ARP表解析
     - `lldp_proc()` - LLDP解析
     - `aggre_port_proc()` - 聚合端口解析

4. **数据入库**
   - 将解析后的数据写入MongoDB：
     - `Automation.layer2interface` - 二层接口
     - `Automation.layer3interface` - 三层接口
     - `Automation.MACTable` - MAC地址表
     - `Automation.ARPTable` - ARP表
     - `Automation.LLDPTable` - LLDP表
     - `Automation.AggreTable` - 聚合端口表

#### 1.4.2 NETCONF采集流程

1. **检查NETCONF配置**
   - 检查 `self.netconf_class` 是否配置
   - 例如：`H3CinfoCollection`, `H3CSecPath`

2. **建立NETCONF连接**
   ```python
   self.device = H3CinfoCollection(
       host=self.netconf_params['ip'],
       user=self.netconf_params['username'],
       password=self.netconf_params['password'],
       timeout=600
   )
   ```

3. **执行NETCONF方法**
   ```python
   methods = json.loads(self.plan['netconf_method'])
   # 例如：["get_arp", "get_interface", "get_lldp"]
   for method in methods:
       class_method = getattr(self.device, method, None)
       res = class_method()
       self._netconf_method_map(method, res)
   ```

4. **数据解析和入库**
   - 调用 `_netconf_method_map(method, res)` 解析XML数据
   - 根据方法名映射到对应的解析函数
   - 将结构化数据写入MongoDB

### 1.5 采集方案模型（旧方案）

**automation.CollectionPlan 模型结构：**

```python
class CollectionPlan(models.Model):
    vendor = models.CharField(max_length=50)  # 厂商：H3C, Huawei等
    category = models.CharField(max_length=50)  # 类型：交换机/防火墙/路由器
    name = models.CharField(max_length=100)  # 方案名称
    commands = models.TextField(default='[]')  # JSON格式的命令列表
    netconf_method = models.TextField(default='[]')  # JSON格式的方法列表
    netconf_class = models.CharField(max_length=100)  # NETCONF连接类名
    memo = models.TextField()  # 备注
```

**示例数据：**
```json
{
    "vendor": "H3C",
    "category": "交换机",
    "name": "H3C交换机标准采集方案",
    "commands": "[\"display arp\", \"display mac-address\", \"display interface brief\"]",
    "netconf_method": "[\"get_arp\", \"get_interface\"]",
    "netconf_class": "H3CinfoCollection"
}
```

### 1.6 数据解析流程

#### 1.6.1 CLI命令解析

1. **TextFSM模板解析**
   - 使用TextFSM模板文件解析命令输出
   - 模板路径：`utils/connect_layer/auto_main/` 目录下
   - 例如：`hp_comware_display_arp.textfsm`

2. **数据格式化**
   - 调用 `StandardFSMAnalysis` 类的方法
   - 不同厂商有不同的格式化逻辑：
     - H3C：接口名称转换（GE -> GigabitEthernet）
     - 华为：接口名称转换（GE -> GigabitEthernet）
     - 山石：MAC地址格式转换（. -> -）

3. **数据入库**
   - 统一写入MongoDB对应集合

#### 1.6.2 NETCONF数据解析

1. **XML数据解析**
   - NETCONF返回XML格式数据
   - 使用ncclient解析XML
   - 转换为Python字典结构

2. **方法映射**
   - 根据方法名（如 `get_arp`）映射到对应的解析函数
   - 不同厂商有不同的解析逻辑

3. **数据入库**
   - 转换为统一格式后写入MongoDB

### 1.7 采集规则任务 `collect_device_by_rule()`

**功能：** 根据采集规则（CollectionRule）动态匹配设备并执行采集

**执行流程：**

1. **获取所有采集规则**
   ```python
   rule_query = CollectionRule.objects.prefetch_related('match_rule').values(...)
   ```

2. **构建设备查询条件**
   - 从 `CollectionMatchRule` 获取匹配规则
   - 构建Django ORM查询条件
   - 例如：`vendor__alias__exact='H3C'`, `category__name__contains='交换机'`

3. **获取匹配的设备**
   ```python
   hosts = get_device_info_v2(**query_params)
   ```

4. **下发采集任务**
   - 调用 `collect_info_sub` 任务
   - 传入设备信息和规则信息

### 1.8 关键函数说明

#### `get_device_info_v2(**kwargs)`
- **功能：** 获取设备信息，包含账号密码等
- **返回：** 设备信息列表，每个设备包含：
  - 基本信息：manage_ip, name, vendor__alias, plan_id等
  - SSH账号：ssh['username'], ssh['password'], ssh['port']
  - NETCONF账号：netconf['username'], netconf['password'], netconf['port']
  - 协议列表：protocol = ['ssh', 'netconf']

#### `datas_to_cache()`
- **功能：** 将MongoDB中的数据写入Redis缓存
- **缓存内容：**
  - ARP表：`device_arp_{ip}`
  - MAC表：`device_mac_{idc}_{mac}`
  - LLDP表：`lldp_{hostip}_{interface}`
  - 聚合端口：`lagg_{hostip}_{aggregroup}`
  - 三层接口：`layer3interface_{hostip}_{ipaddress}`

#### `clear_his_collect_res()`
- **功能：** 清空历史采集数据
- **清空内容：**
  - TextFSM解析记录
  - NETCONF失败记录
  - NETCONF数据库下的所有表

#### `MainIn.cmdb_to_mongo()`
- **功能：** 同步CMDB设备信息到MongoDB
- **同步字段：** name, idc__name, serial_num, manage_ip, status, chassis, slot等

---

## 二、新方案（device_api/tasks.py）定时任务采集逻辑

### 2.1 整体架构

```
collect_device_main (主调度任务)
    ↓
collect_device (单个设备采集任务)
    ↓
DeviceCollectionPlans (父采集方案)
    ↓
DeviceSubCollectionPlan (子采集方案列表)
    ↓
DeviceCollectionService.execute_both_collection()
    ↓
南向驱动服务 (south_gateway)
    ↓
Netmiko采集 + NETCONF采集
    ↓
Webhook回调处理数据
    ↓
写入MongoDB
```

### 2.2 核心改进点

1. **父子采集方案结构**
   - 父方案（DeviceCollectionPlans）：定义厂商、设备类型等基本信息
   - 子方案（DeviceSubCollectionPlan）：定义具体的采集配置
   - 一个父方案可以包含多个子方案

2. **统一的采集服务**
   - 通过南向驱动服务（south_gateway）统一执行采集
   - 支持Netmiko和NETCONF两种方式
   - 通过Webhook回调处理采集结果

3. **灵活的配置**
   - 子方案支持独立的Netmiko和NETCONF配置
   - 支持字段映射（field_mappings）
   - 支持自定义数据处理（processor）

4. **数据存储**
   - 采集结果通过Webhook回调处理
   - 支持字段映射转换
   - 支持自定义数据处理逻辑

### 2.3 主调度任务 `collect_device_main(**kwargs)`

**执行流程：**

1. **数据缓存更新** (`datas_to_cache()`)
   - 与旧方案相同，更新ARP、MAC等表数据缓存

2. **CMDB同步** (`MainIn.cmdb_to_mongo()`)
   - 与旧方案相同，同步设备信息到MongoDB

3. **获取设备列表** (`get_device_info_v2(**kwargs)`)
   - 与旧方案相同，获取符合条件的设备列表
   - 过滤条件：只保留有采集方案（plan_id）的设备

4. **清空历史数据** (`clear_his_collect_res()`)
   - 与旧方案相同，清空历史采集数据

5. **批量下发任务**
   - 遍历所有设备
   - 验证设备有效性：
     - IP有效性
     - 采集方案存在且启用
     - 采集方案下有子方案
   - 为每个设备创建 `collect_device` 异步任务

### 2.4 单个设备采集任务 `collect_device(**kwargs)`

**执行流程：**

1. **设备验证**
   - 检查IP有效性
   - 检查是否关联采集方案
   - 检查是否启用自动化

2. **获取父采集方案**
   ```python
   parent_plan = DeviceCollectionPlans.objects.filter(id=plan_id, is_active=True).first()
   ```

3. **获取所有子采集方案**
   ```python
   sub_plans = DeviceSubCollectionPlan.objects.filter(summary_plan=parent_plan).order_by('id')
   ```

4. **遍历执行子采集方案**
   - 对每个子方案调用 `DeviceCollectionService.execute_both_collection()`
   - 该方法会：
     - 检查Netmiko是否启用，如果启用则执行Netmiko采集
     - 检查NETCONF是否启用，如果启用则执行NETCONF采集
     - 通过南向驱动服务执行采集
     - 通过Webhook回调处理结果

5. **统计结果**
   - 记录成功和失败的子方案数量
   - 返回统计信息

### 2.5 采集服务 `DeviceCollectionService.execute_both_collection()`

**执行流程：**

1. **Netmiko采集**（如果启用）
   - 构建netpalm请求参数
   - 调用南向驱动服务执行命令
   - 通过Webhook回调处理结果

2. **NETCONF采集**（如果启用）
   - 获取XML模板（NetconfXMLTemplate）
   - 构建ncclient请求参数
   - 调用南向驱动服务执行NETCONF操作
   - 通过Webhook回调处理结果

3. **结果处理**
   - Webhook回调会：
     - 应用字段映射（field_mappings）
     - 执行自定义数据处理（processor）
     - 写入MongoDB

### 2.6 采集方案模型（新方案）

**DeviceCollectionPlans（父方案）：**
```python
class DeviceCollectionPlans(models.Model):
    name = models.CharField(max_length=100)  # 方案名称
    vendor = models.CharField(max_length=30)  # 厂商
    device_type = models.CharField(max_length=30)  # 设备类型
    is_active = models.BooleanField(default=True)  # 是否启用
```

**DeviceSubCollectionPlan（子方案）：**
```python
class DeviceSubCollectionPlan(models.Model):
    summary_plan = models.ForeignKey(DeviceCollectionPlans)  # 关联父方案
    name = models.CharField(max_length=50)  # 子方案名称
    collection_type = models.CharField(max_length=20)  # 采集类型：arp, mac等
    
    # Netmiko配置
    netmiko_enabled = models.BooleanField(default=True)
    netmiko_method = models.CharField(max_length=100)  # 命令或方法名
    netmiko_field_mappings = models.JSONField()  # 字段映射
    netmiko_processor = models.TextField()  # 自定义数据处理代码
    
    # NETCONF配置
    netconf_enabled = models.BooleanField(default=False)
    netconf_path = models.CharField(max_length=150)  # XML模板路径
    netconf_field_mappings = models.JSONField()  # 字段映射
    netconf_processor = models.TextField()  # 自定义数据处理代码
```

### 2.7 新方案的优势

1. **更灵活的配置**
   - 子方案可以独立配置Netmiko和NETCONF
   - 支持字段映射，适配不同设备的数据格式
   - 支持自定义数据处理逻辑

2. **统一的采集接口**
   - 通过南向驱动服务统一执行采集
   - 解耦采集逻辑和业务逻辑

3. **更好的扩展性**
   - 新增采集类型只需添加子方案
   - 不需要修改代码

4. **数据处理的灵活性**
   - 支持字段映射转换
   - 支持自定义数据处理代码
   - 支持多种数据格式

---

## 三、对比总结

| 对比项 | 旧方案（automation） | 新方案（device_api） |
|--------|---------------------|---------------------|
| **采集方案结构** | 单一方案（CollectionPlan） | 父子方案（DeviceCollectionPlans + DeviceSubCollectionPlan） |
| **命令配置** | JSON格式存储在方案中 | 子方案独立配置（netmiko_method） |
| **NETCONF配置** | JSON格式方法列表 | 子方案独立配置（XML模板） |
| **采集执行** | 直接使用Netmiko/NETCONF | 通过南向驱动服务 |
| **数据解析** | 硬编码的解析逻辑 | 支持字段映射和自定义处理 |
| **数据存储** | 直接写入MongoDB | 通过Webhook回调处理 |
| **扩展性** | 需要修改代码 | 只需配置子方案 |

---

## 四、定时任务配置建议

### 4.1 Celery Beat 配置

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'collect-device-main': {
        'task': 'apps.device_api.tasks.collect_device_main',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点执行
    },
}
```

### 4.2 任务队列配置

- **主调度任务**：可以放在默认队列或专用队列
- **单个设备采集任务**：建议使用 `queue='config'` 队列
- **并发控制**：通过Celery worker数量控制并发度

### 4.3 监控和告警

建议监控以下指标：
- 任务执行成功率
- 任务执行耗时
- 失败设备数量
- 采集数据量

### 2.8 新方案任务函数说明

#### `collect_device(**kwargs)` - 单个设备采集任务
- **功能：** 执行设备关联的父采集方案下的所有子采集方案
- **参数：** 设备信息字典（包含 manage_ip, plan_id 等）
- **执行流程：**
  1. 验证设备有效性
  2. 获取父采集方案（DeviceCollectionPlans）
  3. 获取所有子采集方案（DeviceSubCollectionPlan）
  4. 遍历执行每个子采集方案
  5. 统计成功/失败数量

#### `collect_device_main(**kwargs)` - 主调度任务
- **功能：** 批量获取设备并下发采集任务
- **参数：** 可选的过滤条件（如 manage_ip, vendor__alias 等）
- **执行流程：**
  1. 更新数据缓存
  2. 同步CMDB到MongoDB
  3. 获取设备列表
  4. 清空历史数据
  5. 批量下发采集任务

#### `collect_device_by_plan(plan_id=None)` - 按采集方案执行
- **功能：** 按父采集方案执行采集任务
- **参数：** plan_id（父采集方案ID，None表示所有启用的方案）
- **执行流程：**
  1. 获取父采集方案列表
  2. 遍历每个父方案
  3. 获取该方案下的所有设备
  4. 批量下发采集任务

#### `collect_device_by_sub_plan(device_ip, sub_plan_id)` - 按子方案执行
- **功能：** 对指定设备执行指定的子采集方案
- **参数：** device_ip（设备IP）、sub_plan_id（子采集方案ID）
- **执行流程：**
  1. 验证设备和子方案有效性
  2. 验证设备是否关联了对应的父方案
  3. 执行单个子方案的采集
  4. 返回采集结果

---

## 五、迁移建议

从旧方案迁移到新方案时：

1. **数据迁移**
   - 将 `CollectionPlan` 数据迁移为 `DeviceCollectionPlans` + `DeviceSubCollectionPlan`
   - 将命令列表拆分为多个子方案

2. **功能验证**
   - 对比新旧方案的采集结果
   - 确保数据格式一致

3. **逐步切换**
   - 可以先并行运行新旧方案
   - 验证新方案稳定后再完全切换

