# device_api 替代 automation 架构审视与迁移计划

## 1. 结论

结论分两层：

- 长期上，`device_api` 应该成为网络设备采集、解析、事实回写、结果查询的唯一主链。
- 短期上，`asset.NetworkDevice.plan -> automation.CollectionPlan` 这条旧入口必须保留，直到 `device_api` 的新链路被完整评估、具备桥接能力并经过并跑验证。

这不是保守选择，是上线安全要求。如果现在直接动旧入口，最坏结果不是局部回归，而是新旧链路同时不可用。

---

## 2. 当前问题的结构性判断

### 2.1 旧入口仍然是现网主事实

当前 `asset.NetworkDevice.plan` 仍然指向旧方案：

- [backend/apps/asset/models.py](/Users/lijiamin/.codex/worktrees/device-api-replace-automation/BasePlatform/backend/apps/asset/models.py)

```python
plan = models.ForeignKey("automation.CollectionPlan", ...)
```

这条链路对应的是：

- 设备是否被纳入旧采集体系
- 旧采集任务如何选设备
- 现网大量已配置设备如何继续运行

因此现阶段不能把它直接改成 `device_api.DeviceCollectionPlans`，也不能让它失效。

### 2.2 `device_api` 当前已经具备“新链路形态”，但还不具备“替换条件”

`device_api` 已具备：

- 父方案 / 子方案模型
- 多协议采集执行器
- processors / tools / metadata 三层预处理结构
- 结果按 `collection_type` 标准化入库

但还缺：

- 设备事实回写闭环
- 平台能力画像
- 默认模板自动派发
- 新旧链路桥接
- 全量厂商与产品线覆盖

所以当前正确判断不是“可以直接切换”，而是“新主链已成型，但尚未具备切流条件”。

### 2.3 当前最大卡点不是单个采集类型，而是四类结构问题

1. 设备绑定模型未切干净  
2. 设备事实字段仍依赖人工维护  
3. 设备能力决策还停留在 vendor 级别  
4. `automation` 仍承担采集后的大量结果加工与调度职责

---

## 3. 必须遵守的迁移原则

### 3.1 旧入口不能动

现阶段明确约束：

- `NetworkDevice.plan` 保留
- `automation.CollectionPlan` 保留
- 旧采集调度入口保留

禁止动作：

- 不允许直接把 `NetworkDevice.plan` 改指向 `device_api` 模型
- 不允许直接删除 `automation` 采集入口
- 不允许让 `device_api` 主调度默认只认新绑定关系

### 3.2 新能力只进 `device_api`

从现在开始，采集相关新增需求统一进入 `device_api`：

- 新采集类型
- 新厂商支持
- 新产品线适配
- 新事实回写
- 新查询接口

`automation` 只做：

- 旧链路兼容
- 自动化流程
- 编排 / 执行 / 审计

### 3.3 先桥接，后切流

后续替代必须走这条顺序：

1. 保留旧入口
2. 建立新入口
3. 建立桥接
4. 并跑比对
5. 分批切流
6. 最后收缩旧链路

---

## 4. 目标架构

### 4.1 模块职责

建议收敛为以下分层：

1. `asset`
   - 设备主数据
   - 账号、厂商、型号、位置等事实源

2. `device_api`
   - 原子采集能力
   - 连接管理
   - 厂商差异封装
   - 标准结果入库
   - 设备事实回写

3. `config_center` / `dcs_control` / `topology`
   - 各领域治理和查询

4. `automation`
   - 自动化编排
   - 审批流
   - AutoFlow 留痕
   - 非采集类任务
   - 旧采集入口兼容

5. `NetClaw-CN`
   - 只消费稳定接口，不依赖内部旧模型

### 4.2 必须新增的平台能力画像层

这是替代能否成立的核心。

能力判断不能只靠 `vendor`，至少要考虑：

- vendor
- category
- model family
- os family
- version band
- preferred methods
- fallback methods
- supported collection types

示意：

```python
{
    "key": "huawei_ce_vrp_modern",
    "vendor": "Huawei",
    "category": "switch",
    "model_regex": r"^CE",
    "version_regex": r"V[2-9]",
    "preferred_methods": {
        "route_table": ["netconf", "netmiko"],
        "fan_status": ["netmiko"],
        "version": ["netmiko"]
    },
    "fallback_methods": {
        "route_table": ["netmiko"]
    }
}
```

没有这层，`device_api` 只能做到“多协议采集”，做不到“正确替代旧链路”。

