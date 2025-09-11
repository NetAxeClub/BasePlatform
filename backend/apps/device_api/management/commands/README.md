# Device API 管理命令使用说明

这个目录包含了用于管理Device API数据的Django管理命令。

## 命令列表

### 1. init_summary_plans
初始化采集汇总方案数据

**用法：**
```bash
# 创建汇总方案（如果不存在）
python manage.py init_summary_plans

# 强制重新创建所有汇总方案
python manage.py init_summary_plans --force
```

**功能：**
- 创建预定义的采集汇总方案
- 支持H3C、华为、思科、山石、锐捷、Mellanox、盛科等厂商
- 支持交换机、路由器、防火墙、负载均衡器、服务器等设备类型
- 自动检查重复数据，避免重复创建

**预定义数据：**
- H3C交换机/路由器采集方案
- 华为交换机/路由器采集方案
- 思科交换机/路由器采集方案
- 山石防火墙采集方案
- 锐捷交换机采集方案
- Mellanox交换机采集方案
- 盛科交换机采集方案

### 2. init_collection_plans
初始化设备采集方案数据

**用法：**
```bash
# 创建采集方案（如果不存在）
python manage.py init_collection_plans

# 强制重新创建所有采集方案
python manage.py init_collection_plans --force

# 只为指定汇总方案创建采集方案
python manage.py init_collection_plans --summary-plan "H3C交换机采集方案"
```

**功能：**
- 在汇总方案下创建具体的采集方案
- 支持Netmiko和NETCONF两种采集方式
- 包含示例数据处理代码
- 自动关联到对应的汇总方案

**预定义数据：**
- H3C交换机接口信息采集
- H3C交换机VLAN信息采集
- H3C路由器路由表采集
- 华为交换机接口信息采集
- 思科交换机接口信息采集
- 山石防火墙策略采集

### 3. init_xml_templates
初始化NETCONF XML模板数据

**用法：**
```bash
# 创建XML模板（如果不存在）
python manage.py init_xml_templates

# 强制重新创建所有XML模板
python manage.py init_xml_templates --force

# 只为指定采集方案创建XML模板
python manage.py init_xml_templates --collection-plan "H3C交换机接口信息采集"
```

**功能：**
- 为启用了NETCONF的采集方案创建XML模板
- 包含标准的接口查询、路由查询等模板
- 支持多种厂商的NETCONF查询

**预定义模板：**
- H3C交换机接口状态查询
- H3C交换机接口配置查询
- H3C路由器路由表查询
- 华为交换机接口状态查询
- 思科交换机接口状态查询



### 4. quick_start
快速初始化所有数据

**用法：**
```bash
# 一次性初始化所有数据
python manage.py quick_start

# 强制重新创建所有数据
python manage.py quick_start --force

# 跳过XML模板初始化
python manage.py quick_start --skip-xml
```

**功能：**
- 一次性初始化汇总方案、采集方案、XML模板
- 自动按正确顺序执行所有初始化步骤
- 显示详细的执行过程和统计信息
- 提供下一步使用建议

**执行步骤：**
1. 初始化采集汇总方案
2. 初始化设备采集方案
3. 初始化NETCONF XML模板（可选）
4. 显示数据统计信息
5. 提供使用建议

### 5. cleanup_test_data
清理测试数据

**用法：**
```bash
# 预览将要删除的数据
python manage.py cleanup_test_data --test-only --dry-run

# 清理测试数据
python manage.py cleanup_test_data --test-only --confirm

# 清理所有数据（危险操作）
python manage.py cleanup_test_data --all --confirm
```

**功能：**
- 清理包含"测试"关键词的数据
- 支持清理所有数据（危险操作）
- 级联删除关联数据
- 支持预览模式，避免误删

**安全特性：**
- 使用`--confirm`参数确认删除操作
- 支持预览模式查看将要删除的数据
- 事务保护，删除失败时自动回滚

## 使用建议

### 1. 快速开始（推荐）
```bash
# 一次性初始化所有数据
python manage.py quick_start
```

### 2. 分步初始化
```bash
# 1. 初始化汇总方案
python manage.py init_summary_plans

# 2. 初始化采集方案
python manage.py init_collection_plans

# 3. 初始化XML模板
python manage.py init_xml_templates
```



### 2. 测试数据管理
```bash
# 1. 预览测试数据
python manage.py cleanup_test_data --test-only --dry-run

# 2. 清理测试数据
python manage.py cleanup_test_data --test-only --confirm
```

## 注意事项

1. **备份数据**：在执行删除或迁移操作前，建议备份数据库
2. **测试环境**：建议在测试环境中先验证命令功能
3. **权限控制**：确保有足够的数据库操作权限
4. **事务安全**：所有命令都使用事务保护，失败时自动回滚

## 错误处理

如果命令执行失败：

1. 检查Django环境是否正确配置
2. 确认数据库连接正常
3. 查看错误日志获取详细信息
4. 使用`--dry-run`参数预览操作

## 自定义数据

如果需要添加自定义数据：

1. 修改对应命令文件中的数据定义
2. 按照现有格式添加新的数据项
3. 重新运行命令创建数据

## 联系支持

如果遇到问题或需要帮助，请：
1. 查看Django错误日志
2. 检查数据库连接和权限
3. 联系开发团队获取支持 