---

## 5. 迁移路线

### Phase 0：定义双轨过渡基线

目标：

- 明确旧入口保留
- 明确新入口建设范围
- 明确桥接约束

产出：

- 本文档
- 仓库规范中关于双轨迁移的说明

### Phase 1：建设新链路，但不替换旧入口

目标：

- 让 `device_api` 有独立可运行的新入口

具体动作：

1. 保持 `NetworkDevice.plan` 不动
2. 使用 `PlansToDevice` 作为 `device_api` 新链路绑定源
3. 所有新模板、新采集类型、新健康能力都只进入 `device_api`
4. 为 `device_api` 提供独立调度入口和查询入口

验收：

- 不依赖 `NetworkDevice.plan`，也能独立跑 `device_api` 采集链

### Phase 2：建设桥接层

目标：

- 让旧入口和新入口可以并行，不互相冲突

建议动作：

1. 增加“旧计划 -> 新模板”的映射关系
2. 为现有 `NetworkDevice.plan` 派生默认 `PlansToDevice`
3. 桥接逻辑只做同步，不做替换
4. 增加桥接状态标识：
   - 未桥接
   - 已桥接
   - 桥接待确认

当前已落地的第一步：

- 新增桥接命令：
  - `python manage.py sync_legacy_plan_bindings`
- 作用：
  - 根据旧的 `NetworkDevice.plan`
  - 按 `plan.name + vendor.alias + category.name`
  - 去匹配 `DeviceCollectionPlans`
  - 然后创建并行的 `PlansToDevice` 绑定关系
- 约束：
  - 只做同步，不修改旧字段
  - 可作为并跑准备动作使用

验收：

- 旧设备可以继续走旧链路
- 同一设备可以具备新链路绑定信息

### Phase 3：设备事实回写闭环

目标：

- 让 `NetworkDevice` 的核心事实由采集自动发现，而不是人工录入

优先事实：

- name
- soft_version
- patch_version
- model
- vendor family / platform profile

验收：

- Huawei / H3C / Ruijie 至少各有一条身份发现闭环

### Phase 4：平台能力画像驱动

目标：

- 让协议路径选择脱离人工硬编码

动作：

1. 建平台画像注册表
2. 建 `collection_type -> preferred_methods -> fallback_methods`
3. 让 `connection_manager` 和执行器改为按画像决策

验收：

- 老 H3C、新 H3C、Huawei CE、Huawei USG、YunShan OS 可走不同路径

### Phase 5：并跑比对

目标：

- 证明新链路具备替换能力

动作：

1. 同设备同类型双链路执行
2. 比较结果数量、字段完整性、稳定性、耗时
3. 形成厂商/类型级切流矩阵

切流条件：

- 结果准确率满足要求
- 失败率不高于旧链路
- 事实回写稳定
- 查询接口已具备

### Phase 6：分批切流

目标：

- 逐厂商、逐类型替代，而不是一次性替换

建议顺序：

1. Huawei 交换机基础事实与接口类
2. H3C 交换机基础事实与接口类
3. Ruijie 健康与基础接口
4. 路由协议
5. 配置拉取
6. 防火墙与治理类事实

### Phase 7：收缩旧链路

条件：

- 新链路并跑验证完成
- 切流矩阵稳定
- NetClaw-CN 已切到稳定接口

动作：

- 停止在 `automation` 中新增采集能力
- 将旧采集入口显式标记为 legacy
- 最后再讨论是否废弃 `NetworkDevice.plan`

---

## 6. 对 NetClaw-CN 的约束

NetClaw-CN 后续不能直接依赖：

- `automation.CollectionPlan`
- `NetworkDevice.plan`
- 各类旧 Mongo 原始表

应该依赖：

- `device_api` 标准结果
- `config_center` 标准配置接口
- `dcs_control` 标准审计接口
- `automation.AutoFlow` 的巡检写回接口

同时，设备能力判断必须留在 BasePlatform，而不是让 NetClaw-CN 再维护一套厂商判断逻辑。

---

## 7. 当前建议的下一步

真正应该先做的，不是继续泛化补采集类型，而是：

1. 保持 `NetworkDevice.plan` 旧入口不动
2. 让 `PlansToDevice` 成为 `device_api` 新链路唯一绑定源
3. 增加旧入口到新入口的桥接设计
4. 建立设备事实回写闭环
5. 引入平台能力画像

这五件事做完，后面的类型扩展和 NetClaw-CN 集成才会真正站稳。
